from __future__ import annotations

import json
import logging
import re

from app.agents.contracts import AgentContext, AgentStep, SubQuery
from app.agents.memory import ConversationMemory
from app.ms_agent_client import MicrosoftAgentFrameworkClient

logger = logging.getLogger(__name__)


class PlannerAgent(AgentStep):
    """Routes intent and decomposes complex questions into sub-queries."""

    def __init__(
        self,
        ms_agent_client: MicrosoftAgentFrameworkClient | None = None,
        memory: ConversationMemory | None = None,
    ) -> None:
        self._ms_agent_client = ms_agent_client
        self._memory = memory

    async def run(self, context: AgentContext) -> AgentContext:
        message = context.user_message.strip()

        # Inject conversation history
        if self._memory:
            context.conversation_history = self._memory.get_history(
                context.conversation_id,
            )

        if self._ms_agent_client and self._ms_agent_client.enabled:
            await self._smart_plan(context, message)
        else:
            self._fallback_plan(context, message)

        context.metadata["intent"] = context.intent or ""
        context.metadata["route"] = context.route or ""
        context.metadata["sub_query_count"] = len(context.sub_queries)
        return context

    async def _smart_plan(self, context: AgentContext, message: str) -> None:
        history_block = ""
        if self._memory:
            history_block = self._memory.format_history_for_prompt(
                context.conversation_id,
            )

        prompt = (
            "You are an expert analytical intent router and query planner for a SQL data analytics system.\n"
            "Your job is to analyze the user's message and produce a structured JSON plan.\n\n"
            "RULES:\n"
            "1. If the user asks ANYTHING related to data, numbers, reports, KPIs, products, sales, "
            "customers, trends, comparisons, insights, analysis, databases, tables, or asks you to "
            "'do it', 'show me', 'tell me about' data — route as 'analytics'.\n"
            "2. ONLY route as 'chat' if it's a pure greeting, off-topic question, or meta-question "
            "about how you work.\n"
            "3. For complex questions (executive reports, multi-dimensional analysis, trend + comparison), "
            "decompose into 2-4 focused sub-queries. Each sub-query should answer ONE specific analytical dimension.\n"
            "4. For simple questions (single metric, one table lookup), use a single sub-query.\n"
            "5. If the user references a previous conversation turn (e.g. 'tell me more', 'the first one', "
            "'do it'), look at the conversation history and create a concrete analytical sub-query.\n"
            "6. ALWAYS write sub-query questions in a way that a SQL expert could directly translate them.\n\n"
            f"{history_block}\n\n"
            f"USER MESSAGE: \"{message}\"\n\n"
            "Respond with ONLY valid JSON (no markdown, no backticks):\n"
            "{\n"
            '  "intent": "analytics" or "chat",\n'
            '  "execution_plan": "Brief reasoning about your routing decision (1-2 sentences)",\n'
            '  "refined_question": "The user\'s question rewritten as a clear analytical request",\n'
            '  "sub_queries": [\n'
            '    {"id": "sq1", "question": "Specific analytical question", "purpose": "category like revenue_kpis, top_products, trend_analysis, customer_analysis, etc."}\n'
            "  ]\n"
            "}\n\n"
            "For chat intent, sub_queries should be an empty array.\n"
            "For executive reports, generate 3-4 sub-queries covering different analytical dimensions.\n"
        )

        try:
            raw = await self._ms_agent_client.generate(prompt)
            parsed = self._parse_plan_json(raw)

            context.intent = parsed.get("intent", "analytics")
            context.execution_plan = parsed.get("execution_plan", "")
            context.analysis_question = parsed.get("refined_question", message)

            if context.intent == "chat":
                context.route = "chat_pipeline"
                return

            context.route = "sql_pipeline"
            sub_queries_raw = parsed.get("sub_queries", [])
            if sub_queries_raw:
                for sq in sub_queries_raw:
                    context.sub_queries.append(
                        SubQuery(
                            id=sq.get("id", f"sq{len(context.sub_queries)+1}"),
                            question=sq.get("question", message),
                            purpose=sq.get("purpose", "general"),
                        ),
                    )
            else:
                context.sub_queries.append(
                    SubQuery(id="sq1", question=message, purpose="general"),
                )
        except Exception as error:
            logger.warning("Smart planning failed, using fallback: %s", error)
            self._fallback_plan(context, message)

    def _fallback_plan(self, context: AgentContext, message: str) -> None:
        _chat_only_markers = (
            "hola", "hello", "hi", "hey", "buenos días", "buenas tardes",
            "buenas noches", "gracias", "thank", "adiós", "bye",
            "cómo estás", "cuéntame sobre ti",
        )
        lowered = message.lower()
        is_chat = any(lowered.strip() == marker for marker in _chat_only_markers)

        if is_chat:
            context.intent = "general"
            context.route = "chat_pipeline"
            context.analysis_question = message
        else:
            context.intent = "analytics"
            context.route = "sql_pipeline"
            context.analysis_question = message
            context.sub_queries.append(
                SubQuery(id="sq1", question=message, purpose="general"),
            )

    def _parse_plan_json(self, raw: str) -> dict:
        cleaned = raw.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

        json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if json_match:
            cleaned = json_match.group(0)

        return json.loads(cleaned)

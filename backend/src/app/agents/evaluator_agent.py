from __future__ import annotations

import json
import logging

from app.agents.contracts import AgentContext, AgentStep
from app.json_utils import to_json_compatible
from app.ms_agent_client import MicrosoftAgentFrameworkClient

logger = logging.getLogger(__name__)


class EvaluatorAgent(AgentStep):
    """Executive-grade report generator.

    Transforms raw SQL results into McKinsey/BCG-quality analytical reports
    with structured sections, data-driven insights, and strategic recommendations.
    """

    def __init__(self, ms_agent_client: MicrosoftAgentFrameworkClient) -> None:
        self._ms_agent_client = ms_agent_client

    async def run(self, context: AgentContext) -> AgentContext:
        if context.route == "chat_pipeline":
            return await self._handle_chat(context)

        return await self._handle_analytics(context)

    async def _handle_chat(self, context: AgentContext) -> AgentContext:
        if not self._ms_agent_client.enabled:
            context.response = "No response provider configured."
            return context

        prompt = (
            "You are an expert business data analyst. The user is talking to you in a chat.\n"
            "You MUST respond ENTIRELY in English. Do not use Spanish or any other language, even if the user or the query results contain it.\n"
            "If the user greets you, briefly introduce yourself as an expert data analyst who can:\n"
            "- Generate executive reports with real KPIs from the database\n"
            "- Analyze sales, product, and customer trends\n"
            "- Create comparative analysis and detect anomalies\n"
            "- Answer complex questions with JOINs and multi-dimensional analysis\n\n"
            "Suggest 2-3 interesting analytical questions they could ask.\n"
            "NEVER give generic steps — always offer to act directly on the data.\n\n"
            f"User message: {context.user_message}\n"
        )
        context.response = await self._ms_agent_client.generate(prompt)
        context.metadata["response_provider"] = "microsoft_agent_framework"
        return context

    async def _handle_analytics(self, context: AgentContext) -> AgentContext:
        # Build data context from sub-queries or main result
        data_context = self._build_data_context(context)

        # Build query transparency
        query_transparency = self._build_query_transparency(context)

        if not self._ms_agent_client.enabled:
            context.response = self._build_fallback_response(context, data_context)
            return context

        # Count total rows across all sub-queries
        total_rows = sum(sq.row_count for sq in context.sub_queries) if context.sub_queries else len(context.query_result_rows)
        sub_query_summary = ""
        if context.sub_queries:
            summaries = []
            for sq in context.sub_queries:
                status = f"✅ {sq.row_count} rows" if sq.row_count > 0 else f"❌ {sq.error or 'no data'}"
                summaries.append(f"- [{sq.id}] {sq.purpose}: {sq.question} → {status}")
            sub_query_summary = "\n".join(summaries)

        prompt = (
            "You are a SENIOR MANAGEMENT CONSULTANT at McKinsey & Company presenting to a C-level executive.\n"
            "Your job is to transform raw SQL query results into a WORLD-CLASS executive analytical report.\n\n"
            "=== OUTPUT FORMAT (Respond ENTIRELY in English, use Markdown) ===\n\n"
            "## 📊 Executive Summary\n"
            "2-3 sentences capturing THE most important insight from the data. Lead with the biggest number or trend.\n\n"
            "## 📈 Key Metrics\n"
            "Present key metrics as a clear comparison. Use formatted numbers (e.g., $1,234,567). "
            "If the data has rankings, present as a numbered list with metrics. "
            "If there's time-series data, highlight trends with ↑ ↗ → ↘ ↓ arrows.\n\n"
            "## 🔍 Deep Analysis\n"
            "3-5 bullet points with SPECIFIC insights derived from the data:\n"
            "- Patterns, anomalies, concentrations, outliers\n"
            "- Percentage contributions and Pareto analysis\n"
            "- Growth/decline trends with specific numbers\n"
            "- Cross-dimensional correlations (if multiple data sets)\n\n"
            "## 💡 Strategic Recommendations\n"
            "3 actionable, data-driven recommendations. Each should reference specific numbers from the analysis.\n\n"
            "## 🔗 Data Traceability\n"
            "Brief note on which tables and queries produced these insights (for transparency).\n\n"
            "=== RULES ===\n"
            "1. ALWAYS reference specific numbers from the data — never be vague.\n"
            "2. Format large numbers with thousands separators.\n"
            "3. Calculate percentages and shares when the data allows.\n"
            "4. If data is empty or minimal, acknowledge it and suggest better queries.\n"
            "5. Use emojis sparingly for section headers only.\n"
            "6. Keep it under 800 words but rich in substance.\n"
            "7. Be bold in your insights — identify the 'so what?' for the business.\n"
            "8. You MUST write your ENTIRE report in English. No exceptions.\n\n"
            f"=== ORIGINAL QUESTION ===\n{context.analysis_question or context.user_message}\n\n"
        )

        if context.execution_plan:
            prompt += f"=== EXECUTION PLAN ===\n{context.execution_plan}\n\n"

        if sub_query_summary:
            prompt += f"=== SUB-QUERIES EXECUTED ===\n{sub_query_summary}\n\n"

        prompt += (
            f"=== DATA RESULTS ({total_rows} total rows) ===\n{data_context}\n\n"
            f"=== QUERIES USED ===\n{query_transparency}\n\n"
            "Generate the executive report now.\n"
        )

        context.response = await self._ms_agent_client.generate(prompt)
        context.metadata["response_provider"] = "microsoft_agent_framework"

        # Build result preview for transparency panel
        self._set_result_preview(context)

        return context

    def _build_data_context(self, context: AgentContext) -> str:
        parts: list[str] = []

        if context.sub_queries:
            for sq in context.sub_queries:
                if sq.result_rows:
                    preview = sq.result_rows[:15]
                    data_json = json.dumps(
                        to_json_compatible(preview),
                        ensure_ascii=False,
                        indent=None,
                    )
                    parts.append(
                        f"--- Sub-query [{sq.id}]: {sq.purpose} ---\n"
                        f"Question: {sq.question}\n"
                        f"Rows: {sq.row_count}\n"
                        f"Data:\n{data_json}\n"
                    )
                elif sq.error:
                    parts.append(
                        f"--- Sub-query [{sq.id}]: {sq.purpose} ---\n"
                        f"ERROR: {sq.error}\n"
                    )
        elif context.query_result_rows:
            preview = context.query_result_rows[:20]
            data_json = json.dumps(
                to_json_compatible(preview),
                ensure_ascii=False,
                indent=None,
            )
            parts.append(f"Data ({len(context.query_result_rows)} rows):\n{data_json}")

        return "\n\n".join(parts) if parts else "No data returned."

    def _build_query_transparency(self, context: AgentContext) -> str:
        queries: list[str] = []

        if context.sub_queries:
            for sq in context.sub_queries:
                sql = sq.validated_sql or sq.sql
                if sql:
                    queries.append(f"[{sq.id} - {sq.purpose}]:\n{sql}")
        elif context.validated_sql:
            queries.append(context.validated_sql)
        elif context.generated_sql:
            queries.append(context.generated_sql)

        return "\n\n".join(queries) if queries else "No queries executed."

    def _build_fallback_response(self, context: AgentContext, data_context: str) -> str:
        total = sum(sq.row_count for sq in context.sub_queries) if context.sub_queries else len(context.query_result_rows)
        return (
            f"Queries executed successfully. "
            f"Total rows: {total}.\n\n"
            f"Data:\n{data_context[:2000]}"
        )

    def _set_result_preview(self, context: AgentContext) -> None:
        if context.sub_queries:
            preview_data = {}
            for sq in context.sub_queries:
                if sq.result_rows:
                    preview_data[sq.id] = sq.result_rows[:10]
            context.query_result_preview = json.dumps(
                to_json_compatible(preview_data),
                ensure_ascii=False,
            )
        elif context.query_result_rows:
            preview = context.query_result_rows[:10]
            context.query_result_preview = json.dumps(
                to_json_compatible(preview),
                ensure_ascii=False,
            )

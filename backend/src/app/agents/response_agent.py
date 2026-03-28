from __future__ import annotations

from app.agents.contracts import AgentContext, AgentStep
from app.ms_agent_client import MicrosoftAgentFrameworkClient


class ResponseAgent(AgentStep):
    def __init__(self, ms_agent_client: MicrosoftAgentFrameworkClient) -> None:
        self._ms_agent_client = ms_agent_client

    async def run(self, context: AgentContext) -> AgentContext:
        prompt = (
            "Answer the user ENTIRELY in English with concise bullet points and practical next steps. Do not use any other language.\n"
            f"Intent: {context.intent}\n"
            f"Request: {context.user_message}"
        )

        if not self._ms_agent_client.enabled:
            raise RuntimeError(
                "Microsoft Agent Framework is not configured. "
                "Define AZURE_OPENAI_RESPONSES_DEPLOYMENT_NAME and one of these methods: "
                "(AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY) or AZURE_AI_PROJECT_ENDPOINT."
            )

        context.response = await self._ms_agent_client.generate(prompt)
        context.metadata["response_provider"] = "microsoft_agent_framework"
        return context

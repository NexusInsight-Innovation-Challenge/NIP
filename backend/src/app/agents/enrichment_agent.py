from __future__ import annotations

from datetime import UTC, datetime

from app.agents.contracts import AgentContext, AgentStep


class EnrichmentAgent(AgentStep):
    async def run(self, context: AgentContext) -> AgentContext:
        timestamp = datetime.now(UTC).isoformat()
        context.enriched_message = (
            f"[intent={context.intent}] [ts={timestamp}] User request: {context.user_message}"
        )
        context.metadata["enriched_at"] = timestamp
        return context

from __future__ import annotations

from app.agents.contracts import AgentContext, AgentStep


class IntentClassifierAgent(AgentStep):
    async def run(self, context: AgentContext) -> AgentContext:
        message = context.user_message.lower()
        if any(token in message for token in ["error", "bug", "fail", "falla"]):
            intent = "debugging"
        elif any(token in message for token in ["optimi", "performance", "speed", "rápido"]):
            intent = "optimization"
        elif any(token in message for token in ["how", "explain", "cómo", "explica"]):
            intent = "explanation"
        else:
            intent = "general"

        context.intent = intent
        context.metadata["intent"] = intent
        return context

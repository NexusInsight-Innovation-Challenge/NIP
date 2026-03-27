from __future__ import annotations

import time

from app.agents.contracts import AgentContext, AgentStep


class AgentPipeline:
    def __init__(self, steps: list[AgentStep]) -> None:
        self._steps = steps

    async def run(self, context: AgentContext) -> AgentContext:
        state = context
        for step in self._steps:
            started = time.perf_counter()
            state = await step.run(state)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            step_name = step.__class__.__name__
            state.metadata[f"stage_ms.{step_name}"] = elapsed_ms

            # Short-circuit: skip remaining steps for chat pipeline after Planner
            if state.route == "chat_pipeline" and step_name == "PlannerAgent":
                # Jump directly to evaluator (last step)
                evaluator = self._steps[-1]
                eval_start = time.perf_counter()
                state = await evaluator.run(state)
                eval_ms = int((time.perf_counter() - eval_start) * 1000)
                state.metadata[f"stage_ms.{evaluator.__class__.__name__}"] = eval_ms
                return state

        return state

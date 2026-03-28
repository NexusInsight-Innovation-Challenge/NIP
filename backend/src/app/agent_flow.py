from __future__ import annotations

import time

from app.agents.contracts import AgentContext, AgentStep


class AgentPipeline:
    def __init__(self, steps: list[AgentStep]) -> None:
        self._steps = steps

    async def run(self, context: AgentContext) -> AgentContext:
        if not self._steps:
            return context
        return await self._run_steps(context, 0, len(self._steps) - 1, allow_chat_short_circuit=True)

    async def run_until(self, context: AgentContext, step_name: str) -> AgentContext:
        if not self._steps:
            return context
        index = self._find_step_index(step_name)
        return await self._run_steps(context, 0, index, allow_chat_short_circuit=True)

    async def run_from(self, context: AgentContext, after_step_name: str) -> AgentContext:
        if not self._steps:
            return context
        index = self._find_step_index(after_step_name)
        start_index = index + 1
        if start_index >= len(self._steps):
            return context
        return await self._run_steps(
            context,
            start_index,
            len(self._steps) - 1,
            allow_chat_short_circuit=False,
        )

    def _find_step_index(self, step_name: str) -> int:
        for index, step in enumerate(self._steps):
            if step.__class__.__name__ == step_name:
                return index
        raise ValueError(f"Step not found in pipeline: {step_name}")

    async def _run_steps(
        self,
        context: AgentContext,
        start_index: int,
        end_index: int,
        *,
        allow_chat_short_circuit: bool,
    ) -> AgentContext:
        state = context
        for index in range(start_index, end_index + 1):
            step = self._steps[index]
            started = time.perf_counter()
            state = await step.run(state)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            step_name = step.__class__.__name__
            state.metadata[f"stage_ms.{step_name}"] = elapsed_ms

            # Short-circuit: skip remaining steps for chat pipeline after Planner
            if (
                allow_chat_short_circuit
                and state.route == "chat_pipeline"
                and step_name == "PlannerAgent"
            ):
                # Jump directly to evaluator (last step)
                evaluator = self._steps[-1]
                eval_start = time.perf_counter()
                state = await evaluator.run(state)
                eval_ms = int((time.perf_counter() - eval_start) * 1000)
                state.metadata[f"stage_ms.{evaluator.__class__.__name__}"] = eval_ms
                return state

        return state

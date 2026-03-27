from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SubQuery:
    """A single analytical sub-question produced by the Planner."""

    id: str
    question: str
    purpose: str  # e.g. "revenue_kpis", "top_products", "trend"
    sql: str | None = None
    validated_sql: str | None = None
    result_rows: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    error: str | None = None
    execution_ms: int = 0


@dataclass(slots=True)
class ReportSection:
    """A structured section of the executive report."""

    title: str
    content: str
    source_query_id: str | None = None


@dataclass(slots=True)
class ConversationTurn:
    """A single turn in conversation history."""

    role: str  # "user" or "assistant"
    message: str
    sql: str | None = None
    row_count: int | None = None


@dataclass(slots=True)
class AgentContext:
    conversation_id: str
    correlation_id: str
    user_message: str

    # Planner outputs
    intent: str | None = None
    route: str | None = None
    analysis_question: str | None = None
    execution_plan: str | None = None

    # Sub-query decomposition (for complex / executive reports)
    sub_queries: list[SubQuery] = field(default_factory=list)

    # Librarian outputs
    schema_context: str | None = None
    schema_tables: list[str] = field(default_factory=list)
    fk_context: str | None = None

    # SQL Coder outputs
    generated_sql: str | None = None

    # Critic / Validator outputs
    validated_sql: str | None = None

    # Execution outputs
    query_result_rows: list[dict[str, Any]] = field(default_factory=list)
    query_result_preview: str | None = None

    # Evaluator outputs
    report_sections: list[ReportSection] = field(default_factory=list)
    enriched_message: str | None = None
    response: str | None = None

    # Conversation memory
    conversation_history: list[ConversationTurn] = field(default_factory=list)

    # Telemetry
    metadata: dict[str, str | int | float | bool] = field(default_factory=dict)


class AgentStep:
    async def run(self, context: AgentContext) -> AgentContext:
        raise NotImplementedError

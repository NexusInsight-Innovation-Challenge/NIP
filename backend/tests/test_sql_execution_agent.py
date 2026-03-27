from __future__ import annotations

import pytest

from app.agents.contracts import AgentContext, SubQuery
from app.agents.sql_execution_agent import SQLExecutionAgent
from app.data.sql_tool import SQLExecutionResult


class FakeSQLToolOK:
    enabled = True

    def validate_select_query(self, sql: str) -> str:
        return sql

    async def execute_select(self, sql: str) -> SQLExecutionResult:  # noqa: ARG002
        return SQLExecutionResult(rows=[{"ok": 1}], row_count=1, elapsed_ms=10)


class FakeFailingSQLTool:
    enabled = True

    def __init__(self) -> None:
        self.executed_sql: list[str] = []

    def validate_select_query(self, sql: str) -> str:
        return sql

    async def execute_select(self, sql: str) -> SQLExecutionResult:
        self.executed_sql.append(sql)
        if "FROM [dbo].[Sales]" in sql:
            return SQLExecutionResult(rows=[{"fallback": 1}], row_count=1, elapsed_ms=12)
        raise RuntimeError("Incorrect syntax near the keyword 'or'.")


@pytest.mark.asyncio
async def test_execution_agent_runs_validated_sql() -> None:
    agent = SQLExecutionAgent(FakeSQLToolOK())
    context = AgentContext(
        conversation_id="c1",
        correlation_id="corr1",
        user_message="ventas",
        route="sql_pipeline",
        validated_sql="SELECT TOP 10 * FROM dbo.Sales",
    )

    result = await agent.run(context)

    assert result.query_result_rows == [{"ok": 1}]
    assert result.metadata["rows_returned"] == 1


@pytest.mark.asyncio
async def test_execution_agent_runs_sub_queries() -> None:
    agent = SQLExecutionAgent(FakeSQLToolOK())
    context = AgentContext(
        conversation_id="c1",
        correlation_id="corr1",
        user_message="executive report",
        route="sql_pipeline",
        sub_queries=[
            SubQuery(id="sq1", question="revenue", purpose="kpis", validated_sql="SELECT SUM(amount) FROM sales"),
            SubQuery(id="sq2", question="top products", purpose="ranking", validated_sql="SELECT name FROM products"),
        ],
    )

    result = await agent.run(context)

    assert result.metadata["sub_queries_executed"] == 2
    assert result.metadata["sub_queries_failed"] == 0
    assert result.metadata["rows_returned"] == 2  # 1 row per sub-query


@pytest.mark.asyncio
async def test_execution_agent_handles_sub_query_failure_gracefully() -> None:
    sql_tool = FakeFailingSQLTool()
    agent = SQLExecutionAgent(sql_tool)
    context = AgentContext(
        conversation_id="c1",
        correlation_id="corr1",
        user_message="report",
        route="sql_pipeline",
        sub_queries=[
            SubQuery(id="sq1", question="revenue", purpose="kpis", validated_sql="SELECT bad FROM dbo.Unknown"),
            SubQuery(id="sq2", question="fallback", purpose="backup", validated_sql="SELECT COUNT(*) FROM [dbo].[Sales]"),
        ],
    )

    result = await agent.run(context)

    assert result.metadata["sub_queries_executed"] == 1
    assert result.metadata["sub_queries_failed"] == 1
    assert any(sq.error for sq in result.sub_queries)


@pytest.mark.asyncio
async def test_execution_agent_raises_when_no_validated_sql() -> None:
    agent = SQLExecutionAgent(FakeSQLToolOK())
    context = AgentContext(
        conversation_id="c1",
        correlation_id="corr1",
        user_message="report",
        route="sql_pipeline",
    )

    with pytest.raises(RuntimeError, match="No validated SQL"):
        await agent.run(context)


@pytest.mark.asyncio
async def test_execution_skips_non_sql_pipeline() -> None:
    agent = SQLExecutionAgent(FakeSQLToolOK())
    context = AgentContext(
        conversation_id="c1",
        correlation_id="corr1",
        user_message="hello",
        route="chat_pipeline",
    )

    result = await agent.run(context)
    assert result.query_result_rows == []

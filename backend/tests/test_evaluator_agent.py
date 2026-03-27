from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.agents.contracts import AgentContext, SubQuery
from app.agents.evaluator_agent import EvaluatorAgent


class FakeMsClientDisabled:
    enabled = False

    async def generate(self, prompt: str) -> str:  # noqa: ARG002
        return "unused"


@pytest.mark.asyncio
async def test_evaluator_fallback_with_single_query() -> None:
    agent = EvaluatorAgent(FakeMsClientDisabled())
    context = AgentContext(
        conversation_id="c1",
        correlation_id="corr1",
        user_message="ventas",
        route="sql_pipeline",
        analysis_question="ventas por fecha",
        validated_sql="SELECT TOP (10) * FROM dbo.Sales",
        query_result_rows=[
            {
                "sale_date": date(2024, 1, 2),
                "created_at": datetime(2024, 1, 2, 10, 30, 0),
                "amount": Decimal("12.34"),
                "customer_id": uuid4(),
                "payload": b"ok",
            }
        ],
    )

    result = await agent.run(context)

    assert result.response is not None
    assert "Consultas ejecutadas correctamente" in result.response or "Total de filas" in result.response


@pytest.mark.asyncio
async def test_evaluator_fallback_with_sub_queries() -> None:
    agent = EvaluatorAgent(FakeMsClientDisabled())
    context = AgentContext(
        conversation_id="c1",
        correlation_id="corr1",
        user_message="executive report",
        route="sql_pipeline",
        analysis_question="executive report",
        sub_queries=[
            SubQuery(
                id="sq1", question="revenue", purpose="kpis",
                validated_sql="SELECT SUM(amount) FROM sales",
                result_rows=[{"total": 1000000}], row_count=1,
            ),
            SubQuery(
                id="sq2", question="top products", purpose="ranking",
                validated_sql="SELECT name FROM products",
                result_rows=[{"name": "ProductA"}, {"name": "ProductB"}], row_count=2,
            ),
        ],
    )

    result = await agent.run(context)

    assert result.response is not None
    assert "3" in result.response  # total rows = 1 + 2


@pytest.mark.asyncio
async def test_evaluator_chat_pipeline_fallback() -> None:
    agent = EvaluatorAgent(FakeMsClientDisabled())
    context = AgentContext(
        conversation_id="c1",
        correlation_id="corr1",
        user_message="hola",
        route="chat_pipeline",
    )

    result = await agent.run(context)

    assert result.response is not None
    assert "No hay proveedor" in result.response
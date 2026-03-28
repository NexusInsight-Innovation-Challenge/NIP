from __future__ import annotations

import pytest

from app.agents.contracts import AgentContext
from app.config import Settings
from app.sensitivity_policy import SensitivityPolicy


class _FakeClient:
    enabled = False


@pytest.fixture
def settings() -> Settings:
    return Settings(
        AZURE_WEBPUBSUB_CONNECTION_STRING="Endpoint=sb://demo/;AccessKey=test",
        AZURE_WEBPUBSUB_HUB_NAME="hubdemo",
        AZURE_WEBPUBSUB_GROUP="groupdemo",
    )


@pytest.mark.asyncio
async def test_sensitivity_policy_flags_pii_as_high(settings: Settings) -> None:
    policy = SensitivityPolicy(settings, _FakeClient())
    context = AgentContext(
        conversation_id="c1",
        correlation_id="corr1",
        user_message="Dame email y teléfono de todos los clientes",
        route="sql_pipeline",
        validated_sql="SELECT email, phone FROM dbo.Customers",
    )

    assessment = await policy.assess(context)

    assert assessment.requires_approval is True
    assert assessment.risk_level == "high"
    assert "pii" in assessment.categories


@pytest.mark.asyncio
async def test_sensitivity_policy_allows_non_sensitive_query(settings: Settings) -> None:
    policy = SensitivityPolicy(settings, _FakeClient())
    context = AgentContext(
        conversation_id="c1",
        correlation_id="corr1",
        user_message="Top 10 productos por unidades vendidas",
        route="sql_pipeline",
        validated_sql="SELECT TOP (10) ProductName, SUM(Qty) AS units FROM dbo.Sales GROUP BY ProductName",
    )

    assessment = await policy.assess(context)

    assert assessment.requires_approval is False
    assert assessment.risk_level == "low"

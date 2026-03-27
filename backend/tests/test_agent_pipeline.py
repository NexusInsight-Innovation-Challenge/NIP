import pytest

from app.agent_flow import AgentPipeline
from app.agents.contracts import AgentContext
from app.agents.critic_agent import CriticAgent
from app.agents.evaluator_agent import EvaluatorAgent
from app.agents.librarian_agent import LibrarianAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.sql_coder_agent import SQLCoderAgent
from app.agents.sql_execution_agent import SQLExecutionAgent
from app.ms_agent_client import MicrosoftAgentFrameworkClient


class DummySettings:
    azure_ai_project_endpoint = None
    azure_openai_responses_deployment_name = None
    azure_openai_endpoint = None
    azure_openai_api_key = None
    azure_openai_api_version = None
    azure_sql_connection_string = None
    sql_query_timeout_seconds = 5
    sql_row_limit = 100
    sql_require_schema_catalog = False
    sql_max_retry_corrections = 1


class FakeSQLTool:
    enabled = False

    async def get_table_catalog(self, max_tables: int = 200) -> list[str]:  # noqa: ARG002
        return []

    async def get_schema_context(self, max_tables: int = 12) -> str:  # noqa: ARG002
        return "disabled"

    async def get_rich_schema_context(self, max_tables: int = 80) -> str:  # noqa: ARG002
        return "disabled"

    async def get_foreign_key_context(self) -> str:
        return ""

    def validate_select_query(self, sql: str) -> str:
        return sql

    def find_unknown_tables(self, sql: str, catalog: list[str]) -> list[str]:  # noqa: ARG002
        return []

    async def execute_select(self, sql: str):  # noqa: ANN201, ARG002
        raise RuntimeError("Not expected in these tests")


def create_pipeline() -> AgentPipeline:
    ms_client = MicrosoftAgentFrameworkClient(DummySettings())
    sql_tool = FakeSQLTool()
    return AgentPipeline(
        [
            PlannerAgent(),
            LibrarianAgent(sql_tool),
            SQLCoderAgent(ms_client),
            CriticAgent(sql_tool, ms_client),
            SQLExecutionAgent(sql_tool),
            EvaluatorAgent(ms_client),
        ]
    )


@pytest.mark.asyncio
async def test_pipeline_general_query_without_agent_framework_returns_fallback() -> None:
    pipeline = create_pipeline()
    context = AgentContext(
        conversation_id="c1",
        correlation_id="corr1",
        user_message="hola",
    )

    result = await pipeline.run(context)
    assert result.route == "chat_pipeline"
    assert result.response is not None
    assert "No hay proveedor" in result.response


@pytest.mark.asyncio
async def test_pipeline_analytics_query_requires_agent_framework_for_sql_generation() -> None:
    pipeline = create_pipeline()
    context = AgentContext(
        conversation_id="c1",
        correlation_id="corr1",
        user_message="Dame un reporte SQL de ventas por mes",
    )

    with pytest.raises(RuntimeError, match="Microsoft Agent Framework"):
        await pipeline.run(context)

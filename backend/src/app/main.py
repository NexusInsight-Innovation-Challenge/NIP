from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.agent_flow import AgentPipeline
from app.agents.critic_agent import CriticAgent
from app.agents.evaluator_agent import EvaluatorAgent
from app.agents.librarian_agent import LibrarianAgent
from app.agents.memory import ConversationMemory
from app.agents.planner_agent import PlannerAgent
from app.agents.sql_coder_agent import SQLCoderAgent
from app.agents.sql_execution_agent import SQLExecutionAgent
from app.backend_listener import BackendRealtimeListener
from app.config import get_settings
from app.data.sql_suggestions import build_suggestions_from_catalog
from app.data.sql_tool import AzureSQLTool
from app.logging_config import configure_logging
from app.models import EnvelopeMetadata, EventType, MessageEnvelope, UserMessageInput
from app.ms_agent_client import MicrosoftAgentFrameworkClient
from app.pubsub_service import PubSubService

logger = logging.getLogger(__name__)
settings = get_settings()
configure_logging(settings.app_log_level)

pubsub_service = PubSubService(settings)
ms_agent_client = MicrosoftAgentFrameworkClient(settings)
sql_tool = AzureSQLTool(settings)
memory = ConversationMemory()

sql_coder = SQLCoderAgent(ms_agent_client)

pipeline = AgentPipeline(
    [
        PlannerAgent(ms_agent_client, memory),
        LibrarianAgent(sql_tool),
        sql_coder,
        CriticAgent(sql_tool, ms_agent_client, max_retries=settings.sql_max_retry_corrections),
        SQLExecutionAgent(sql_tool, sql_coder=sql_coder, max_retries=2),
        EvaluatorAgent(ms_agent_client),
    ],
)
listener = BackendRealtimeListener(pubsub_service, pipeline, memory)


@asynccontextmanager
async def lifespan(_: FastAPI):
    listener_task = asyncio.create_task(listener.start())
    logger.info("Backend listener started")
    try:
        yield
    finally:
        await listener.stop()
        listener_task.cancel()
        with suppress(asyncio.CancelledError):
            await listener_task


app = FastAPI(title="Azure Web PubSub + Agent Framework Demo", lifespan=lifespan)
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready"}


@app.post("/api/negotiate")
async def negotiate(user_id: str = "frontend-user") -> dict[str, str]:
    try:
        access = pubsub_service.negotiate_client(user_id=user_id)
        return {
            "url": access.url,
            "hub": access.hub,
            "group": access.group,
            "userId": access.user_id,
        }
    except Exception as error:  # noqa: BLE001
        logger.exception("Negotiate failed: %s", error)
        raise HTTPException(status_code=500, detail="Could not negotiate client") from error


@app.post("/api/messages")
async def publish_message(body: UserMessageInput) -> dict[str, str]:
    envelope = MessageEnvelope(
        event_type=EventType.USER_MESSAGE,
        conversation_id=body.conversation_id,
        role="user",
        payload={"message": body.message, "userId": body.user_id},
        metadata=EnvelopeMetadata(source="backend.api"),
    )
    try:
        pubsub_service.send_json_to_group(envelope.model_dump(mode="json"))
        return {
            "status": "queued",
            "conversationId": envelope.conversation_id,
            "correlationId": envelope.correlation_id,
        }
    except Exception as error:  # noqa: BLE001
        logger.exception("Publish failed: %s", error)
        raise HTTPException(status_code=500, detail="Could not publish message") from error


@app.get("/api/sql/suggestions")
async def sql_suggestions(limit: int = 6) -> dict[str, object]:
    safe_limit = max(1, min(limit, 12))

    if not sql_tool.enabled:
        suggestions = await build_suggestions_from_catalog([], limit=safe_limit, ms_agent_client=ms_agent_client)
        return {
            "source": "disabled",
            "suggestions": suggestions,
            "tableCount": 0,
        }

    try:
        catalog = await sql_tool.get_table_catalog(max_tables=200)
        suggestions = await build_suggestions_from_catalog(catalog, limit=safe_limit, ms_agent_client=ms_agent_client)
        return {
            "source": "catalog",
            "suggestions": suggestions,
            "tableCount": len(catalog),
        }
    except Exception as error:  # noqa: BLE001
        logger.exception("Failed to build SQL suggestions: %s", error)
        suggestions = await build_suggestions_from_catalog([], limit=safe_limit, ms_agent_client=ms_agent_client)
        return {
            "source": "fallback",
            "suggestions": suggestions,
            "tableCount": 0,
        }

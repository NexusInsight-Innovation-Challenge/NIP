from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from collections.abc import AsyncIterator
from typing import Any

import websockets

from app.agent_flow import AgentPipeline
from app.agents.contracts import AgentContext, ConversationTurn
from app.agents.memory import ConversationMemory
from app.models import EnvelopeMetadata, EventType, MessageEnvelope
from app.pubsub_protocol import is_group_json_message, join_group_message
from app.pubsub_service import PubSubService

logger = logging.getLogger(__name__)


class BackendRealtimeListener:
    def __init__(
        self,
        pubsub_service: PubSubService,
        pipeline: AgentPipeline,
        memory: ConversationMemory | None = None,
    ) -> None:
        self._pubsub_service = pubsub_service
        self._pipeline = pipeline
        self._memory = memory
        self._running = False

    async def start(self) -> None:
        self._running = True
        retry = 1.0

        while self._running:
            try:
                await self._run_session()
                retry = 1.0
            except Exception as error:  # noqa: BLE001
                jitter = random.uniform(0.0, 0.5)
                wait_time = min(30.0, retry + jitter)
                logger.exception("Listener session failed: %s", error)
                await asyncio.sleep(wait_time)
                retry = min(30.0, retry * 2)

    async def stop(self) -> None:
        self._running = False

    async def _run_session(self) -> None:
        access = self._pubsub_service.negotiate_backend_listener()
        logger.info("Connecting backend listener to Web PubSub hub=%s", access.hub)

        async with websockets.connect(
            access.url,
            subprotocols=["json.webpubsub.azure.v1"],
            ping_interval=20,
            ping_timeout=20,
            max_size=1_000_000,
        ) as websocket:
            await websocket.send(json.dumps(join_group_message(access.group, ack_id=1)))
            logger.info("Backend listener joined group=%s", access.group)

            async for raw_message in websocket:
                try:
                    parsed = json.loads(raw_message)
                except json.JSONDecodeError:
                    continue

                if not is_group_json_message(parsed):
                    continue

                await self._handle_payload(parsed["data"])

    async def _handle_payload(self, payload: dict) -> None:
        try:
            envelope = MessageEnvelope.model_validate(payload)
        except Exception as error:  # noqa: BLE001
            logger.warning("Invalid envelope received: %s", error)
            return

        source = envelope.metadata.source or ""
        if source.startswith("backend.listener"):
            return

        if envelope.event_type != EventType.USER_MESSAGE:
            return

        user_message = str(envelope.payload.get("message", "")).strip()
        if not user_message:
            return

        await self._publish_status(envelope, "processing")

        # Record user turn in memory
        if self._memory:
            self._memory.add_turn(
                envelope.conversation_id,
                ConversationTurn(role="user", message=user_message),
            )

        started_at = time.perf_counter()
        context = AgentContext(
            conversation_id=envelope.conversation_id,
            correlation_id=envelope.correlation_id,
            user_message=user_message,
        )

        try:
            result = await self._pipeline.run(context)
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)

            # Record assistant turn in memory
            if self._memory:
                summary = (result.response or "")[:300]
                sql_used = result.validated_sql or result.generated_sql
                total_rows = sum(sq.row_count for sq in result.sub_queries) if result.sub_queries else len(result.query_result_rows)
                self._memory.add_turn(
                    envelope.conversation_id,
                    ConversationTurn(
                        role="assistant",
                        message=summary,
                        sql=sql_used[:200] if sql_used else None,
                        row_count=total_rows if total_rows else None,
                    ),
                )

            await self._stream_response(
                envelope,
                result.response or "",
                elapsed_ms,
                result.metadata,
                result.analysis_question,
                result.generated_sql,
                result.validated_sql,
                result.query_result_preview,
            )
            await self._publish_status(envelope, "completed")
        except Exception as error:  # noqa: BLE001
            logger.exception("Agent pipeline failed: %s", error)
            error_event = MessageEnvelope(
                event_type=EventType.ERROR,
                correlation_id=envelope.correlation_id,
                conversation_id=envelope.conversation_id,
                role="assistant",
                payload={"message": str(error)},
                metadata=EnvelopeMetadata(source="backend.listener"),
            )
            self._pubsub_service.send_json_to_group(error_event.model_dump(mode="json"))

    async def _publish_status(self, inbound: MessageEnvelope, status: str) -> None:
        event = MessageEnvelope(
            event_type=EventType.STATUS,
            correlation_id=inbound.correlation_id,
            conversation_id=inbound.conversation_id,
            role="system",
            payload={"status": status},
            metadata=EnvelopeMetadata(source="backend.listener"),
        )
        self._pubsub_service.send_json_to_group(event.model_dump(mode="json"))

    async def _stream_response(
        self,
        inbound: MessageEnvelope,
        response_text: str,
        elapsed_ms: int,
        metadata: dict[str, str | int | float | bool],
        analysis_question: str | None,
        generated_sql: str | None,
        validated_sql: str | None,
        query_result_preview: str | None,
    ) -> None:
        intent = str(metadata.get("intent", "")) or None
        route = str(metadata.get("route", "")) or None
        transparency_metadata = self._build_transparency_metadata(
            metadata,
            analysis_question,
            generated_sql,
            validated_sql,
            query_result_preview,
        )
        chunk_buffer = ""
        async for token in self._tokenize(response_text):
            chunk_buffer += token
            event = MessageEnvelope(
                event_type=EventType.ASSISTANT_DELTA,
                correlation_id=inbound.correlation_id,
                conversation_id=inbound.conversation_id,
                role="assistant",
                payload={"delta": token},
                metadata=EnvelopeMetadata(source="backend.listener", intent=intent, route=route),
            )
            self._pubsub_service.send_json_to_group(event.model_dump(mode="json"))

        complete_event = MessageEnvelope(
            event_type=EventType.ASSISTANT_COMPLETE,
            correlation_id=inbound.correlation_id,
            conversation_id=inbound.conversation_id,
            role="assistant",
            payload={
                "message": chunk_buffer,
                "transparency": transparency_metadata,
                "analysis_question": analysis_question,
                "generated_sql": generated_sql,
                "validated_sql": validated_sql,
                "result_preview": query_result_preview,
            },
            metadata=EnvelopeMetadata(
                source="backend.listener",
                processing_ms=elapsed_ms,
                intent=intent,
                route=route,
                **transparency_metadata,
            ),
        )
        self._pubsub_service.send_json_to_group(complete_event.model_dump(mode="json"))

    def _build_transparency_metadata(
        self,
        metadata: dict[str, str | int | float | bool],
        analysis_question: str | None,
        generated_sql: str | None,
        validated_sql: str | None,
        query_result_preview: str | None,
    ) -> dict[str, Any]:
        stage_timings: list[str] = []
        for key, value in metadata.items():
            if key.startswith("stage_ms.") and isinstance(value, int):
                stage_name = key.replace("stage_ms.", "")
                stage_timings.append(f"{stage_name}:{value}ms")

        stage_timing_summary = " | ".join(stage_timings)
        preview = (query_result_preview or "").strip()

        return {
            "analysis_question": analysis_question,
            "generated_sql": generated_sql,
            "validated_sql": validated_sql,
            "rows_returned": metadata.get("rows_returned"),
            "sql_retries": metadata.get("sql_retries"),
            "sql_execution_ms": metadata.get("sql_execution_ms"),
            "sql_last_resort_fallback": metadata.get("sql_last_resort_fallback"),
            "sql_last_error": metadata.get("sql_last_error"),
            "schema_source": metadata.get("schema_source"),
            "schema_tables_count": metadata.get("schema_tables_count"),
            "schema_catalog_missing": metadata.get("schema_catalog_missing"),
            "sub_query_count": metadata.get("sub_query_count"),
            "sub_queries_executed": metadata.get("sub_queries_executed"),
            "sub_queries_failed": metadata.get("sub_queries_failed"),
            "critic_validated": metadata.get("critic_validated"),
            "stage_timing": stage_timing_summary,
            "result_preview": preview[:2000] if preview else None,
        }

    async def _tokenize(self, text: str) -> AsyncIterator[str]:
        words = text.split(" ")
        for index, word in enumerate(words):
            separator = "" if index == len(words) - 1 else " "
            yield f"{word}{separator}"
            await asyncio.sleep(0.03)

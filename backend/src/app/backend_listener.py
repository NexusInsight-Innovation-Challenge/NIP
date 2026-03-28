from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import websockets

from app.agent_flow import AgentPipeline
from app.agents.contracts import AgentContext, ConversationTurn
from app.agents.memory import ConversationMemory
from app.models import EnvelopeMetadata, EventType, MessageEnvelope
from app.pubsub_protocol import is_group_json_message, join_group_message
from app.pubsub_service import PubSubService
from app.sensitivity_policy import SensitivityAssessment, SensitivityPolicy

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PendingApproval:
    inbound: MessageEnvelope
    context: AgentContext
    started_at: float
    timeout_seconds: int
    expires_at_unix: float
    expiry_task: asyncio.Task[None]


class BackendRealtimeListener:
    def __init__(
        self,
        pubsub_service: PubSubService,
        pipeline: AgentPipeline,
        sensitivity_policy: SensitivityPolicy,
        memory: ConversationMemory | None = None,
    ) -> None:
        self._pubsub_service = pubsub_service
        self._pipeline = pipeline
        self._sensitivity_policy = sensitivity_policy
        self._memory = memory
        self._running = False
        self._pending_approvals: dict[str, PendingApproval] = {}
        self._pending_lock = asyncio.Lock()

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

        if envelope.event_type == EventType.USER_MESSAGE:
            await self._handle_user_message(envelope)
            return

        if envelope.event_type == EventType.APPROVAL_RESPONSE:
            await self._handle_approval_response(envelope)
            return

    async def _handle_user_message(self, envelope: MessageEnvelope) -> None:
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
            pre_execution_context = await self._pipeline.run_until(context, "CriticAgent")

            if pre_execution_context.route == "chat_pipeline":
                await self._complete_flow(envelope, pre_execution_context, started_at)
                return

            assessment = await self._sensitivity_policy.assess(pre_execution_context)
            self._apply_assessment(pre_execution_context, assessment)

            if assessment.requires_approval:
                await self._queue_approval(envelope, pre_execution_context, started_at)
                return

            result = await self._pipeline.run_from(pre_execution_context, "CriticAgent")
            await self._complete_flow(envelope, result, started_at)
        except Exception as error:  # noqa: BLE001
            logger.exception("Agent pipeline failed: %s", error)
            self._publish_error(envelope, str(error))

    async def _handle_approval_response(self, envelope: MessageEnvelope) -> None:
        decision = envelope.payload.get("approved")
        if not isinstance(decision, bool):
            self._publish_error(
                envelope,
                "Invalid approval format. Expected approved=true|false.",
            )
            return

        async with self._pending_lock:
            pending = self._pending_approvals.pop(envelope.correlation_id, None)

        if pending is None:
            self._publish_error(
                envelope,
                "Unknown or expired approval request.",
            )
            return

        pending.expiry_task.cancel()
        await self._finalize_approval_decision(pending, envelope, approved=decision)

    async def _queue_approval(
        self,
        inbound: MessageEnvelope,
        context: AgentContext,
        started_at: float,
    ) -> None:
        timeout_seconds = self._sensitivity_policy.approval_timeout_seconds
        requested_at = datetime.now(UTC)
        expires_at = requested_at.timestamp() + timeout_seconds

        context.approval_required = True
        context.approval_status = "pending"
        context.approval_requested_at = requested_at.isoformat()
        context.approval_timeout_seconds = timeout_seconds
        context.metadata["approval_required"] = True
        context.metadata["approval_status"] = "pending"
        context.metadata["approval_requested_at"] = context.approval_requested_at
        context.metadata["approval_timeout_seconds"] = timeout_seconds

        expiry_task = asyncio.create_task(
            self._expire_approval(inbound.correlation_id, timeout_seconds)
        )
        pending = PendingApproval(
            inbound=inbound,
            context=context,
            started_at=started_at,
            timeout_seconds=timeout_seconds,
            expires_at_unix=expires_at,
            expiry_task=expiry_task,
        )

        async with self._pending_lock:
            self._pending_approvals[inbound.correlation_id] = pending

        approval_event = MessageEnvelope(
            event_type=EventType.APPROVAL_REQUIRED,
            correlation_id=inbound.correlation_id,
            conversation_id=inbound.conversation_id,
            role="system",
            payload={
                "message": "Sensitive query detected. Human approval is required before executing SQL.",
                "reason": context.approval_reason,
                "categories": context.approval_categories,
                "risk_level": context.approval_risk_level,
                "policy_version": context.metadata.get("approval_policy_version"),
                "timeout_seconds": timeout_seconds,
                "requested_at": context.approval_requested_at,
                "expires_at": datetime.fromtimestamp(expires_at, tz=UTC).isoformat(),
                "analysis_question": context.analysis_question,
                "validated_sql": context.validated_sql,
            },
            metadata=EnvelopeMetadata(
                source="backend.listener",
                intent=context.intent,
                route=context.route,
            ),
        )
        self._pubsub_service.send_json_to_group(approval_event.model_dump(mode="json"))
        await self._publish_status(
            inbound,
            "processing",
            message="Waiting for human approval for sensitive query.",
        )

    async def _expire_approval(self, correlation_id: str, timeout_seconds: int) -> None:
        try:
            await asyncio.sleep(timeout_seconds)
            async with self._pending_lock:
                pending = self._pending_approvals.pop(correlation_id, None)
            if pending is None:
                return

            pending.context.approval_status = "expired"
            pending.context.approval_decided_at = datetime.now(UTC).isoformat()
            pending.context.approval_decision_reason = "Approval timeout expired"
            pending.context.metadata["approval_status"] = "expired"
            pending.context.metadata["approval_decided_at"] = pending.context.approval_decided_at
            pending.context.metadata["approval_decision_reason"] = "timeout"

            finalized_event = MessageEnvelope(
                event_type=EventType.APPROVAL_FINALIZED,
                correlation_id=pending.inbound.correlation_id,
                conversation_id=pending.inbound.conversation_id,
                role="system",
                payload={
                    "status": "expired",
                    "approved": False,
                    "decided_at": pending.context.approval_decided_at,
                    "reason": "Approval timeout expired",
                },
                metadata=EnvelopeMetadata(
                    source="backend.listener",
                    intent=pending.context.intent,
                    route=pending.context.route,
                ),
            )
            self._pubsub_service.send_json_to_group(finalized_event.model_dump(mode="json"))
            await self._reject_sensitive_query(
                pending.inbound,
                pending.context,
                pending.started_at,
                rejection_reason="Human approval expired. The sensitive query was not executed.",
            )
        except asyncio.CancelledError:
            return

    async def _finalize_approval_decision(
        self,
        pending: PendingApproval,
        decision_envelope: MessageEnvelope,
        *,
        approved: bool,
    ) -> None:
        context = pending.context
        context.approval_status = "approved" if approved else "rejected"
        context.approval_decided_at = datetime.now(UTC).isoformat()
        context.approval_decided_by = str(
            decision_envelope.payload.get("decided_by")
            or decision_envelope.payload.get("userId")
            or "chat-user"
        )
        raw_reason = decision_envelope.payload.get("reason")
        context.approval_decision_reason = str(raw_reason).strip() if raw_reason else None
        context.metadata["approval_status"] = context.approval_status
        context.metadata["approval_decided_at"] = context.approval_decided_at
        context.metadata["approval_decided_by"] = context.approval_decided_by
        if context.approval_decision_reason:
            context.metadata["approval_decision_reason"] = context.approval_decision_reason

        finalized_event = MessageEnvelope(
            event_type=EventType.APPROVAL_FINALIZED,
            correlation_id=pending.inbound.correlation_id,
            conversation_id=pending.inbound.conversation_id,
            role="system",
            payload={
                "status": context.approval_status,
                "approved": approved,
                "decided_at": context.approval_decided_at,
                "decided_by": context.approval_decided_by,
                "reason": context.approval_decision_reason,
            },
            metadata=EnvelopeMetadata(
                source="backend.listener",
                intent=context.intent,
                route=context.route,
            ),
        )
        self._pubsub_service.send_json_to_group(finalized_event.model_dump(mode="json"))

        if approved:
            try:
                resumed = await self._pipeline.run_from(context, "CriticAgent")
                await self._complete_flow(
                    pending.inbound,
                    resumed,
                    pending.started_at,
                )
                return
            except Exception as error:  # noqa: BLE001
                logger.exception("Agent pipeline resume failed: %s", error)
                self._publish_error(pending.inbound, str(error))
                return

        await self._reject_sensitive_query(
            pending.inbound,
            context,
            pending.started_at,
            rejection_reason="The sensitive SQL execution was rejected by human approval.",
        )

    def _apply_assessment(
        self,
        context: AgentContext,
        assessment: SensitivityAssessment,
    ) -> None:
        context.approval_required = assessment.requires_approval
        context.approval_reason = assessment.reason
        context.approval_categories = assessment.categories
        context.approval_risk_level = assessment.risk_level
        context.metadata["approval_required"] = assessment.requires_approval
        context.metadata["approval_reason"] = assessment.reason
        context.metadata["approval_categories"] = ",".join(assessment.categories)
        context.metadata["approval_risk_level"] = assessment.risk_level
        context.metadata["approval_policy_version"] = assessment.policy_version

    async def _complete_flow(
        self,
        inbound: MessageEnvelope,
        result: AgentContext,
        started_at: float,
    ) -> None:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)

        if self._memory:
            summary = (result.response or "")[:300]
            sql_used = result.validated_sql or result.generated_sql
            total_rows = (
                sum(sq.row_count for sq in result.sub_queries)
                if result.sub_queries
                else len(result.query_result_rows)
            )
            self._memory.add_turn(
                inbound.conversation_id,
                ConversationTurn(
                    role="assistant",
                    message=summary,
                    sql=sql_used[:200] if sql_used else None,
                    row_count=total_rows if total_rows else None,
                ),
            )

        await self._stream_response(
            inbound,
            result.response or "",
            elapsed_ms,
            result.metadata,
            result.analysis_question,
            result.generated_sql,
            result.validated_sql,
            result.query_result_preview,
        )
        await self._publish_status(inbound, "completed")

    async def _reject_sensitive_query(
        self,
        inbound: MessageEnvelope,
        context: AgentContext,
        started_at: float,
        rejection_reason: str,
    ) -> None:
        context.response = (
            "### Execution paused for compliance\n"
            f"{rejection_reason}\n\n"
            "You can rephrase the query without PII or sensitive financial metrics "
            "or request a new approval."
        )
        await self._complete_flow(inbound, context, started_at)

    def _publish_error(self, inbound: MessageEnvelope, message: str) -> None:
        error_event = MessageEnvelope(
            event_type=EventType.ERROR,
            correlation_id=inbound.correlation_id,
            conversation_id=inbound.conversation_id,
            role="assistant",
            payload={"message": message},
            metadata=EnvelopeMetadata(source="backend.listener"),
        )
        self._pubsub_service.send_json_to_group(error_event.model_dump(mode="json"))

    async def _publish_status(
        self,
        inbound: MessageEnvelope,
        status: str,
        message: str | None = None,
    ) -> None:
        event = MessageEnvelope(
            event_type=EventType.STATUS,
            correlation_id=inbound.correlation_id,
            conversation_id=inbound.conversation_id,
            role="system",
            payload={"status": status, "message": message},
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
            "approval_required": metadata.get("approval_required"),
            "approval_status": metadata.get("approval_status"),
            "approval_reason": metadata.get("approval_reason"),
            "approval_categories": metadata.get("approval_categories"),
            "approval_risk_level": metadata.get("approval_risk_level"),
            "approval_policy_version": metadata.get("approval_policy_version"),
            "approval_requested_at": metadata.get("approval_requested_at"),
            "approval_timeout_seconds": metadata.get("approval_timeout_seconds"),
            "approval_decided_at": metadata.get("approval_decided_at"),
            "approval_decided_by": metadata.get("approval_decided_by"),
            "approval_decision_reason": metadata.get("approval_decision_reason"),
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

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass

from app.agents.contracts import AgentContext
from app.config import Settings
from app.ms_agent_client import MicrosoftAgentFrameworkClient

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SensitivityAssessment:
    requires_approval: bool
    risk_level: str
    reason: str
    categories: list[str]
    policy_version: str


class SensitivityPolicy:
    _pii_keywords = {
        "pii",
        "personal",
        "personally identifiable",
        "email",
        "correo",
        "phone",
        "telefono",
        "teléfono",
        "address",
        "direccion",
        "dirección",
        "ssn",
        "social security",
        "passport",
        "dni",
        "curp",
        "rfc",
        "birth",
        "nacimiento",
        "full name",
        "nombre completo",
        "customer name",
    }
    _financial_keywords = {
        "financial",
        "financiero",
        "revenue",
        "ingresos",
        "margin",
        "margen",
        "profit",
        "utilidad",
        "ebitda",
        "cashflow",
        "cash flow",
        "balance",
        "p&l",
        "income statement",
        "cost",
        "costos",
        "expense",
        "gasto",
        "salary",
        "salario",
        "payroll",
        "nomina",
        "nómina",
        "invoice",
        "factura",
        "bank",
        "banco",
        "tax",
        "impuesto",
    }
    _ambiguous_keywords = {
        "customer",
        "cliente",
        "employee",
        "empleado",
        "contact",
        "account",
        "cuenta",
        "payment",
        "pago",
        "transaction",
        "transaccion",
        "transacción",
    }

    def __init__(self, settings: Settings, ms_agent_client: MicrosoftAgentFrameworkClient) -> None:
        self._settings = settings
        self._ms_agent_client = ms_agent_client

    @property
    def approval_timeout_seconds(self) -> int:
        return self._settings.hitl_approval_timeout_seconds

    async def assess(self, context: AgentContext) -> SensitivityAssessment:
        text_blob = self._build_text_blob(context)
        pii_hits = self._match_keywords(text_blob, self._pii_keywords)
        financial_hits = self._match_keywords(text_blob, self._financial_keywords)
        ambiguous_hits = self._match_keywords(text_blob, self._ambiguous_keywords)

        categories: list[str] = []
        if pii_hits:
            categories.append("pii")
        if financial_hits:
            categories.append("financial")

        score = 0
        score += 3 if pii_hits else 0
        score += 3 if financial_hits else 0
        score += 1 if ambiguous_hits else 0
        score += 1 if self._looks_like_bulk_extract(context) else 0

        risk_level = "low"
        reason_parts: list[str] = []
        if pii_hits:
            reason_parts.append(f"PII keywords: {', '.join(sorted(pii_hits)[:4])}")
        if financial_hits:
            reason_parts.append(
                f"Financial keywords: {', '.join(sorted(financial_hits)[:4])}"
            )

        if score >= 3:
            risk_level = "high"
        elif score >= 2:
            risk_level = "medium"

        if risk_level == "medium" and self._settings.hitl_llm_review_enabled:
            llm_result = await self._review_with_llm(context, reason_parts)
            if llm_result is not None:
                llm_risk, llm_reason, llm_categories = llm_result
                risk_level = llm_risk
                if llm_reason:
                    reason_parts.append(llm_reason)
                for category in llm_categories:
                    if category not in categories:
                        categories.append(category)

        requires_approval = (
            self._settings.hitl_sensitive_approval_enabled and risk_level == "high"
        )

        if not reason_parts:
            reason_parts.append("No sensitive indicators detected")

        return SensitivityAssessment(
            requires_approval=requires_approval,
            risk_level=risk_level,
            reason="; ".join(reason_parts),
            categories=categories,
            policy_version=self._settings.hitl_policy_version,
        )

    def _build_text_blob(self, context: AgentContext) -> str:
        parts = [
            context.user_message or "",
            context.analysis_question or "",
            context.generated_sql or "",
            context.validated_sql or "",
            " ".join(sq.question for sq in context.sub_queries),
            " ".join((sq.validated_sql or sq.sql or "") for sq in context.sub_queries),
        ]
        return " ".join(part for part in parts if part).lower()

    def _match_keywords(self, text: str, keywords: set[str]) -> set[str]:
        matches: set[str] = set()
        for keyword in keywords:
            pattern = r"\b" + re.escape(keyword) + r"\b"
            if re.search(pattern, text):
                matches.add(keyword)
        return matches

    def _looks_like_bulk_extract(self, context: AgentContext) -> bool:
        sql = (context.validated_sql or context.generated_sql or "").lower()
        if not sql:
            return False
        has_top = bool(re.search(r"\btop\s*\(", sql))
        return "select" in sql and not has_top

    async def _review_with_llm(
        self,
        context: AgentContext,
        reason_parts: list[str],
    ) -> tuple[str, str, list[str]] | None:
        if not self._ms_agent_client.enabled:
            return None

        prompt = (
            "Classify sensitivity for SQL analytics approval workflow. "
            "Return only compact JSON: "
            '{"risk":"low|high","reason":"...","categories":["pii","financial"]}. '
            "Choose high if the query can expose personal identifiers or confidential financial metrics.\n"
            f"User message: {context.user_message}\n"
            f"Analysis question: {context.analysis_question}\n"
            f"SQL: {context.validated_sql or context.generated_sql or 'N/A'}\n"
            f"Heuristic hints: {'; '.join(reason_parts)}"
        )

        try:
            response = await asyncio.wait_for(
                self._ms_agent_client.generate(prompt),
                timeout=self._settings.hitl_llm_review_timeout_seconds,
            )
        except Exception as error:  # noqa: BLE001
            logger.warning("HITL LLM review failed, keeping heuristic decision: %s", error)
            return None

        try:
            payload = self._parse_json(response)
            risk_raw = str(payload.get("risk", "")).lower().strip()
            risk = "high" if risk_raw == "high" else "low"
            reason = str(payload.get("reason", "")).strip()
            categories_raw = payload.get("categories", [])
            categories = [
                str(item).strip().lower()
                for item in categories_raw
                if str(item).strip().lower() in {"pii", "financial"}
            ]
            return risk, reason, categories
        except Exception as error:  # noqa: BLE001
            logger.warning("HITL LLM review parsing failed, keeping heuristic decision: %s", error)
            return None

    def _parse_json(self, value: str) -> dict:
        trimmed = value.strip()
        match = re.search(r"\{.*\}", trimmed, re.DOTALL)
        if match:
            trimmed = match.group(0)
        return json.loads(trimmed)

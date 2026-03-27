from __future__ import annotations

import logging
import re

import sqlparse

from app.agents.contracts import AgentContext, AgentStep
from app.data.sql_tool import AzureSQLTool, SQLSafetyError
from app.ms_agent_client import MicrosoftAgentFrameworkClient

logger = logging.getLogger(__name__)


class CriticAgent(AgentStep):
    """Security guardrails + SQL validation + self-correction loop.

    Validates generated SQL before execution:
    1. Blocks DDL/DML (SQL injection prevention)
    2. Forces TOP/LIMIT clauses
    3. Verifies table references against catalog
    4. Runs LLM-based self-correction if validation fails
    """

    def __init__(
        self,
        sql_tool: AzureSQLTool,
        ms_agent_client: MicrosoftAgentFrameworkClient,
        max_retries: int = 2,
    ) -> None:
        self._sql_tool = sql_tool
        self._ms_agent_client = ms_agent_client
        self._max_retries = max_retries

    async def run(self, context: AgentContext) -> AgentContext:
        if context.route != "sql_pipeline":
            return context

        # Validate each sub-query
        if context.sub_queries:
            for sq in context.sub_queries:
                if not sq.sql:
                    continue
                validated = await self._validate_and_fix(
                    sq.sql, context.schema_tables, context.schema_context, sq.question,
                )
                if validated:
                    sq.validated_sql = validated
                else:
                    sq.error = sq.error or "Validation failed after retries"

            # Set main validated_sql for backward compatibility
            first_valid = next(
                (sq.validated_sql for sq in context.sub_queries if sq.validated_sql),
                None,
            )
            context.validated_sql = first_valid
        elif context.generated_sql:
            validated = await self._validate_and_fix(
                context.generated_sql,
                context.schema_tables,
                context.schema_context,
                context.analysis_question or context.user_message,
            )
            context.validated_sql = validated

        context.metadata["critic_validated"] = bool(context.validated_sql)
        return context

    async def _validate_and_fix(
        self,
        sql: str,
        catalog: list[str],
        schema_context: str | None,
        question: str,
    ) -> str | None:
        latest_sql = sql
        last_error = ""

        for attempt in range(self._max_retries + 1):
            try:
                # Check for unknown tables
                unknown = self._sql_tool.find_unknown_tables(latest_sql, catalog)
                if unknown:
                    raise RuntimeError(
                        f"Unknown table references: {', '.join(unknown)}"
                    )

                # Validate safety and inject TOP
                validated = self._sql_tool.validate_select_query(latest_sql)
                return validated

            except SQLSafetyError as error:
                logger.warning("SQL blocked by security: %s", error)
                return None

            except Exception as error:
                last_error = str(error)
                logger.warning(
                    "Critic validation attempt=%d error=%s", attempt + 1, error,
                )

                if attempt >= self._max_retries:
                    break

                # Try LLM-powered repair
                if self._ms_agent_client.enabled:
                    latest_sql = await self._repair_sql(
                        latest_sql, last_error, catalog, schema_context, question,
                    )
                    latest_sql = self._normalize_sql(latest_sql)

        logger.error("Critic: could not fix SQL after %d attempts: %s", self._max_retries + 1, last_error)
        return None

    async def _repair_sql(
        self,
        current_sql: str,
        error_message: str,
        catalog: list[str],
        schema_context: str | None,
        question: str,
    ) -> str:
        invalid_object = self._sql_tool.extract_invalid_object_name(error_message)
        suggestions = ""
        if invalid_object:
            matches = self._sql_tool.suggest_table_matches(invalid_object, catalog)
            if matches:
                suggestions = f"\nSuggested replacements: {', '.join(matches)}"

        prompt = (
            "You are fixing a SQL Server SELECT query that failed validation. "
            "Return ONLY the corrected SQL. Keep it read-only and safe. "
            "Use ONLY tables from the provided catalog — never translate or invent names.\n\n"
            f"Business question: {question}\n"
            f"Table catalog: {', '.join(catalog[:100]) or 'N/A'}\n"
            f"Schema context: {schema_context or 'N/A'}\n"
            f"Failed SQL:\n{current_sql}\n"
            f"Error: {error_message}{suggestions}\n"
        )
        repaired = await self._ms_agent_client.generate(prompt)
        return self._extract_sql(repaired) or current_sql

    def _extract_sql(self, response_text: str) -> str:
        candidate = response_text.strip()
        if not candidate:
            return ""

        fenced = re.search(r"```(?:sql)?\s*(.*?)```", candidate, re.IGNORECASE | re.DOTALL)
        if fenced:
            candidate = fenced.group(1).strip()

        start = re.search(r"\b(select|with)\b", candidate, re.IGNORECASE)
        if start:
            candidate = candidate[start.start():]

        statements = [s.strip() for s in sqlparse.split(candidate) if s.strip()]
        if statements:
            candidate = statements[0]

        return candidate.strip().rstrip(";")

    def _normalize_sql(self, sql: str) -> str:
        candidate = sql.strip().rstrip(";")
        candidate = re.sub(r"\s+", " ", candidate).strip()
        candidate = re.sub(r"\b(?:and|or)\s*$", "", candidate, flags=re.IGNORECASE).strip()
        candidate = re.sub(r"\b(?:and|or)\s+(order\s+by|group\s+by)\b", r" \1", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"\bwhere\s+(order\s+by|group\s+by)\b", r" \1", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"\bwhere\s*$", "", candidate, flags=re.IGNORECASE).strip()
        return candidate

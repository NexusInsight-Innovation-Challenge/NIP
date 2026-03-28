from __future__ import annotations

import difflib
import logging
import re

from app.agents.contracts import AgentContext, AgentStep, SubQuery
from app.data.sql_tool import AzureSQLTool

logger = logging.getLogger(__name__)

# Lazy import to avoid circular deps — resolved at runtime
SQLCoderAgent = None  # type: ignore[assignment]


def _get_sql_coder_class():
    global SQLCoderAgent
    if SQLCoderAgent is None:
        from app.agents.sql_coder_agent import SQLCoderAgent as _Cls
        SQLCoderAgent = _Cls
    return SQLCoderAgent


class SQLExecutionAgent(AgentStep):
    """Executes validated SQL queries against the database.

    Key improvement: on execution failure, the agent re-generates SQL using
    the error message as context (self-correction loop), then retries up to
    `max_retries` times per sub-query.
    """

    _business_priority_tokens = (
        "sales", "order", "customer", "product", "store", "invoice", "revenue",
    )
    _question_table_hints = {
        "ventas": ["sale", "sales", "order", "orders"],
        "sales": ["sale", "sales", "order", "orders"],
        "ingresos": ["sale", "sales", "revenue"],
        "revenue": ["sale", "sales", "revenue"],
        "clientes": ["customer", "client"],
        "customers": ["customer", "client"],
        "pedidos": ["order", "orders", "purchase"],
        "orders": ["order", "orders", "purchase"],
        "productos": ["product", "item"],
        "products": ["product", "item"],
        "compras": ["purchase", "order", "orders"],
        "purchases": ["purchase", "order", "orders"],
        "factura": ["invoice", "billing"],
        "facturación": ["invoice", "billing"],
        "invoice": ["invoice", "billing"],
    }

    def __init__(
        self,
        sql_tool: AzureSQLTool,
        sql_coder=None,
        max_retries: int = 2,
    ) -> None:
        self._sql_tool = sql_tool
        self._sql_coder = sql_coder  # SQLCoderAgent instance for retry
        self._max_retries = max_retries

    async def run(self, context: AgentContext) -> AgentContext:
        if context.route != "sql_pipeline":
            return context

        if not self._sql_tool.enabled:
            raise RuntimeError("Azure SQL connector is not configured.")

        # Execute sub-queries with retry
        if context.sub_queries:
            total_rows = 0
            total_exec_ms = 0
            total_retries = 0

            for sq in context.sub_queries:
                if not sq.validated_sql:
                    continue

                success, retries = await self._execute_with_retry(sq, context)
                total_retries += retries

                if success:
                    total_rows += sq.row_count
                    total_exec_ms += sq.execution_ms

            # Aggregate to main context for backward compatibility
            all_rows = []
            for sq in context.sub_queries:
                all_rows.extend(sq.result_rows)
            context.query_result_rows = all_rows
            context.metadata["rows_returned"] = total_rows
            context.metadata["sql_execution_ms"] = total_exec_ms
            context.metadata["sub_queries_executed"] = sum(
                1 for sq in context.sub_queries if sq.row_count > 0
            )
            context.metadata["sub_queries_failed"] = sum(
                1 for sq in context.sub_queries if sq.error
            )
            context.metadata["sql_retries"] = total_retries

        elif context.validated_sql:
            # Single query mode
            try:
                execution = await self._sql_tool.execute_select(context.validated_sql)
                context.query_result_rows = execution.rows
                context.metadata["rows_returned"] = execution.row_count
                context.metadata["sql_execution_ms"] = execution.elapsed_ms
            except Exception as error:
                # Try last-resort fallback
                fallback_sql = self._build_last_resort_sql(context)
                if fallback_sql:
                    try:
                        validated = self._sql_tool.validate_select_query(fallback_sql)
                        execution = await self._sql_tool.execute_select(validated)
                        context.validated_sql = validated
                        context.query_result_rows = execution.rows
                        context.metadata["rows_returned"] = execution.row_count
                        context.metadata["sql_execution_ms"] = execution.elapsed_ms
                        context.metadata["sql_last_resort_fallback"] = True
                        return context
                    except Exception:
                        pass
                raise RuntimeError(
                    f"SQL execution failed: {error}"
                ) from error
        else:
            raise RuntimeError("No validated SQL to execute.")

        return context

    async def _execute_with_retry(
        self,
        sq: SubQuery,
        context: AgentContext,
    ) -> tuple[bool, int]:
        """Execute a sub-query with self-correction retry on failure.

        Returns (success, retry_count).
        """
        current_sql = sq.validated_sql or sq.sql or ""
        retries = 0

        for attempt in range(self._max_retries + 1):
            try:
                execution = await self._sql_tool.execute_select(current_sql)
                sq.result_rows = execution.rows
                sq.row_count = execution.row_count
                sq.execution_ms = execution.elapsed_ms
                sq.validated_sql = current_sql
                sq.error = None  # Clear any previous error
                return True, retries
            except Exception as error:
                error_msg = str(error)
                logger.warning(
                    "Sub-query %s attempt=%d failed: %s", sq.id, attempt + 1, error_msg,
                )

                if attempt >= self._max_retries:
                    sq.error = error_msg
                    break

                # Try self-correction via SQLCoder re-generation
                if self._sql_coder is not None:
                    retries += 1
                    try:
                        schema_block = self._sql_coder.build_schema_block_public(context)
                        corrected_sql = await self._sql_coder.generate_corrected_sql(
                            question=sq.question,
                            failed_sql=current_sql,
                            error_message=error_msg,
                            schema_block=schema_block,
                        )
                        if corrected_sql:
                            # Validate the corrected SQL before retrying
                            try:
                                validated = self._sql_tool.validate_select_query(corrected_sql)
                                current_sql = validated
                            except Exception:
                                current_sql = corrected_sql  # try anyway
                            logger.info(
                                "Sub-query %s: self-corrected SQL (attempt %d)",
                                sq.id, attempt + 2,
                            )
                            continue
                    except Exception as retry_error:
                        logger.warning(
                            "Sub-query %s: self-correction failed: %s",
                            sq.id, retry_error,
                        )
                else:
                    # No SQLCoder available for retry — stop
                    sq.error = error_msg
                    break

        return False, retries

    def _build_last_resort_sql(self, context: AgentContext) -> str:
        table = self._pick_fallback_table(
            context.analysis_question or "", context.schema_tables,
        )
        if table:
            return f"SELECT COUNT(*) AS total_records FROM [{table.replace('.', '].[')}]"
        return "SELECT 1 AS ok"

    def _pick_fallback_table(self, question: str, catalog: list[str]) -> str | None:
        if not catalog:
            return None
        candidates = [t for t in catalog if not t.lower().startswith("sys.")]
        if not candidates:
            candidates = catalog
        scored = sorted(
            candidates,
            key=lambda t: self._score_table(question, t),
            reverse=True,
        )
        return scored[0]

    def _score_table(self, question: str, table_name: str) -> float:
        lowered_q = question.lower()
        bare = table_name.lower().split(".")[-1]
        score = 0.0
        for i, token in enumerate(self._business_priority_tokens):
            if token in bare:
                score += max(0.0, 3.5 - i * 0.35)
        if bare in lowered_q:
            score += 10.0
        for marker, hints in self._question_table_hints.items():
            if marker in lowered_q:
                if any(h in bare for h in hints):
                    score += 7.0
        words = [w for w in re.findall(r"\w+", lowered_q) if len(w) >= 3]
        if words and difflib.get_close_matches(bare, words, n=1, cutoff=0.7):
            score += 3.0
        return score

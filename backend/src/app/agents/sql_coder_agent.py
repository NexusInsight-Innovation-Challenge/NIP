from __future__ import annotations

import json
import logging
import re

from app.agents.contracts import AgentContext, AgentStep
from app.ms_agent_client import MicrosoftAgentFrameworkClient

logger = logging.getLogger(__name__)


class SQLCoderAgent(AgentStep):
    """Expert SQL generator — produces one query per sub-query with JOINs, CTEs, and window functions.

    Key improvement: few-shot examples are dynamically built from the actual schema
    to prevent column-name hallucination (the #1 cause of sub-query failures).
    """

    def __init__(self, ms_agent_client: MicrosoftAgentFrameworkClient) -> None:
        self._ms_agent_client = ms_agent_client

    async def run(self, context: AgentContext) -> AgentContext:
        if context.route != "sql_pipeline":
            return context

        if not self._ms_agent_client.enabled:
            raise RuntimeError(
                "Microsoft Agent Framework no está configurado para generar SQL."
            )

        # Build the schema + FK context once
        schema_block = self._build_schema_block(context)

        if context.sub_queries:
            # Generate SQL for each sub-query
            for sq in context.sub_queries:
                try:
                    sql = await self._generate_sql(sq.question, schema_block, context)
                    sq.sql = sql
                except Exception as error:
                    logger.warning("SQL generation failed for %s: %s", sq.id, error)
                    sq.error = str(error)

            # Set the first successful SQL as the main generated_sql for backward compatibility
            first_sql = next((sq.sql for sq in context.sub_queries if sq.sql), None)
            context.generated_sql = first_sql
        else:
            # Single query mode
            sql = await self._generate_sql(
                context.analysis_question or context.user_message,
                schema_block,
                context,
            )
            context.generated_sql = sql

        context.metadata["sql_generated"] = bool(context.generated_sql)
        context.metadata["sub_queries_with_sql"] = sum(
            1 for sq in context.sub_queries if sq.sql
        )
        return context

    async def generate_corrected_sql(
        self,
        question: str,
        failed_sql: str,
        error_message: str,
        schema_block: str,
    ) -> str:
        """Called by SQLExecutionAgent when a sub-query fails at execution time.

        Re-generates SQL with the error context so the model can fix column names.
        """
        prompt = (
            "You are an ELITE SQL Server BI Architect fixing a query that FAILED at execution.\n"
            "The query used wrong column or table names. You MUST fix it using ONLY columns from the schema below.\n\n"
            "=== CRITICAL RULES ===\n"
            "1. Return ONLY the corrected SQL — no comments, no explanation, no markdown.\n"
            "2. Use ONLY table and column names that appear EXACTLY in the schema below.\n"
            "3. NEVER guess or invent column names. If you're unsure, look at the schema carefully.\n"
            "4. Keep the query read-only (SELECT only).\n"
            "5. Use fully qualified table names (schema.table).\n"
            "6. Preserve the original intent of the query.\n\n"
            f"=== DATABASE SCHEMA ===\n{schema_block}\n\n"
            f"=== BUSINESS QUESTION ===\n{question}\n\n"
            f"=== FAILED SQL ===\n{failed_sql}\n\n"
            f"=== ERROR MESSAGE ===\n{error_message}\n\n"
            "Return ONLY the corrected SQL.\n"
        )
        raw_sql = await self._ms_agent_client.generate(prompt)
        return self._extract_sql(raw_sql)

    async def _generate_sql(
        self,
        question: str,
        schema_block: str,
        context: AgentContext,
    ) -> str:
        prompt = (
            "You are an ELITE SQL Server BI Architect at a top consulting firm.\n"
            "Your mission: write a SINGLE, advanced T-SQL SELECT query that fully answers the business question.\n\n"
            "=== ABSOLUTE RULES ===\n"
            "1. NO DDL, NO DML, NO comments, NO explanations — return ONLY the SQL query.\n"
            "2. NEVER use SELECT * — always specify precise columns with meaningful aliases.\n"
            "3. *** USE ONLY TABLE AND COLUMN NAMES THAT APPEAR EXACTLY IN THE SCHEMA BELOW ***\n"
            "   This is the MOST IMPORTANT rule. NEVER invent, guess, or assume column names.\n"
            "   If you need a column, find it in the schema first. If it doesn't exist, use an alternative.\n"
            "4. ALWAYS perform JOINs using the foreign key relationships provided below.\n"
            "5. Use CTEs (WITH clause) to organize complex logic into readable steps.\n"
            "6. Use Window Functions (ROW_NUMBER, SUM() OVER, RANK) for rankings and running totals.\n"
            "7. ALWAYS aggregate — calculate KPIs like Revenue, Volume, AOV, Growth%, Share%.\n"
            "8. Use fully qualified names (schema.table) when referencing tables.\n"
            "9. NEVER leave dangling AND/OR operators.\n"
            "10. For rankings, always ORDER BY the metric DESC and include rank position.\n"
            "11. When asked about products, ALWAYS JOIN to the product dimension to get readable names.\n"
            "12. When asked about customers, ALWAYS JOIN to the customer dimension for names.\n"
            "13. When asked about time/dates, use date columns from the schema — DO NOT assume 'OrderDate' or 'DateKey'.\n"
            "14. Include percentage calculations (ROUND(x * 100.0 / total, 2)) for share analysis.\n"
            "15. Before writing the query, mentally map each column you plan to use to its exact name in the schema.\n\n"
            f"=== DATABASE SCHEMA ===\n{schema_block}\n\n"
            f"=== BUSINESS QUESTION ===\n{question}\n\n"
            "Return ONLY the SQL. No markdown, no backticks, no explanation.\n"
        )

        raw_sql = await self._ms_agent_client.generate(prompt)
        return self._extract_sql(raw_sql)

    def _build_schema_block(self, context: AgentContext) -> str:
        parts: list[str] = []

        if context.schema_context:
            parts.append(context.schema_context)

        if context.fk_context:
            parts.append(f"\n=== FOREIGN KEY RELATIONSHIPS (JOIN GUIDE) ===\n{context.fk_context}")

        if context.schema_tables and not context.schema_context:
            table_catalog = ", ".join(context.schema_tables[:120])
            parts.append(f"\nTable catalog: {table_catalog}")

        return "\n".join(parts) if parts else "No schema context available"

    def build_schema_block_public(self, context: AgentContext) -> str:
        """Public accessor for _build_schema_block, used by SQLExecutionAgent for retry."""
        return self._build_schema_block(context)

    def _extract_sql(self, response_text: str) -> str:
        candidate = response_text.strip()
        if not candidate:
            return ""

        fenced_match = re.search(
            r"```(?:sql)?\s*(.*?)```",
            candidate,
            re.IGNORECASE | re.DOTALL,
        )
        if fenced_match:
            candidate = fenced_match.group(1).strip()

        start_match = re.search(r"\b(select|with)\b", candidate, re.IGNORECASE)
        if start_match:
            candidate = candidate[start_match.start():]

        return candidate.strip().rstrip(";")

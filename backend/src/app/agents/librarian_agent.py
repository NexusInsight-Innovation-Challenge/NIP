from __future__ import annotations

import logging
import time

from app.agents.contracts import AgentContext, AgentStep
from app.data.sql_tool import AzureSQLTool

logger = logging.getLogger(__name__)

_SCHEMA_CACHE_TTL_SECONDS = 300  # 5 minutes


class LibrarianAgent(AgentStep):
    """Semantic Pruning + Full Schema Context + FK Relationship Discovery."""

    def __init__(self, sql_tool: AzureSQLTool) -> None:
        self._sql_tool = sql_tool
        self._cached_tables: list[str] = []
        self._cached_rich_schema: str | None = None
        self._cached_fk_context: str | None = None
        self._cache_timestamp: float = 0.0

    async def run(self, context: AgentContext) -> AgentContext:
        if context.route != "sql_pipeline":
            return context

        if not self._sql_tool.enabled:
            context.schema_context = "Azure SQL is not configured."
            context.schema_tables = []
            context.metadata["schema_source"] = "disabled"
            return context

        cache_age = time.monotonic() - self._cache_timestamp
        use_cache = cache_age < _SCHEMA_CACHE_TTL_SECONDS and self._cached_rich_schema

        if use_cache:
            context.schema_tables = list(self._cached_tables)
            context.schema_context = self._cached_rich_schema
            context.fk_context = self._cached_fk_context
            context.metadata["schema_source"] = "cache"
            context.metadata["schema_tables_count"] = len(context.schema_tables)
            context.metadata["schema_cache_age_s"] = int(cache_age)
            return context

        # Fetch fresh schema
        try:
            context.schema_tables = await self._sql_tool.get_table_catalog(max_tables=200)
            self._cached_tables = list(context.schema_tables)
            context.metadata["schema_tables_count"] = len(context.schema_tables)
            context.metadata["schema_source"] = "information_schema"
        except Exception as error:
            logger.exception("Failed to collect table catalog: %s", error)
            if self._cached_tables:
                context.schema_tables = list(self._cached_tables)
                context.metadata["schema_source"] = "cache_fallback"
            else:
                context.schema_tables = []
                context.metadata["schema_source"] = "error"

        # Get rich schema with columns
        try:
            context.schema_context = await self._sql_tool.get_rich_schema_context(max_tables=80)
            self._cached_rich_schema = context.schema_context
        except Exception as error:
            logger.exception("Failed to get rich schema: %s", error)
            if self._cached_rich_schema:
                context.schema_context = self._cached_rich_schema
                context.metadata["schema_context_source"] = "cache_fallback"
            else:
                try:
                    context.schema_context = await self._sql_tool.get_schema_context(max_tables=60)
                    self._cached_rich_schema = context.schema_context
                except Exception as fallback_error:
                    logger.exception("Schema context fallback also failed: %s", fallback_error)
                    context.schema_context = "Could not retrieve schema metadata."

        # Get FK relationships
        try:
            context.fk_context = await self._sql_tool.get_foreign_key_context()
            self._cached_fk_context = context.fk_context
        except Exception as error:
            logger.exception("Failed to get FK context: %s", error)
            if self._cached_fk_context:
                context.fk_context = self._cached_fk_context
            else:
                context.fk_context = ""

        self._cache_timestamp = time.monotonic()
        return context

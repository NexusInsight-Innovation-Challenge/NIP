from __future__ import annotations

import asyncio
import difflib
import re
from dataclasses import dataclass
from typing import Any

import certifi
import pytds
import sqlparse

from app.config import Settings


class SQLSafetyError(RuntimeError):
    pass


@dataclass(slots=True)
class SQLExecutionResult:
    rows: list[dict[str, Any]]
    row_count: int
    elapsed_ms: int


class AzureSQLTool:
    _semantic_table_hints = {
        "ventas": ["sale", "sales", "order"],
        "clientes": ["customer", "client"],
        "productos": ["product", "item"],
        "pedidos": ["order", "purchase"],
        "facturas": ["invoice", "billing"],
    }

    _blocked_keywords = {
        "insert",
        "update",
        "delete",
        "drop",
        "alter",
        "create",
        "truncate",
        "merge",
        "grant",
        "revoke",
        "execute",
        "exec",
    }

    def __init__(self, settings: Settings) -> None:
        self._connection_string = settings.azure_sql_connection_string
        self._timeout_seconds = settings.sql_query_timeout_seconds
        self._row_limit = settings.sql_row_limit
        self._connection_options = self._parse_ado_connection_string(self._connection_string)

    @property
    def enabled(self) -> bool:
        return bool(self._connection_string)

    @property
    def row_limit(self) -> int:
        return self._row_limit

    async def get_table_catalog(self, max_tables: int = 200) -> list[str]:
        if not self.enabled:
            return []

        query = """
SELECT TOP (%(max_tables)s)
    t.TABLE_SCHEMA,
    t.TABLE_NAME
FROM INFORMATION_SCHEMA.TABLES t
WHERE t.TABLE_TYPE IN ('BASE TABLE', 'VIEW')
ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME;
"""
        try:
            rows = await self._run_query(query, {"max_tables": max_tables})
        except Exception:
            rows = []

        if not rows:
            fallback_query = """
SELECT TOP (%(max_tables)s)
    s.name AS TABLE_SCHEMA,
    o.name AS TABLE_NAME
FROM sys.objects o
JOIN sys.schemas s ON s.schema_id = o.schema_id
WHERE o.type IN ('U', 'V')
ORDER BY s.name, o.name;
"""
            rows = await self._run_query(fallback_query, {"max_tables": max_tables})

        catalog: list[str] = []
        for row in rows:
            schema_name = str(row.get("TABLE_SCHEMA", "")).strip()
            table_name = str(row.get("TABLE_NAME", "")).strip()
            if not schema_name or not table_name:
                continue
            catalog.append(f"{schema_name}.{table_name}")
        return catalog

    async def get_schema_context(self, max_tables: int = 60) -> str:
        if not self.enabled:
            return "Azure SQL connector disabled."

        query = """
SELECT TOP (%(max_tables)s)
    t.TABLE_SCHEMA,
    t.TABLE_NAME,
    c.COLUMN_NAME,
    c.DATA_TYPE
FROM INFORMATION_SCHEMA.TABLES t
JOIN INFORMATION_SCHEMA.COLUMNS c
    ON t.TABLE_SCHEMA = c.TABLE_SCHEMA
   AND t.TABLE_NAME = c.TABLE_NAME
WHERE t.TABLE_TYPE IN ('BASE TABLE', 'VIEW')
ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME, c.ORDINAL_POSITION;
"""

        rows = await self._run_query(query, {"max_tables": max_tables})
        grouped: dict[tuple[str, str], list[str]] = {}
        for row in rows:
            schema_name = str(row.get("TABLE_SCHEMA", "dbo"))
            table_name = str(row.get("TABLE_NAME", ""))
            if not table_name:
                continue
            key = (schema_name, table_name)
            grouped.setdefault(key, []).append(
                f"{row.get('COLUMN_NAME')}:{row.get('DATA_TYPE')}"
            )

        if not grouped:
            return "No tables discovered from INFORMATION_SCHEMA."

        lines = ["Available tables and columns:"]
        for (schema_name, table_name), columns in grouped.items():
            lines.append(f"- {schema_name}.{table_name} => {', '.join(columns)}")
        return "\n".join(lines)

    async def get_rich_schema_context(self, max_tables: int = 80) -> str:
        """Full DDL-like schema with columns, types, nullability, and primary keys."""
        if not self.enabled:
            return "Azure SQL connector disabled."

        column_query = """
SELECT
    c.TABLE_SCHEMA,
    c.TABLE_NAME,
    c.COLUMN_NAME,
    c.DATA_TYPE,
    c.IS_NULLABLE,
    c.CHARACTER_MAXIMUM_LENGTH,
    CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 'PK' ELSE '' END AS IS_PK
FROM INFORMATION_SCHEMA.COLUMNS c
INNER JOIN INFORMATION_SCHEMA.TABLES t
    ON c.TABLE_SCHEMA = t.TABLE_SCHEMA AND c.TABLE_NAME = t.TABLE_NAME
LEFT JOIN (
    SELECT ku.TABLE_SCHEMA, ku.TABLE_NAME, ku.COLUMN_NAME
    FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
    JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
        ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
       AND tc.TABLE_SCHEMA = ku.TABLE_SCHEMA
    WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
) pk ON c.TABLE_SCHEMA = pk.TABLE_SCHEMA
       AND c.TABLE_NAME = pk.TABLE_NAME
       AND c.COLUMN_NAME = pk.COLUMN_NAME
WHERE t.TABLE_TYPE IN ('BASE TABLE', 'VIEW')
ORDER BY c.TABLE_SCHEMA, c.TABLE_NAME, c.ORDINAL_POSITION;
"""
        try:
            rows = await self._run_query(column_query)
        except Exception:
            return await self.get_schema_context(max_tables=max_tables)

        grouped: dict[str, list[str]] = {}
        table_count = 0
        seen_tables: set[str] = set()

        for row in rows:
            schema = str(row.get("TABLE_SCHEMA", "dbo"))
            table = str(row.get("TABLE_NAME", ""))
            if not table:
                continue

            full_name = f"{schema}.{table}"
            if full_name not in seen_tables:
                seen_tables.add(full_name)
                table_count += 1
                if table_count > max_tables:
                    break

            col = row.get("COLUMN_NAME", "")
            dtype = row.get("DATA_TYPE", "")
            nullable = "NULL" if row.get("IS_NULLABLE") == "YES" else "NOT NULL"
            pk_marker = " [PK]" if row.get("IS_PK") == "PK" else ""
            max_len = row.get("CHARACTER_MAXIMUM_LENGTH")
            type_str = f"{dtype}({max_len})" if max_len and max_len > 0 else dtype

            col_def = f"  {col} {type_str} {nullable}{pk_marker}"
            grouped.setdefault(full_name, []).append(col_def)

        if not grouped:
            return "No tables discovered."

        lines = [f"=== DATABASE SCHEMA ({len(grouped)} tables) ==="]
        for table_name, columns in grouped.items():
            lines.append(f"\nTABLE {table_name} (")
            lines.extend(columns)
            lines.append(")")

        return "\n".join(lines)

    async def get_foreign_key_context(self) -> str:
        """Discover FK relationships to guide JOIN generation."""
        if not self.enabled:
            return ""

        fk_query = """
SELECT
    fk.TABLE_SCHEMA AS FK_Schema,
    fk.TABLE_NAME AS FK_Table,
    cu.COLUMN_NAME AS FK_Column,
    pk.TABLE_SCHEMA AS PK_Schema,
    pk.TABLE_NAME AS PK_Table,
    pt.COLUMN_NAME AS PK_Column
FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS fk
    ON rc.CONSTRAINT_NAME = fk.CONSTRAINT_NAME
   AND rc.CONSTRAINT_SCHEMA = fk.CONSTRAINT_SCHEMA
JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS pk
    ON rc.UNIQUE_CONSTRAINT_NAME = pk.CONSTRAINT_NAME
   AND rc.UNIQUE_CONSTRAINT_SCHEMA = pk.CONSTRAINT_SCHEMA
JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE cu
    ON rc.CONSTRAINT_NAME = cu.CONSTRAINT_NAME
   AND rc.CONSTRAINT_SCHEMA = cu.CONSTRAINT_SCHEMA
JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE pt
    ON rc.UNIQUE_CONSTRAINT_NAME = pt.CONSTRAINT_NAME
   AND rc.UNIQUE_CONSTRAINT_SCHEMA = pt.CONSTRAINT_SCHEMA
ORDER BY fk.TABLE_SCHEMA, fk.TABLE_NAME;
"""
        try:
            rows = await self._run_query(fk_query)
        except Exception:
            return ""

        if not rows:
            return "No foreign key relationships found. Use column naming conventions (e.g. ProductKey, CustomerKey) to infer JOINs."

        lines = ["FOREIGN KEY RELATIONSHIPS (use these for JOINs):"]
        for row in rows:
            fk_full = f"{row.get('FK_Schema', 'dbo')}.{row.get('FK_Table', '')}"
            fk_col = row.get('FK_Column', '')
            pk_full = f"{row.get('PK_Schema', 'dbo')}.{row.get('PK_Table', '')}"
            pk_col = row.get('PK_Column', '')
            lines.append(
                f"  {fk_full}.{fk_col} → {pk_full}.{pk_col}"
            )

        return "\n".join(lines)

    def find_unknown_tables(self, sql: str, catalog: list[str]) -> list[str]:
        if not sql or not catalog:
            return []

        known_full = {name.lower() for name in catalog}
        known_bare = {name.split(".", 1)[1].lower() for name in catalog if "." in name}

        cte_pattern = re.compile(r"(?:\bwith\b|,)\s+([a-zA-Z0-9_]+)\s+as\s*\(", re.IGNORECASE)
        for match in cte_pattern.finditer(sql):
            known_bare.add(match.group(1).lower())

        pattern = re.compile(
            r"\b(?:from|join)\s+([\[\]`\"\w\.]+)",
            re.IGNORECASE,
        )
        candidates = [match.group(1) for match in pattern.finditer(sql)]

        unknown: list[str] = []
        for item in candidates:
            normalized = item.strip().strip(",")
            normalized = normalized.replace("[", "").replace("]", "")
            normalized = normalized.replace("`", "").replace('"', "")
            lowered = normalized.lower()
            if not lowered:
                continue

            if lowered in known_full:
                continue

            bare_name = lowered.split(".")[-1]
            if bare_name in known_bare:
                continue

            unknown.append(normalized)

        deduped: list[str] = []
        for name in unknown:
            if name not in deduped:
                deduped.append(name)
        return deduped

    def extract_invalid_object_name(self, error_message: str) -> str | None:
        if not error_message:
            return None

        match = re.search(
            r"invalid object name ['\"]?([^'\"\)]+)['\"]?",
            error_message,
            re.IGNORECASE,
        )
        if not match:
            return None

        return match.group(1).strip()

    def suggest_table_matches(
        self,
        unknown_name: str,
        catalog: list[str],
        limit: int = 5,
    ) -> list[str]:
        if not unknown_name or not catalog:
            return []

        bare_catalog = {item.split(".")[-1]: item for item in catalog}
        unknown_bare = unknown_name.split(".")[-1]

        close_bare = difflib.get_close_matches(
            unknown_bare.lower(),
            [name.lower() for name in bare_catalog],
            n=limit,
            cutoff=0.4,
        )

        suggestions: list[str] = []
        for candidate in close_bare:
            for bare_name, full_name in bare_catalog.items():
                if bare_name.lower() == candidate and full_name not in suggestions:
                    suggestions.append(full_name)

        if suggestions:
            return suggestions[:limit]

        semantic_matches: list[str] = []
        hint_tokens = self._semantic_table_hints.get(unknown_bare.lower(), [])
        for full_name in catalog:
            lower_full = full_name.lower()
            if any(token in lower_full for token in hint_tokens):
                semantic_matches.append(full_name)

        if semantic_matches:
            return semantic_matches[:limit]

        close_full = difflib.get_close_matches(
            unknown_name.lower(),
            [item.lower() for item in catalog],
            n=limit,
            cutoff=0.4,
        )

        mapped: list[str] = []
        for candidate in close_full:
            for full_name in catalog:
                if full_name.lower() == candidate and full_name not in mapped:
                    mapped.append(full_name)
        return mapped[:limit]

    def validate_select_query(self, sql: str) -> str:
        candidate = self._extract_sql_candidate(sql)
        if not candidate:
            raise SQLSafetyError("Empty SQL query.")

        if self._contains_blocked_keyword(candidate):
            raise SQLSafetyError("Query contains blocked keyword.")

        statements = [stmt for stmt in sqlparse.split(candidate) if stmt.strip()]
        if len(statements) != 1:
            raise SQLSafetyError("Only a single SQL statement is allowed.")

        parsed = sqlparse.parse(candidate)
        if not parsed:
            raise SQLSafetyError("Unable to parse SQL.")

        first_statement = parsed[0]
        first_token = next(
            (token for token in first_statement.tokens if not token.is_whitespace),
            None,
        )
        if first_token is None:
            raise SQLSafetyError("Only SELECT queries are allowed.")

        first_keyword = first_token.value.strip().lower()
        if first_keyword not in {"select", "with"}:
            raise SQLSafetyError("Only SELECT queries are allowed.")

        return self._ensure_top_limit(candidate)

    def _extract_sql_candidate(self, sql: str) -> str:
        candidate = sql.strip()
        if not candidate:
            return ""

        candidate = re.sub(r"^```(?:sql)?\\s*", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"\\s*```$", "", candidate)
        candidate = candidate.strip().rstrip(";")

        start_match = re.search(r"\b(select|with)\b", candidate, flags=re.IGNORECASE)
        if not start_match:
            return candidate

        return candidate[start_match.start() :].strip().rstrip(";")

    def _contains_blocked_keyword(self, sql: str) -> bool:
        lowered = sql.lower()
        for keyword in self._blocked_keywords:
            if re.search(rf"\b{re.escape(keyword)}\b", lowered):
                return True
        return False

    async def execute_select(self, sql: str) -> SQLExecutionResult:
        if not self.enabled:
            raise SQLSafetyError("Azure SQL connector is not configured.")

        validated = self.validate_select_query(sql)
        loop = asyncio.get_running_loop()
        started = loop.time()
        rows = await self._run_query(validated)
        elapsed_ms = int((loop.time() - started) * 1000)
        return SQLExecutionResult(rows=rows, row_count=len(rows), elapsed_ms=elapsed_ms)

    def _ensure_top_limit(self, sql: str) -> str:
        select_top_pattern = re.compile(r"^\s*select\s+top\s+\(?(\d+)\)?", re.IGNORECASE)
        if select_top_pattern.search(sql):
            return sql

        # SQL Server cannot combine TOP and OFFSET in same scope
        offset_pattern = re.compile(r"\boffset\s+\d+\s+rows?\b", re.IGNORECASE)
        fetch_pattern = re.compile(r"\bfetch\s+next\s+\d+\s+rows?\b", re.IGNORECASE)
        if offset_pattern.search(sql) or fetch_pattern.search(sql):
            return sql

        select_distinct_pattern = re.compile(r"^\s*select\s+distinct\s+", re.IGNORECASE)
        if select_distinct_pattern.search(sql):
            return select_distinct_pattern.sub(
                f"SELECT DISTINCT TOP ({self._row_limit}) ",
                sql,
                count=1,
            )

        return re.sub(
            r"^\s*select\s+",
            f"SELECT TOP ({self._row_limit}) ",
            sql,
            flags=re.IGNORECASE,
            count=1,
        )

    async def _run_query(
        self,
        sql: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._run_query_sync, sql, params or {})

    def _run_query_sync(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        if not self._connection_options:
            raise SQLSafetyError("Invalid or missing AZURE_SQL_CONNECTION_STRING.")

        conn = pytds.connect(
            server=self._connection_options["server"],
            database=self._connection_options["database"],
            user=self._connection_options["user"],
            password=self._connection_options["password"],
            timeout=self._timeout_seconds,
            as_dict=True,
            cafile=certifi.where(),
            validate_host=self._connection_options["validate_host"],
            enc_login_only=False,
        )
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        finally:
            conn.close()

    def _parse_ado_connection_string(self, raw: str | None) -> dict[str, str | bool]:
        if not raw:
            return {}

        parts = [segment.strip() for segment in raw.split(";") if segment.strip()]
        kv: dict[str, str] = {}
        for part in parts:
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            kv[key.strip().lower()] = value.strip()

        server = kv.get("server", "").replace("tcp:", "")
        if "," in server:
            server = server.split(",", 1)[0].strip()

        database = kv.get("initial catalog") or kv.get("database")
        user = kv.get("user id") or kv.get("uid")
        password = kv.get("password") or kv.get("pwd")
        trust_server_certificate = (kv.get("trustservercertificate", "false").lower() == "true")
        validate_host = not trust_server_certificate

        if not all([server, database, user, password]):
            return {}

        return {
            "server": server,
            "database": database,
            "user": user,
            "password": password,
            "validate_host": validate_host,
        }

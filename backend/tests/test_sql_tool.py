import pytest

from app.data.sql_tool import AzureSQLTool, SQLSafetyError


class MinimalSettings:
    azure_sql_connection_string = (
        "Server=tcp:test.database.windows.net,1433;"
        "Initial Catalog=ContosoV2;"
        "User ID=user;"
        "Password=pass;"
    )
    sql_query_timeout_seconds = 10
    sql_row_limit = 200
    sql_max_retry_corrections = 2


def test_validate_select_query_injects_top_limit() -> None:
    tool = AzureSQLTool(MinimalSettings())

    validated = tool.validate_select_query("SELECT customer_id, total FROM sales")

    assert validated.lower().startswith("select top (200)")


def test_validate_select_query_blocks_mutation_keywords() -> None:
    tool = AzureSQLTool(MinimalSettings())

    with pytest.raises(SQLSafetyError, match="blocked keyword"):
        tool.validate_select_query("SELECT * FROM users; DROP TABLE users;")


def test_validate_select_query_allows_cte_with_clause() -> None:
    tool = AzureSQLTool(MinimalSettings())

    validated = tool.validate_select_query(
        "WITH recent_sales AS (SELECT TOP 10 * FROM sales) SELECT * FROM recent_sales"
    )

    assert validated.lower().startswith("with recent_sales")


def test_validate_select_query_extracts_fenced_sql() -> None:
    tool = AzureSQLTool(MinimalSettings())

    validated = tool.validate_select_query(
        """
        Aquí está tu consulta:
        ```sql
        SELECT customer_id FROM sales
        ```
        """
    )

    assert validated.lower().startswith("select top (200)")


def test_validate_select_query_does_not_block_created_at() -> None:
    tool = AzureSQLTool(MinimalSettings())

    validated = tool.validate_select_query("SELECT created_at FROM sales")

    assert "created_at" in validated.lower()


def test_validate_select_query_rejects_multiple_statements() -> None:
    tool = AzureSQLTool(MinimalSettings())

    with pytest.raises(SQLSafetyError, match="single SQL statement"):
        tool.validate_select_query("SELECT 1; SELECT 2;")


def test_connection_string_parser_extracts_required_fields() -> None:
    tool = AzureSQLTool(MinimalSettings())

    assert tool.enabled is True
    assert tool._connection_options["server"] == "test.database.windows.net"
    assert tool._connection_options["database"] == "ContosoV2"


def test_find_unknown_tables_detects_non_catalog_names() -> None:
    tool = AzureSQLTool(MinimalSettings())

    unknown = tool.find_unknown_tables(
        "SELECT * FROM dbo.Ventas v JOIN dbo.Clientes c ON v.cliente_id = c.id",
        ["dbo.sales", "dbo.customers"],
    )

    assert "dbo.Ventas" in unknown
    assert "dbo.Clientes" in unknown


def test_find_unknown_tables_accepts_known_table_without_schema() -> None:
    tool = AzureSQLTool(MinimalSettings())

    unknown = tool.find_unknown_tables(
        "SELECT * FROM sales s JOIN customers c ON s.customer_id = c.id",
        ["dbo.sales", "dbo.customers"],
    )

    assert unknown == []


def test_extract_invalid_object_name() -> None:
    tool = AzureSQLTool(MinimalSettings())

    object_name = tool.extract_invalid_object_name(
        '("Invalid object name \'Ventas\'.", None)'
    )

    assert object_name == "Ventas"


def test_suggest_table_matches_for_unknown_name() -> None:
    tool = AzureSQLTool(MinimalSettings())

    suggestions = tool.suggest_table_matches(
        "Ventas",
        ["dbo.SalesOrderHeader", "dbo.SalesOrderDetail", "dbo.Customers"],
    )

    assert len(suggestions) >= 1

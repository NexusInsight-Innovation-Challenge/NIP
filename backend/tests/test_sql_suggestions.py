from __future__ import annotations

import pytest
from app.data.sql_suggestions import build_suggestions_from_catalog

@pytest.mark.asyncio
async def test_build_suggestions_from_catalog_sales_model() -> None:
    catalog = [
        "Data.Sales",
        "Data.Customer",
        "Data.Product",
        "Data.Date",
    ]

    suggestions = await build_suggestions_from_catalog(catalog, limit=6)

    assert suggestions
    assert any("ventas" in suggestion.lower() for suggestion in suggestions)
    assert len(suggestions) <= 6

@pytest.mark.asyncio
async def test_build_suggestions_from_catalog_fallback() -> None:
    suggestions = await build_suggestions_from_catalog([], limit=3)

    assert len(suggestions) == 3
    assert any("reporte ejecutivo" in suggestion.lower() for suggestion in suggestions)
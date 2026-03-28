from __future__ import annotations
import json
import logging
from app.ms_agent_client import MicrosoftAgentFrameworkClient

logger = logging.getLogger(__name__)

async def build_suggestions_from_catalog(
    catalog: list[str],
    limit: int = 6,
    ms_agent_client: MicrosoftAgentFrameworkClient | None = None
) -> list[str]:
    
    if not catalog:
        return [
            "Give me an executive report with the most relevant KPIs from the database",
            "Top 10 products by sales and percentage share",
            "Monthly sales trend with drop alerts",
            "Customers with highest contribution and risk concentration",
        ][:limit]

    # Use LLM to generate suggestions based on the actual catalog
    if ms_agent_client and ms_agent_client.enabled:
        try:
            table_list = ", ".join(catalog[:100])
            prompt = (
                "You are an Expert Data Analyst. "
                "Based on the following tables from a SQL Server database, "
                f"generate {limit} high-level, business-focused analytical question suggestions "
                "that an executive would ask the database. Be creative and insightful.\n\n"
                f"Tables: {table_list}\n\n"
                "Rules:\n"
                "1. Write in English.\n"
                "2. Return ONLY a plain text JSON array with the questions (Strings), no extra explanations or backticks.\n"
                'Example: ["Question 1", "Question 2"]'
            )
            
            response = await ms_agent_client.generate(prompt)
            # Try to safely parse JSON response
            # Remove any markdown formatting just in case
            response_clean = response.replace("```json", "").replace("```", "").strip()
            suggestions = json.loads(response_clean)
            if isinstance(suggestions, list) and len(suggestions) > 0:
                # Ensure they are strings
                return [str(s) for s in suggestions][:limit]
        except Exception as e:
            logger.warning(f"Error generating AI suggestions: {e}")

    # Fallback heuristic logic
    lowered = [item.lower() for item in catalog]

    has_sales = any("sales" in item or "venta" in item for item in lowered)
    has_orders = any("order" in item or "pedido" in item for item in lowered)
    has_customer = any("customer" in item or "cliente" in item for item in lowered)
    has_product = any("product" in item or "producto" in item for item in lowered)
    has_store = any("store" in item or "tienda" in item for item in lowered)
    has_date = any("date" in item or "fecha" in item for item in lowered)

    suggestions: list[str] = []

    if has_sales and has_date:
        suggestions.append("Give me quarterly sales for 2025 with comparison vs 2024")
        suggestions.append("Summarize monthly sales trend and detect outliers")

    if has_sales and has_product:
        suggestions.append("Top 10 products by sales and percentage share")

    if has_sales and has_customer:
        suggestions.append("Top customers by sales and concentration risk")

    if has_orders and has_customer:
        suggestions.append("Analyze average ticket and frequency by customer segment")

    if has_sales and has_store:
        suggestions.append("Ranking of stores by sales and gap between top/bottom")

    if not suggestions:
        suggestions.extend(
            [
                "Give me an executive report with the most relevant KPIs from the database",
                "Which dimensions and metrics would you recommend for a management dashboard?",
                "Summarize key findings and recommended next analysis",
            ]
        )

    deduped: list[str] = []
    for suggestion in suggestions:
        if suggestion not in deduped:
            deduped.append(suggestion)

    return deduped[:limit]
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
            "Dame un reporte ejecutivo con los KPIs más relevantes de la base de datos",
            "Top 10 productos por ventas y participación porcentual",
            "Tendencia mensual de ventas con alertas de caída",
            "Clientes con mayor contribución y concentración de riesgo",
        ][:limit]

    # Use LLM to generate suggestions based on the actual catalog
    if ms_agent_client and ms_agent_client.enabled:
        try:
            table_list = ", ".join(catalog[:100])
            prompt = (
                "Eres un Analista de Datos Experto. "
                "Basado en las siguientes tablas de una base de datos SQL Server, "
                f"genera {limit} sugerencias de preguntas analíticas de alto nivel, de negocio o enfocadas a insights "
                "que un ejecutivo le preguntaría a la base de datos. Sé creativo e interesante.\n\n"
                f"Tablas: {table_list}\n\n"
                "Reglas:\n"
                "1. Escribe en español.\n"
                "2. Retorna SOLAMENTE un arreglo JSON en texto plano con las preguntas (Strings), sin explicaciones adicionales ni backticks.\n"
                'Ejemplo: ["Pregunta 1", "Pregunta 2"]'
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
        suggestions.append("Dame ventas por trimestre para 2025 con comparación vs 2024")
        suggestions.append("Resume tendencia mensual de ventas y detecta meses atípicos")

    if has_sales and has_product:
        suggestions.append("Top 10 productos por ventas y participación porcentual")

    if has_sales and has_customer:
        suggestions.append("Top clientes por ventas y riesgo de concentración")

    if has_orders and has_customer:
        suggestions.append("Analiza ticket promedio y frecuencia por segmento de cliente")

    if has_sales and has_store:
        suggestions.append("Ranking de tiendas por ventas y brecha entre top/bottom")

    if not suggestions:
        suggestions.extend(
            [
                "Dame un reporte ejecutivo con los KPIs más relevantes de la base de datos",
                "¿Qué dimensiones y métricas recomendarías para un dashboard de dirección?",
                "Resume hallazgos clave y próximos análisis recomendados",
            ]
        )

    deduped: list[str] = []
    for suggestion in suggestions:
        if suggestion not in deduped:
            deduped.append(suggestion)

    return deduped[:limit]
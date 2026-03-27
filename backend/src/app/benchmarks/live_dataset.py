from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class LiveBenchmarkCase:
    id: str
    question: str
    sql: str
    repeated: bool
    malicious: bool


def load_live_benchmark_cases() -> list[LiveBenchmarkCase]:
    return [
        LiveBenchmarkCase(
            id="live_q1",
            question="Listar tablas disponibles",
            sql=(
                "SELECT TABLE_SCHEMA, TABLE_NAME "
                "FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_TYPE = 'BASE TABLE'"
            ),
            repeated=True,
            malicious=False,
        ),
        LiveBenchmarkCase(
            id="live_q2",
            question="Contar columnas por tabla",
            sql=(
                "SELECT TABLE_SCHEMA, TABLE_NAME, COUNT(*) AS column_count "
                "FROM INFORMATION_SCHEMA.COLUMNS "
                "GROUP BY TABLE_SCHEMA, TABLE_NAME"
            ),
            repeated=True,
            malicious=False,
        ),
        LiveBenchmarkCase(
            id="live_q3",
            question="Obtener vistas registradas",
            sql=(
                "SELECT TABLE_SCHEMA, TABLE_NAME "
                "FROM INFORMATION_SCHEMA.VIEWS"
            ),
            repeated=False,
            malicious=False,
        ),
        LiveBenchmarkCase(
            id="live_q4",
            question="Intento malicioso de borrado",
            sql="DROP TABLE dbo.should_not_exist",
            repeated=False,
            malicious=True,
        ),
    ]

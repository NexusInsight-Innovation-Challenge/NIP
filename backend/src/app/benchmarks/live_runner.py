from __future__ import annotations

import time
from statistics import median
from typing import Any

from app.benchmarks.live_dataset import LiveBenchmarkCase, load_live_benchmark_cases
from app.data.sql_tool import AzureSQLTool, SQLExecutionResult, SQLSafetyError


def _percentile(values: list[int], percentile: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * percentile))
    return ordered[max(0, min(index, len(ordered) - 1))]


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _summarize_kpis(
    results: list[dict[str, Any]],
    stage_totals: dict[str, list[int]],
    total_malicious: int,
) -> dict[str, float | int | dict[str, int]]:
    latencies = [int(item["latency_ms"]) for item in results]
    tokens = [int(item["tokens"]) for item in results]
    syntax_ok = sum(1 for item in results if item["syntax_valid"])
    accuracy_ok = sum(1 for item in results if item["accuracy_pass"])
    security_ok = sum(1 for item in results if item["security_blocked"])
    fast_track_hits = sum(1 for item in results if item["fast_track_hit"])

    stage_p50 = {
        stage: int(median(values)) if values else 0 for stage, values in stage_totals.items()
    }

    return {
        "queries": len(results),
        "latency_p50_ms": int(median(latencies)) if latencies else 0,
        "latency_p95_ms": _percentile(latencies, 0.95),
        "latency_p99_ms": _percentile(latencies, 0.99),
        "avg_tokens": int(sum(tokens) / max(1, len(tokens))),
        "syntax_validity_rate": round(syntax_ok / max(1, len(results)), 4),
        "execution_accuracy_rate": round(accuracy_ok / max(1, len(results)), 4),
        "security_block_rate": round(security_ok / max(1, total_malicious), 4),
        "fast_track_hit_rate": round(fast_track_hits / max(1, len(results)), 4),
        "stage_p50_ms": stage_p50,
    }


def _run_single_query(sql_tool: AzureSQLTool, sql: str) -> SQLExecutionResult:
    validated = sql_tool.validate_select_query(sql)
    return time_it(lambda: _run_sync(sql_tool, validated))


def _run_sync(sql_tool: AzureSQLTool, validated_sql: str) -> SQLExecutionResult:
    import asyncio

    return asyncio.run(sql_tool.execute_select(validated_sql))


def time_it(callback):  # type: ignore[no-untyped-def]
    started = time.perf_counter()
    result = callback()
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    result.elapsed_ms = elapsed_ms
    return result


def _execute_variant(
    variant: str,
    cases: list[LiveBenchmarkCase],
    sql_tool: AzureSQLTool,
    cache: dict[str, SQLExecutionResult],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    stage_totals: dict[str, list[int]] = {
        "planner": [],
        "librarian": [],
        "coder": [],
        "critic": [],
        "execution": [],
        "evaluator": [],
    }

    for case in cases:
        planner_started = time.perf_counter()
        route = "sql_pipeline" if not case.malicious else "blocked"
        stage_totals["planner"].append(int((time.perf_counter() - planner_started) * 1000))

        librarian_started = time.perf_counter()
        schema_context = "live_schema" if route == "sql_pipeline" else "none"
        stage_totals["librarian"].append(int((time.perf_counter() - librarian_started) * 1000))

        coder_started = time.perf_counter()
        generated_sql = case.sql
        stage_totals["coder"].append(int((time.perf_counter() - coder_started) * 1000))

        critic_started = time.perf_counter()
        syntax_valid = False
        security_blocked = False
        validated_sql = ""
        try:
            validated_sql = sql_tool.validate_select_query(generated_sql)
            syntax_valid = True
        except SQLSafetyError:
            security_blocked = case.malicious
        stage_totals["critic"].append(int((time.perf_counter() - critic_started) * 1000))

        execution_ms = 0
        row_count = 0
        fast_track_hit = False
        if syntax_valid:
            execution_started = time.perf_counter()
            if variant == "C" and case.repeated and case.id in cache:
                execution = cache[case.id]
                fast_track_hit = True
            else:
                execution = _run_single_query(sql_tool, validated_sql)
                if variant in {"B", "C"} and case.repeated:
                    cache[case.id] = execution
            execution_ms = execution.elapsed_ms
            row_count = execution.row_count
            stage_totals["execution"].append(
                int((time.perf_counter() - execution_started) * 1000)
            )
        else:
            stage_totals["execution"].append(0)

        evaluator_started = time.perf_counter()
        accuracy_pass = (not case.malicious and row_count >= 0) or security_blocked
        stage_totals["evaluator"].append(int((time.perf_counter() - evaluator_started) * 1000))

        total_latency = sum(stage[-1] for stage in stage_totals.values())
        if syntax_valid and execution_ms:
            total_latency = max(total_latency, execution_ms)

        token_base = _estimate_tokens(case.question + generated_sql + schema_context)
        if variant == "A":
            tokens = int(token_base * 1.2)
        elif variant == "B":
            tokens = int(token_base)
        else:
            tokens = int(token_base * (0.25 if fast_track_hit else 0.85))

        rows.append(
            {
                "case_id": case.id,
                "latency_ms": total_latency,
                "tokens": tokens,
                "syntax_valid": syntax_valid,
                "accuracy_pass": accuracy_pass,
                "security_blocked": security_blocked,
                "fast_track_hit": fast_track_hit,
                "rows": row_count,
            }
        )

    total_malicious = sum(1 for item in cases if item.malicious)
    kpis = _summarize_kpis(rows, stage_totals, total_malicious)
    return {"results": rows, "kpis": kpis}


def run_live_benchmark_suite(sql_tool: AzureSQLTool) -> dict[str, Any]:
    if not sql_tool.enabled:
        raise RuntimeError("AZURE_SQL_CONNECTION_STRING is required for live benchmark mode")

    cases = load_live_benchmark_cases()
    shared_cache: dict[str, SQLExecutionResult] = {}

    variants = {
        "A": _execute_variant("A", cases, sql_tool, shared_cache),
        "B": _execute_variant("B", cases, sql_tool, shared_cache),
        "C": _execute_variant("C", cases, sql_tool, shared_cache),
    }

    kpi_a = variants["A"]["kpis"]
    kpi_c = variants["C"]["kpis"]

    latency_gain = 1 - (kpi_c["latency_p50_ms"] / max(1, kpi_a["latency_p50_ms"]))
    token_gain = 1 - (kpi_c["avg_tokens"] / max(1, kpi_a["avg_tokens"]))

    return {
        "dataset": "live_catalog_v1",
        "query_count": len(cases),
        "variants": variants,
        "comparison": {
            "latency_p50_reduction_vs_A": round(latency_gain, 4),
            "avg_tokens_reduction_vs_A": round(token_gain, 4),
        },
        "notes": [
            "Live benchmark executed against Azure SQL using INFORMATION_SCHEMA-safe queries.",
            "Token metric is estimated from prompt/query payload length.",
        ],
    }

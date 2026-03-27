from __future__ import annotations

from dataclasses import asdict
from statistics import median

from app.benchmarks.contracts import BenchmarkCase, QueryRunResult
from app.benchmarks.dataset import load_synthetic_benchmark_cases


def _percentile(values: list[int], percentile: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * percentile))
    return ordered[max(0, min(index, len(ordered) - 1))]


def _simulate_case(variant: str, case: BenchmarkCase) -> QueryRunResult:
    complexity = case.complexity

    if variant == "A":
        latency = 1800 + (complexity * 320)
        tokens = 1400 + (complexity * 180)
        syntax_valid = not case.malicious and complexity <= 4
        accuracy_pass = not case.malicious and complexity <= 3
        security_blocked = case.malicious and case.id == "q7"
        fast_track = False
    elif variant == "B":
        latency = 1300 + (complexity * 240)
        tokens = 1100 + (complexity * 130)
        syntax_valid = not case.malicious
        accuracy_pass = not case.malicious and complexity <= 4
        security_blocked = case.malicious
        fast_track = False
    elif variant == "C":
        if case.repeated and not case.malicious:
            latency = 280 + (complexity * 40)
            tokens = 180 + (complexity * 30)
            fast_track = True
        else:
            latency = 1050 + (complexity * 210)
            tokens = 900 + (complexity * 120)
            fast_track = False

        syntax_valid = not case.malicious
        accuracy_pass = not case.malicious and complexity <= 5
        security_blocked = case.malicious
    else:
        raise ValueError(f"Unknown variant: {variant}")

    return QueryRunResult(
        case_id=case.id,
        latency_ms=latency,
        tokens=tokens,
        syntax_valid=syntax_valid,
        accuracy_pass=accuracy_pass,
        security_blocked=security_blocked,
        fast_track_hit=fast_track,
    )


def _aggregate(results: list[QueryRunResult], total_malicious: int) -> dict[str, float | int]:
    latencies = [item.latency_ms for item in results]
    tokens = [item.tokens for item in results]

    syntax_ok = sum(1 for item in results if item.syntax_valid)
    accuracy_ok = sum(1 for item in results if item.accuracy_pass)
    security_ok = sum(1 for item in results if item.security_blocked)
    fast_track_hits = sum(1 for item in results if item.fast_track_hit)

    return {
        "queries": len(results),
        "latency_p50_ms": int(median(latencies)),
        "latency_p95_ms": _percentile(latencies, 0.95),
        "latency_p99_ms": _percentile(latencies, 0.99),
        "avg_tokens": int(sum(tokens) / max(1, len(tokens))),
        "syntax_validity_rate": round(syntax_ok / max(1, len(results)), 4),
        "execution_accuracy_rate": round(accuracy_ok / max(1, len(results)), 4),
        "security_block_rate": round(security_ok / max(1, total_malicious), 4),
        "fast_track_hit_rate": round(fast_track_hits / max(1, len(results)), 4),
    }


def run_benchmark_suite() -> dict[str, object]:
    cases = load_synthetic_benchmark_cases()
    total_malicious = sum(1 for case in cases if case.malicious)

    variants: dict[str, dict[str, object]] = {}
    for variant in ["A", "B", "C"]:
        runs = [_simulate_case(variant, case) for case in cases]
        variants[variant] = {
            "results": [asdict(run) for run in runs],
            "kpis": _aggregate(runs, total_malicious),
        }

    baseline = variants["A"]["kpis"]
    c_kpis = variants["C"]["kpis"]

    latency_gain = 1 - (c_kpis["latency_p50_ms"] / baseline["latency_p50_ms"])
    token_gain = 1 - (c_kpis["avg_tokens"] / baseline["avg_tokens"])

    return {
        "dataset": "synthetic_v1",
        "query_count": len(cases),
        "variants": variants,
        "comparison": {
            "latency_p50_reduction_vs_A": round(latency_gain, 4),
            "avg_tokens_reduction_vs_A": round(token_gain, 4),
        },
        "notes": [
            "Synthetic benchmark for reproducible baseline during hackathon build phase.",
            "Replace simulator with live Azure SQL + agent telemetry in Phase 3.",
        ],
    }

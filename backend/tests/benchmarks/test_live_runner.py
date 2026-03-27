from app.benchmarks.live_dataset import load_live_benchmark_cases
from app.benchmarks.live_runner import _summarize_kpis


def test_live_dataset_includes_malicious_case() -> None:
    cases = load_live_benchmark_cases()

    assert any(case.malicious for case in cases)


def test_stage_metrics_aggregation() -> None:
    rows = [
        {
            "case_id": "1",
            "latency_ms": 120,
            "tokens": 200,
            "syntax_valid": True,
            "accuracy_pass": True,
            "security_blocked": False,
            "fast_track_hit": False,
        },
        {
            "case_id": "2",
            "latency_ms": 80,
            "tokens": 100,
            "syntax_valid": True,
            "accuracy_pass": True,
            "security_blocked": True,
            "fast_track_hit": True,
        },
    ]
    stages = {
        "planner": [1, 1],
        "librarian": [2, 2],
        "coder": [1, 1],
        "critic": [1, 1],
        "execution": [110, 70],
        "evaluator": [1, 1],
    }

    kpis = _summarize_kpis(rows, stages, total_malicious=1)

    assert kpis["latency_p50_ms"] == 100
    assert kpis["stage_p50_ms"]["execution"] == 90
    assert kpis["security_block_rate"] == 1.0

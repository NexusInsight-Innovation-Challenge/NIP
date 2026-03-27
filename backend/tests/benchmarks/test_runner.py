from app.benchmarks.runner import run_benchmark_suite


def test_benchmark_suite_returns_three_variants() -> None:
    report = run_benchmark_suite()

    assert report["dataset"] == "synthetic_v1"
    assert set(report["variants"].keys()) == {"A", "B", "C"}


def test_variant_c_beats_variant_a_on_latency_and_tokens() -> None:
    report = run_benchmark_suite()

    kpi_a = report["variants"]["A"]["kpis"]
    kpi_c = report["variants"]["C"]["kpis"]

    assert kpi_c["latency_p50_ms"] < kpi_a["latency_p50_ms"]
    assert kpi_c["avg_tokens"] < kpi_a["avg_tokens"]


def test_variant_c_blocks_all_malicious_queries() -> None:
    report = run_benchmark_suite()

    kpi_c = report["variants"]["C"]["kpis"]
    assert kpi_c["security_block_rate"] == 1.0

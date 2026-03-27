from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.benchmarks.live_runner import run_live_benchmark_suite
from app.benchmarks.runner import run_benchmark_suite
from app.config import get_settings
from app.data.sql_tool import AzureSQLTool


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SQLAgentX benchmark suite")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["synthetic", "live"],
        default="synthetic",
        help="Benchmark mode",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="reports/benchmark_results.json",
        help="Output JSON file path",
    )
    args = parser.parse_args()

    try:
        if args.mode == "live":
            settings = get_settings()
            report = run_live_benchmark_suite(AzureSQLTool(settings))
        else:
            report = run_benchmark_suite()
    except RuntimeError as error:
        print(f"Benchmark failed: {error}")
        sys.exit(2)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    comparison = report["comparison"]
    print("Benchmark completed")
    print(f"- Mode: {args.mode}")
    print(f"- Dataset: {report['dataset']}")
    print(f"- Queries: {report['query_count']}")
    print(f"- P50 latency reduction vs A: {comparison['latency_p50_reduction_vs_A']:.2%}")
    print(f"- Avg tokens reduction vs A: {comparison['avg_tokens_reduction_vs_A']:.2%}")
    print(f"- Report: {output_path}")


if __name__ == "__main__":
    main()

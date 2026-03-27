from __future__ import annotations

import argparse
import json
from pathlib import Path


def _format_percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _build_stage_section(report: dict) -> list[str]:
    stage_lines: list[str] = []
    variants = report.get("variants", {})
    has_stage_metrics = any(
        isinstance(payload.get("kpis", {}).get("stage_p50_ms"), dict)
        for payload in variants.values()
    )
    if not has_stage_metrics:
        return stage_lines

    stage_lines.extend(
        [
            "## Stage Telemetry (P50 ms)",
            "",
            "| Variant | Planner | Librarian | Coder | Critic | Execution | Evaluator |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for variant, payload in variants.items():
        stages = payload.get("kpis", {}).get("stage_p50_ms", {})
        stage_lines.append(
            "| "
            + " | ".join(
                [
                    str(variant),
                    str(stages.get("planner", 0)),
                    str(stages.get("librarian", 0)),
                    str(stages.get("coder", 0)),
                    str(stages.get("critic", 0)),
                    str(stages.get("execution", 0)),
                    str(stages.get("evaluator", 0)),
                ]
            )
            + " |"
        )

    stage_lines.append("")
    return stage_lines


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate markdown report from benchmark JSON")
    parser.add_argument(
        "--input",
        type=str,
        default="reports/benchmark_results.json",
        help="Input JSON benchmark file",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="reports/benchmark_report.md",
        help="Output markdown file",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Benchmark file not found: {input_path}")

    report = json.loads(input_path.read_text(encoding="utf-8"))

    rows = []
    for variant, payload in report["variants"].items():
        kpis = payload["kpis"]
        rows.append(
            "| "
            + " | ".join(
                [
                    variant,
                    str(kpis["latency_p50_ms"]),
                    str(kpis["latency_p95_ms"]),
                    str(kpis["avg_tokens"]),
                    _format_percent(float(kpis["syntax_validity_rate"])),
                    _format_percent(float(kpis["execution_accuracy_rate"])),
                    _format_percent(float(kpis["security_block_rate"])),
                    _format_percent(float(kpis["fast_track_hit_rate"])),
                ]
            )
            + " |"
        )

    comparison = report["comparison"]
    stage_section = _build_stage_section(report)
    markdown = "\n".join(
        [
            "# SQLAgentX Benchmark Report",
            "",
            f"- Dataset: **{report['dataset']}**",
            f"- Queries: **{report['query_count']}**",
            "",
            "## KPI Table",
            "",
            "| Variant | P50 Latency (ms) | P95 Latency (ms) | Avg Tokens "
            "| Syntax Validity | Execution Accuracy "
            "| Security Block Rate | Fast-Track Hit Rate |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
            *rows,
            "",
            *stage_section,
            "## Comparison vs Baseline A",
            "",
            "- P50 latency reduction (C vs A): "
            f"**{_format_percent(float(comparison['latency_p50_reduction_vs_A']))}**",
            "- Avg tokens reduction (C vs A): "
            f"**{_format_percent(float(comparison['avg_tokens_reduction_vs_A']))}**",
            "",
            "## Notes",
            "",
            *[f"- {note}" for note in report.get("notes", [])],
            "",
        ]
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    print(f"Markdown report generated: {output_path}")


if __name__ == "__main__":
    main()

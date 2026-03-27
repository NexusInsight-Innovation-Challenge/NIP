# SQLAgentX Benchmark Report

- Dataset: **live_catalog_v1**
- Queries: **4**

## KPI Table

| Variant | P50 Latency (ms) | P95 Latency (ms) | Avg Tokens | Syntax Validity | Execution Accuracy | Security Block Rate | Fast-Track Hit Rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 503 | 609 | 32 | 75.0% | 100.0% | 100.0% | 0.0% |
| B | 508 | 531 | 27 | 75.0% | 100.0% | 100.0% | 0.0% |
| C | 500 | 528 | 12 | 75.0% | 100.0% | 100.0% | 50.0% |

## Stage Telemetry (P50 ms)

| Variant | Planner | Librarian | Coder | Critic | Execution | Evaluator |
|---|---:|---:|---:|---:|---:|---:|
| A | 0 | 0 | 0 | 0 | 502 | 0 |
| B | 0 | 0 | 0 | 1 | 507 | 0 |
| C | 0 | 0 | 0 | 0 | 0 | 0 |

## Comparison vs Baseline A

- P50 latency reduction (C vs A): **0.6%**
- Avg tokens reduction (C vs A): **62.5%**

## Notes

- Live benchmark executed against Azure SQL using INFORMATION_SCHEMA-safe queries.
- Token metric is estimated from prompt/query payload length.

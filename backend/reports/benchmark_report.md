# SQLAgentX Benchmark Report

- Dataset: **synthetic_v1**
- Queries: **8**

## KPI Table

| Variant | P50 Latency (ms) | P95 Latency (ms) | Avg Tokens | Syntax Validity | Execution Accuracy | Security Block Rate | Fast-Track Hit Rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 2760 | 3400 | 1940 | 62.5% | 37.5% | 50.0% | 0.0% |
| B | 2020 | 2500 | 1490 | 75.0% | 62.5% | 100.0% | 0.0% |
| C | 1365 | 2100 | 888 | 75.0% | 75.0% | 100.0% | 37.5% |

## Comparison vs Baseline A

- P50 latency reduction (C vs A): **50.5%**
- Avg tokens reduction (C vs A): **54.2%**

## Notes

- Synthetic benchmark for reproducible baseline during hackathon build phase.
- Replace simulator with live Azure SQL + agent telemetry in Phase 3.

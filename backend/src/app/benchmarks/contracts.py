from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class BenchmarkCase:
    id: str
    question: str
    complexity: int
    repeated: bool
    malicious: bool


@dataclass(slots=True)
class QueryRunResult:
    case_id: str
    latency_ms: int
    tokens: int
    syntax_valid: bool
    accuracy_pass: bool
    security_blocked: bool
    fast_track_hit: bool

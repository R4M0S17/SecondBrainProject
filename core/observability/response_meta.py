"""Module A6 — Observability.

Metadata attached to every /query response and a MetricsCollector that
aggregates per-query stats for the /status endpoint.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class SourceRef:
    path: str
    chunk_index: int
    score: float


@dataclass
class ToolCallRecord:
    name: str
    args_summary: str
    result_summary: str
    latency_ms: float
    approved: bool


@dataclass
class MemoryRef:
    id: str
    summary_snippet: str
    relevance_score: float


@dataclass
class ResponseMetadata:
    sources_used: list[SourceRef] = field(default_factory=list)
    tools_called: list[ToolCallRecord] = field(default_factory=list)
    memory_retrieved: list[MemoryRef] = field(default_factory=list)
    inference_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    iterations: int = 1
    model_used: str = ""
    provider_used: str = ""
    warnings: list[str] = field(default_factory=list)
    pipeline_stages_ms: dict[str, float] = field(default_factory=dict)
    # Set when the runtime pauses, waiting for user approval of a tool call.
    pending_tool: dict | None = None


@dataclass
class SystemStats:
    queries_total: int
    avg_latency_ms: float
    p95_latency_ms: float
    tool_call_count: int
    memory_hits: int
    provider_fallbacks: int
    active_agent: str


class MetricsCollector:
    """Accumulates per-query ResponseMetadata and computes aggregate stats."""

    def __init__(self) -> None:
        self._latencies: list[float] = []
        self._tool_call_count: int = 0
        self._memory_hits: int = 0
        self._provider_fallbacks: int = 0
        self._active_agent: str = ""

    def record_query(self, meta: ResponseMetadata) -> None:
        self._latencies.append(meta.total_latency_ms)
        self._tool_call_count += len(meta.tools_called)
        self._memory_hits += len(meta.memory_retrieved)
        if "provider_fallback" in meta.warnings:
            self._provider_fallbacks += 1

    def set_active_agent(self, agent_id: str) -> None:
        self._active_agent = agent_id

    def get_stats(self) -> SystemStats:
        n = len(self._latencies)
        avg = sum(self._latencies) / n if n else 0.0
        p95 = self._percentile(self._latencies, 95) if n else 0.0
        return SystemStats(
            queries_total=n,
            avg_latency_ms=round(avg, 2),
            p95_latency_ms=round(p95, 2),
            tool_call_count=self._tool_call_count,
            memory_hits=self._memory_hits,
            provider_fallbacks=self._provider_fallbacks,
            active_agent=self._active_agent,
        )

    @staticmethod
    def _percentile(data: list[float], pct: int) -> float:
        sorted_data = sorted(data)
        n = len(sorted_data)
        if n == 1:
            return sorted_data[0]
        index = (pct / 100) * (n - 1)
        lower = math.floor(index)
        upper = math.ceil(index)
        if lower == upper:
            return sorted_data[lower]
        frac = index - lower
        return sorted_data[lower] * (1 - frac) + sorted_data[upper] * frac

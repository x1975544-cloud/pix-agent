"""Aggregate benchmark metrics from real run records."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class BenchmarkMetrics:
    total: int = 0
    passed: int = 0
    failed: int = 0
    total_latency: float = 0.0
    total_tool_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    @property
    def success_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    @property
    def average_latency(self) -> float:
        return self.total_latency / self.total if self.total else 0.0

    @property
    def average_tool_calls(self) -> float:
        return self.total_tool_calls / self.total if self.total else 0.0

    @property
    def average_input_tokens(self) -> float:
        return self.total_input_tokens / self.total if self.total else 0.0

    @property
    def average_output_tokens(self) -> float:
        return self.total_output_tokens / self.total if self.total else 0.0

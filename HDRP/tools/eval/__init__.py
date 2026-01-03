"""
Evaluation and benchmarking utilities for HDRP.

This package contains:
- A baseline ReAct-style agent for comparison against HDRP.
- Test query suite with queries across complexity levels.
- Comprehensive metrics collection system.
- Comparison runner for HDRP vs ReAct evaluation.
- Results formatting with Rich console output.
- CLI entrypoint (`compare.py`) to run HDRP vs ReAct experiments.
"""

from .react_agent import ReActAgent, ReActStep, ReActRunResult
from .test_queries import TestQuery, QueryComplexity, ALL_QUERIES
from .metrics import (
    MetricsCollector,
    SystemMetrics,
    ComparisonResult,
    AggregateComparison,
)
from .results_formatter import ResultsFormatter
from .compare import ComparisonRunner

__all__ = [
    "ReActAgent",
    "ReActStep",
    "ReActRunResult",
    "TestQuery",
    "QueryComplexity",
    "ALL_QUERIES",
    "MetricsCollector",
    "SystemMetrics",
    "ComparisonResult",
    "AggregateComparison",
    "ResultsFormatter",
    "ComparisonRunner",
]



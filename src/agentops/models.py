"""
Data models for Agent Regression testing.

This module defines the data structures used throughout the agent regression system.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TestCase:
    """Represents a single agent regression test case."""
    
    case_id: str
    name: str
    input_prompt: str
    expected_output: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class TestResult:
    """Represents the result of a test case execution via llmops."""
    
    case_id: str
    actual_output: str
    passed: bool
    score: float
    execution_time: float
    timestamp: datetime
    error: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    
    # llmops integration metrics
    request_id: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    cache_hit: bool = False
    
    def __post_init__(self):
        if self.metrics is None:
            self.metrics = {}
    
    @property
    def cost_efficiency(self) -> float:
        """Calculate cost per token (lower is better)."""
        if self.total_tokens == 0:
            return 0.0
        return self.cost_usd / self.total_tokens * 1000  # per 1000 tokens


@dataclass
class RegressionReport:
    """Represents a complete regression test report with llmops metrics."""
    
    run_id: str
    timestamp: datetime
    total_cases: int
    passed_cases: int
    failed_cases: int
    average_score: float
    results: List[TestResult]
    metadata: Optional[Dict[str, Any]] = None
    
    # llmops aggregated metrics
    total_cost_usd: float = 0.0
    average_cost_per_test: float = 0.0
    total_tokens: int = 0
    average_latency_ms: float = 0.0
    cache_hit_count: int = 0
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        
        # Compute llmops metrics from results
        if self.results:
            self.total_cost_usd = sum(r.cost_usd for r in self.results)
            self.average_cost_per_test = self.total_cost_usd / len(self.results)
            self.total_tokens = sum(r.total_tokens for r in self.results)
            self.average_latency_ms = sum(r.latency_ms for r in self.results) / len(self.results)
            self.cache_hit_count = sum(1 for r in self.results if r.cache_hit)
    
    @property
    def pass_rate(self) -> float:
        """Calculate the pass rate percentage."""
        if self.total_cases == 0:
            return 0.0
        return (self.passed_cases / self.total_cases) * 100
    
    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate for llmops queries."""
        if not self.results:
            return 0.0
        return (self.cache_hit_count / len(self.results)) * 100

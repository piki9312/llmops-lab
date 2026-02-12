"""
Data models for Agent Regression testing.

This module defines the data structures used throughout the agent regression system.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


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
    failure_type: Optional[str] = None
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


class AgentRunRecord(BaseModel):
    """Persistent record of a single test case execution with evaluation results.

    Stored as JSONL in runs/agentreg/YYYYMMDD.jsonl for historical analysis.
    """

    # Required fields
    timestamp: datetime = Field(..., description="UTC timezone-aware timestamp")
    run_id: str = Field(..., description="UUID4 for this regression run")
    case_id: str = Field(..., description="Test case identifier")
    severity: str = Field(..., description="S1 (critical) or S2 (high)")
    category: str = Field(..., description="Test category (api, factual, etc)")
    passed: bool = Field(..., description="Whether test passed evaluation")
    failure_type: Optional[str] = Field(None, description="bad_json, quality_fail, timeout, etc")
    latency_ms: float = Field(..., description="LLM execution latency in milliseconds")
    reasons: List[str] = Field(
        default_factory=list, description="Failure reasons or validation notes"
    )

    # Optional fields
    gateway_request_id: Optional[str] = Field(None, description="llmops gateway request ID")
    provider: Optional[str] = Field(None, description="LLM provider (mock, openai)")
    model: Optional[str] = Field(None, description="Model name")
    prompt_version: Optional[str] = Field(None, description="Prompt template version")
    token_usage: Optional[Dict[str, int]] = Field(None, description="{prompt, completion, total}")
    output_json: Optional[Dict[str, Any]] = Field(
        None, description="Parsed JSON output for S1 cases"
    )
    cost_usd: Optional[float] = Field(None, description="Estimated cost in USD")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2026-02-01T10:30:00Z",
                "run_id": "550e8400-e29b-41d4-a716-446655440000",
                "case_id": "TC005",
                "severity": "S1",
                "category": "api",
                "passed": False,
                "failure_type": "quality_fail",
                "latency_ms": 145.3,
                "reasons": ["Missing required keys: merchant_id"],
                "gateway_request_id": "abc123",
                "provider": "mock",
                "model": "gpt-4-mock",
                "token_usage": {"prompt": 10, "completion": 20, "total": 30},
                "cost_usd": 0.0012,
            }
        }
    )

    @classmethod
    def from_test_result(
        cls, result: TestResult, run_id: str, test_case: TestCase
    ) -> "AgentRunRecord":
        """Convert TestResult to persistent AgentRunRecord."""
        import json

        severity = (result.metrics or {}).get("severity", "S2")
        category = (result.metrics or {}).get("category", "general")

        # Build reasons list from error
        reasons = []
        if result.error:
            reasons.append(result.error)

        # Parse output_json for S1 cases
        output_json = None
        if severity == "S1" and result.actual_output:
            try:
                output_json = json.loads(result.actual_output)
            except (json.JSONDecodeError, ValueError):
                pass

        # Ensure timestamp is UTC aware
        timestamp = result.timestamp
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        return cls(
            timestamp=timestamp,
            run_id=run_id,
            case_id=result.case_id,
            severity=severity,
            category=category,
            passed=result.passed,
            failure_type=result.failure_type,
            latency_ms=result.latency_ms,
            reasons=reasons,
            gateway_request_id=result.request_id,
            provider=result.provider,
            model=result.model,
            token_usage=(
                {
                    "prompt": result.prompt_tokens,
                    "completion": result.completion_tokens,
                    "total": result.total_tokens,
                }
                if result.total_tokens > 0
                else None
            ),
            output_json=output_json,
            cost_usd=result.cost_usd if result.cost_usd > 0 else None,
        )

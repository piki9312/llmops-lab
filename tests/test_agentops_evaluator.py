"""
Tests for agentops.evaluator module.
"""

import pytest
from datetime import datetime

from src.agentops.evaluator import Evaluator
from src.agentops.models import TestResult, RegressionReport


def test_calculate_accuracy():
    """Test accuracy calculation."""
    results = [
        TestResult(
            case_id="TC1",
            actual_output="output",
            passed=True,
            score=1.0,
            execution_time=0.1,
            timestamp=datetime.now()
        ),
        TestResult(
            case_id="TC2",
            actual_output="output",
            passed=False,
            score=0.0,
            execution_time=0.1,
            timestamp=datetime.now()
        )
    ]
    
    accuracy = Evaluator.calculate_accuracy(results)
    assert accuracy == 0.5


def test_generate_summary():
    """Test summary generation with operational metrics."""
    result1 = TestResult(
        case_id="TC1",
        actual_output="output",
        passed=True,
        score=1.0,
        execution_time=0.1,
        timestamp=datetime.now(),
        request_id="req-1",
        provider="mock",
        model="mock-model",
        latency_ms=100.0,
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        cost_usd=0.01,
        cache_hit=False
    )
    
    result2 = TestResult(
        case_id="TC2",
        actual_output="output",
        passed=False,
        score=0.0,
        execution_time=0.1,
        timestamp=datetime.now(),
        request_id="req-2",
        provider="mock",
        model="mock-model",
        latency_ms=150.0,
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        cost_usd=0.01,
        cache_hit=False
    )
    
    report = RegressionReport(
        run_id="test-run",
        timestamp=datetime.now(),
        total_cases=2,
        passed_cases=1,
        failed_cases=1,
        average_score=0.5,
        results=[result1, result2]
    )
    
    summary = Evaluator.generate_summary(report)
    
    assert summary["run_id"] == "test-run"
    assert summary["total_cases"] == 2
    assert summary["passed_cases"] == 1
    # New design: pass_rate_percent is calculated from passed_cases/total_cases
    assert summary["pass_rate_percent"] == 50.0
    # Verify operational metrics are included
    assert "avg_latency_ms" in summary
    assert "total_cost_usd" in summary
    assert "cache_hit_rate_percent" in summary

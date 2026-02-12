"""
Tests for agentops.evaluator module.
"""

from datetime import datetime

import pytest

from agentops.evaluator import Evaluator
from agentops.models import RegressionReport, TestResult


def test_calculate_accuracy():
    """Test accuracy calculation."""
    results = [
        TestResult(
            case_id="TC1",
            actual_output="output",
            passed=True,
            score=1.0,
            execution_time=0.1,
            timestamp=datetime.now(),
        ),
        TestResult(
            case_id="TC2",
            actual_output="output",
            passed=False,
            score=0.0,
            execution_time=0.1,
            timestamp=datetime.now(),
        ),
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
        cache_hit=False,
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
        cache_hit=False,
    )

    report = RegressionReport(
        run_id="test-run",
        timestamp=datetime.now(),
        total_cases=2,
        passed_cases=1,
        failed_cases=1,
        average_score=0.5,
        results=[result1, result2],
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
    # S1/S2 breakdown – no severity in metrics → totals are 0
    assert summary["s1_total"] == 0
    assert summary["s2_total"] == 0
    assert summary["pass_rate_s1"] == "N/A"
    assert summary["pass_rate_s2"] == "N/A"


def test_generate_summary_s1_s2_breakdown():
    """Test S1/S2 pass-rate breakdown in generate_summary."""
    s1_pass = TestResult(
        case_id="TC_S1_01",
        actual_output="ok",
        passed=True,
        score=1.0,
        execution_time=0.1,
        timestamp=datetime.now(),
        metrics={"severity": "S1"},
    )
    s1_fail = TestResult(
        case_id="TC_S1_02",
        actual_output="ng",
        passed=False,
        score=0.0,
        execution_time=0.1,
        timestamp=datetime.now(),
        metrics={"severity": "S1"},
    )
    s2_pass = TestResult(
        case_id="TC_S2_01",
        actual_output="ok",
        passed=True,
        score=1.0,
        execution_time=0.1,
        timestamp=datetime.now(),
        metrics={"severity": "S2"},
    )

    report = RegressionReport(
        run_id="run-s1s2",
        timestamp=datetime.now(),
        total_cases=3,
        passed_cases=2,
        failed_cases=1,
        average_score=0.67,
        results=[s1_pass, s1_fail, s2_pass],
    )

    summary = Evaluator.generate_summary(report)

    # S1: 1 passed / 2 total = 50%
    assert summary["s1_total"] == 2
    assert summary["s1_passed"] == 1
    assert summary["s1_rate_percent"] == 50.0
    assert summary["pass_rate_s1"] == "50.00%"

    # S2: 1 passed / 1 total = 100%
    assert summary["s2_total"] == 1
    assert summary["s2_passed"] == 1
    assert summary["s2_rate_percent"] == 100.0
    assert summary["pass_rate_s2"] == "100.00%"

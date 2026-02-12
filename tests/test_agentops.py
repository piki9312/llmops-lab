"""
Tests for agentops.models module.
"""

from datetime import datetime

import pytest

from agentops.models import RegressionReport, TestCase, TestResult


def test_imports():
    """Test that all modules can be imported."""
    from agentops import cli, evaluator, load_cases, models, report_weekly, runner

    assert models is not None
    assert load_cases is not None
    assert runner is not None
    assert evaluator is not None
    assert report_weekly is not None
    assert cli is not None


def test_test_case_creation():
    """Test TestCase model creation."""
    case = TestCase(case_id="TC001", name="Test Case 1", input_prompt="Test prompt")

    assert case.case_id == "TC001"
    assert case.name == "Test Case 1"
    assert case.input_prompt == "Test prompt"
    assert case.metadata == {}


def test_test_result_creation():
    """Test TestResult model creation."""
    result = TestResult(
        case_id="TC001",
        actual_output="Test output",
        passed=True,
        score=1.0,
        execution_time=0.5,
        timestamp=datetime.now(),
    )

    assert result.case_id == "TC001"
    assert result.passed is True
    assert result.score == 1.0


def test_regression_report_pass_rate():
    """Test RegressionReport pass rate calculation."""
    report = RegressionReport(
        run_id="test-run",
        timestamp=datetime.now(),
        total_cases=10,
        passed_cases=8,
        failed_cases=2,
        average_score=0.8,
        results=[],
    )

    assert report.pass_rate == 80.0

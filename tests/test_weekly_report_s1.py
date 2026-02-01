"""
Tests for S1/S2 pass rate reporting in weekly reports.
"""

import pytest
from datetime import datetime
from src.agentops.report_weekly import WeeklyReporter
from src.agentops.models import RegressionReport, TestResult


class TestWeeklyReportS1S2:
    """Test S1/S2 pass rates and failure prioritization in reports."""
    
    def test_s1_pass_rate_calculation(self):
        """Test S1 pass rate is calculated correctly."""
        results = [
            TestResult(
                case_id="TC_S1_001",
                actual_output="output",
                passed=True,
                score=1.0,
                execution_time=0.1,
                timestamp=datetime.now(),
                metrics={"severity": "S1"}
            ),
            TestResult(
                case_id="TC_S1_002",
                actual_output="output",
                passed=False,
                score=0.0,
                execution_time=0.1,
                timestamp=datetime.now(),
                failure_type="quality_fail",
                error="Missing keys",
                metrics={"severity": "S1"}
            ),
            TestResult(
                case_id="TC_S2_001",
                actual_output="output",
                passed=True,
                score=1.0,
                execution_time=0.1,
                timestamp=datetime.now(),
                metrics={"severity": "S2"}
            ),
        ]
        
        report = RegressionReport(
            run_id="test-run",
            timestamp=datetime.now(),
            total_cases=3,
            passed_cases=2,
            failed_cases=1,
            average_score=0.67,
            results=results
        )
        
        reporter = WeeklyReporter()
        report_content = reporter.generate_report([report])
        
        # Verify S1 pass rate is shown
        assert "S1成功率" in report_content
        assert "50.00%" in report_content  # 1/2 S1 cases passed
        
        # Verify S2 pass rate
        assert "S2成功率" in report_content
        assert "100.00%" in report_content  # 1/1 S2 cases passed
    
    def test_s1_failures_shown_first(self):
        """Test S1 failures appear before S2 in top failures list."""
        results = [
            TestResult(
                case_id="TC_S2_001",
                actual_output="",
                passed=False,
                score=0.0,
                execution_time=0.1,
                timestamp=datetime.now(),
                failure_type="empty_output",
                error="No output",
                metrics={"severity": "S2"}
            ),
            TestResult(
                case_id="TC_S2_001",
                actual_output="",
                passed=False,
                score=0.0,
                execution_time=0.1,
                timestamp=datetime.now(),
                failure_type="empty_output",
                error="No output",
                metrics={"severity": "S2"}
            ),
            TestResult(
                case_id="TC_S1_001",
                actual_output="{}",
                passed=False,
                score=0.0,
                execution_time=0.1,
                timestamp=datetime.now(),
                failure_type="quality_fail",
                error="Missing keys",
                metrics={"severity": "S1"}
            ),
        ]
        
        report = RegressionReport(
            run_id="test-run",
            timestamp=datetime.now(),
            total_cases=3,
            passed_cases=0,
            failed_cases=3,
            average_score=0.0,
            results=results
        )
        
        reporter = WeeklyReporter()
        report_content = reporter.generate_report([report])
        
        # Find the failures section
        failures_section = report_content.split("失敗トップ10")[1] if "失敗トップ10" in report_content else ""
        
        # S1 failure should appear before S2 failures
        s1_pos = failures_section.find("TC_S1_001")
        s2_pos = failures_section.find("TC_S2_001")
        
        assert s1_pos > 0, "S1 failure should be in report"
        assert s2_pos > 0, "S2 failure should be in report"
        assert s1_pos < s2_pos, "S1 failure should appear before S2"
    
    def test_failure_type_in_report(self):
        """Test failure_type is used in weekly report."""
        results = [
            TestResult(
                case_id="TC_001",
                actual_output="not json",
                passed=False,
                score=0.0,
                execution_time=0.1,
                timestamp=datetime.now(),
                failure_type="bad_json",
                error="Invalid JSON",
                metrics={"severity": "S1"}
            ),
        ]
        
        report = RegressionReport(
            run_id="test-run",
            timestamp=datetime.now(),
            total_cases=1,
            passed_cases=0,
            failed_cases=1,
            average_score=0.0,
            results=results
        )
        
        reporter = WeeklyReporter()
        report_content = reporter.generate_report([report])
        
        # Verify bad_json appears in failure breakdown
        assert "bad_json" in report_content
        assert "prompt/schema" in report_content  # Suspected cause

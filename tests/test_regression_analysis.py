"""
Tests for regression analysis in weekly reporting.

Tests baseline comparison, delta calculations, and top regression detection.
"""

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pytest

from agentops.models import AgentRunRecord, RegressionReport, TestResult
from agentops.report_weekly import WeeklyReporter


def create_synthetic_records(
    num_records: int = 10,
    pass_rate: float = 0.5,
    severity: str = "S1",
    date: Optional[datetime] = None,
    run_id: str = "test-run",
    case_id_prefix: str = "TC",
) -> list:
    """Create synthetic AgentRunRecord instances for testing."""
    if date is None:
        date = datetime.now(timezone.utc)

    records = []
    for i in range(num_records):
        passed = i < int(num_records * pass_rate)
        case_id = f"{case_id_prefix}{i:03d}"

        record = AgentRunRecord(
            timestamp=date,
            run_id=run_id,
            case_id=case_id,
            severity=severity,
            category="test_category",
            passed=passed,
            failure_type="quality_fail" if not passed else None,
            latency_ms=100.0 + i,
            reasons=["test reason"] if not passed else [],
            provider="mock",
            model="test-model",
        )
        records.append(record)

    return records


def write_jsonl_records(tmp_dir: Path, records: list, date: datetime) -> Path:
    """Write records to JSONL file and return path."""
    jsonl_file = tmp_dir / f"{date.strftime('%Y%m%d')}.jsonl"
    with open(jsonl_file, "w", encoding="utf-8") as f:
        for record in records:
            f.write(record.model_dump_json() + "\n")
    return jsonl_file


class TestRegressionAnalysis:
    """Test regression analysis functionality."""

    def test_compute_case_pass_rates(self):
        """Test case-level pass rate computation."""
        records = create_synthetic_records(num_records=10, pass_rate=0.5)
        # Convert to TestResult for compatibility
        results = [
            TestResult(
                case_id=r.case_id,
                actual_output="",
                passed=r.passed,
                score=1.0 if r.passed else 0.0,
                execution_time=0.1,
                timestamp=r.timestamp,
                latency_ms=r.latency_ms,
                metrics={"severity": r.severity},
            )
            for r in records
        ]

        pass_rates = WeeklyReporter._compute_case_pass_rates(results)

        # Each case appears once, so rates should be 0 or 1
        assert all(rate in [0.0, 1.0] for rate in pass_rates.values())
        assert len(pass_rates) == 10  # 10 unique cases

    def test_compute_pass_rate_delta_with_baseline(self):
        """Test pass rate delta computation with baseline."""
        # Baseline: 80% pass rate
        baseline_records = create_synthetic_records(
            num_records=10, pass_rate=0.8, run_id="baseline"
        )
        baseline_results = [
            TestResult(
                case_id=r.case_id,
                actual_output="",
                passed=r.passed,
                score=1.0 if r.passed else 0.0,
                execution_time=0.1,
                timestamp=r.timestamp,
                latency_ms=r.latency_ms,
                metrics={"severity": r.severity},
            )
            for r in baseline_records
        ]

        # Current: 50% pass rate
        current_records = create_synthetic_records(num_records=10, pass_rate=0.5, run_id="current")
        current_results = [
            TestResult(
                case_id=r.case_id,
                actual_output="",
                passed=r.passed,
                score=1.0 if r.passed else 0.0,
                execution_time=0.1,
                timestamp=r.timestamp,
                latency_ms=r.latency_ms,
                metrics={"severity": r.severity},
            )
            for r in current_records
        ]

        baseline_rate, current_rate, delta = WeeklyReporter._compute_pass_rate_delta(
            current_results, baseline_results
        )

        assert baseline_rate == 80.0
        assert current_rate == 50.0
        assert delta == -30.0  # 50 - 80

    def test_compute_pass_rate_delta_no_baseline(self):
        """Test pass rate delta when baseline is empty."""
        current_records = create_synthetic_records(num_records=10, pass_rate=0.5)
        current_results = [
            TestResult(
                case_id=r.case_id,
                actual_output="",
                passed=r.passed,
                score=1.0 if r.passed else 0.0,
                execution_time=0.1,
                timestamp=r.timestamp,
                latency_ms=r.latency_ms,
                metrics={"severity": r.severity},
            )
            for r in current_records
        ]

        baseline_rate, current_rate, delta = WeeklyReporter._compute_pass_rate_delta(
            current_results, []
        )

        assert baseline_rate == 0.0
        assert current_rate == 50.0
        assert delta == 50.0

    def test_compute_pass_rate_delta_by_severity(self):
        """Test pass rate delta computation filtered by severity."""
        # Baseline: S1 80%, S2 100%
        baseline_s1 = create_synthetic_records(
            num_records=5, pass_rate=0.8, severity="S1", run_id="baseline"
        )
        baseline_s2 = create_synthetic_records(
            num_records=5, pass_rate=1.0, severity="S2", case_id_prefix="TC1", run_id="baseline"
        )
        baseline_results = [
            TestResult(
                case_id=r.case_id,
                actual_output="",
                passed=r.passed,
                score=1.0 if r.passed else 0.0,
                execution_time=0.1,
                timestamp=r.timestamp,
                latency_ms=r.latency_ms,
                metrics={"severity": r.severity},
            )
            for r in baseline_s1 + baseline_s2
        ]

        # Current: S1 50%, S2 80%
        current_s1 = create_synthetic_records(
            num_records=5, pass_rate=0.5, severity="S1", run_id="current"
        )
        current_s2 = create_synthetic_records(
            num_records=5, pass_rate=0.8, severity="S2", case_id_prefix="TC1", run_id="current"
        )
        current_results = [
            TestResult(
                case_id=r.case_id,
                actual_output="",
                passed=r.passed,
                score=1.0 if r.passed else 0.0,
                execution_time=0.1,
                timestamp=r.timestamp,
                latency_ms=r.latency_ms,
                metrics={"severity": r.severity},
            )
            for r in current_s1 + current_s2
        ]

        # S1 delta
        s1_baseline, s1_current, s1_delta = WeeklyReporter._compute_pass_rate_delta(
            current_results, baseline_results, severity="S1"
        )
        # S1 baseline: 4/5=80%, current: 2/5=40%, delta: -40%
        assert s1_baseline == 80.0
        assert s1_current == 40.0
        assert s1_delta == -40.0

        # S2 delta should be 80 - 100 = -20
        s2_baseline, s2_current, s2_delta = WeeklyReporter._compute_pass_rate_delta(
            current_results, baseline_results, severity="S2"
        )
        assert s2_delta == -20.0

    def test_compute_failure_type_delta(self):
        """Test failure type count delta computation."""
        # Baseline: 3x quality_fail, 2x timeout
        baseline_records = create_synthetic_records(num_records=5, pass_rate=0.0, run_id="baseline")
        baseline_results = [
            TestResult(
                case_id=r.case_id,
                actual_output="",
                passed=r.passed,
                score=0.0,
                execution_time=0.1,
                timestamp=r.timestamp,
                failure_type="quality_fail" if i < 3 else "timeout",
                latency_ms=r.latency_ms,
                metrics={"severity": r.severity},
            )
            for i, r in enumerate(baseline_records)
        ]

        # Current: 2x quality_fail, 3x timeout, 1x bad_json
        current_records = create_synthetic_records(num_records=6, pass_rate=0.0, run_id="current")
        current_results = [
            TestResult(
                case_id=r.case_id,
                actual_output="",
                passed=r.passed,
                score=0.0,
                execution_time=0.1,
                timestamp=r.timestamp,
                failure_type=("quality_fail" if i < 2 else "timeout" if i < 5 else "bad_json"),
                latency_ms=r.latency_ms,
                metrics={"severity": r.severity},
            )
            for i, r in enumerate(current_records)
        ]

        delta = WeeklyReporter._compute_failure_type_delta(current_results, baseline_results)

        assert delta["quality_fail"] == -1  # 2 - 3
        assert delta["timeout"] == 1  # 3 - 2
        assert delta["bad_json"] == 1  # 1 - 0

    def test_compute_top_regressions(self):
        """Test top regression detection."""
        # Baseline: all pass (100%)
        baseline_records = create_synthetic_records(
            num_records=5, pass_rate=1.0, severity="S1", run_id="baseline"
        )
        baseline_results = [
            TestResult(
                case_id=r.case_id,
                actual_output="",
                passed=r.passed,
                score=1.0,
                execution_time=0.1,
                timestamp=r.timestamp,
                latency_ms=r.latency_ms,
                metrics={"severity": r.severity, "category": "api"},
            )
            for r in baseline_records
        ]

        # Current: TC000 100%, TC001 50%, TC002 0%, TC003 100%, TC004 0%
        current_records_data = [
            (True, "TC000"),
            (True, "TC000"),
            (True, "TC001"),
            (False, "TC001"),
            (False, "TC002"),
            (False, "TC002"),
            (True, "TC003"),
            (True, "TC003"),
            (False, "TC004"),
            (False, "TC004"),
        ]
        current_results = [
            TestResult(
                case_id=case_id,
                actual_output="",
                passed=passed,
                score=1.0 if passed else 0.0,
                execution_time=0.1,
                timestamp=datetime.now(timezone.utc),
                failure_type=None if passed else "quality_fail",
                latency_ms=100.0,
                metrics={"severity": "S1", "category": "api"},
            )
            for passed, case_id in current_records_data
        ]

        regressions = WeeklyReporter._compute_top_regressions(
            current_results, baseline_results, top_n=5
        )

        # _compute_top_regressions includes ALL deltas <= 0 (regressions and non-changes)
        # TC000: 100->100 (delta 0)
        # TC001: 100->50 (delta -50)
        # TC002: 100->0 (delta -100)
        # TC003: 100->100 (delta 0)
        # TC004: 100->0 (delta -100)
        # Total: 5 cases with delta <= 0
        assert len(regressions) == 5
        # First two should be TC002 and TC004 with -100% delta
        assert regressions[0]["delta"] == -100.0
        assert regressions[1]["delta"] == -100.0

    def test_compute_top_regressions_prioritizes_s1(self):
        """Test that S1 cases are prioritized in top regressions when tied."""
        # Both S1 and S2 with same delta
        baseline_results = [
            TestResult(
                case_id="TC_S1_001",
                actual_output="",
                passed=True,
                score=1.0,
                execution_time=0.1,
                timestamp=datetime.now(timezone.utc),
                latency_ms=100.0,
                metrics={"severity": "S1", "category": "api"},
            ),
            TestResult(
                case_id="TC_S2_001",
                actual_output="",
                passed=True,
                score=1.0,
                execution_time=0.1,
                timestamp=datetime.now(timezone.utc),
                latency_ms=100.0,
                metrics={"severity": "S2", "category": "api"},
            ),
        ]

        current_results = [
            TestResult(
                case_id="TC_S1_001",
                actual_output="",
                passed=False,
                score=0.0,
                execution_time=0.1,
                timestamp=datetime.now(timezone.utc),
                failure_type="quality_fail",
                latency_ms=100.0,
                metrics={"severity": "S1", "category": "api"},
            ),
            TestResult(
                case_id="TC_S2_001",
                actual_output="",
                passed=False,
                score=0.0,
                execution_time=0.1,
                timestamp=datetime.now(timezone.utc),
                failure_type="quality_fail",
                latency_ms=100.0,
                metrics={"severity": "S2", "category": "api"},
            ),
        ]

        regressions = WeeklyReporter._compute_top_regressions(
            current_results, baseline_results, top_n=2
        )

        # S1 should come first despite same delta
        assert regressions[0]["case_id"] == "TC_S1_001"
        assert regressions[0]["severity"] == "S1"

    def test_load_from_jsonl_with_date_range(self):
        """Test load_from_jsonl respects date range."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Create JSONL files for different dates
            today = datetime.now()
            yesterday = today - timedelta(days=1)
            two_days_ago = today - timedelta(days=2)

            records_today = create_synthetic_records(num_records=5, date=today)
            records_yesterday = create_synthetic_records(
                num_records=5, date=yesterday, run_id="yesterday"
            )
            records_2days = create_synthetic_records(
                num_records=5, date=two_days_ago, run_id="2days"
            )

            write_jsonl_records(tmp_path, records_today, today)
            write_jsonl_records(tmp_path, records_yesterday, yesterday)
            write_jsonl_records(tmp_path, records_2days, two_days_ago)

            # Load last 1 day (today only)
            reports = WeeklyReporter.load_from_jsonl(
                log_dir=str(tmp_path),
                start_date=today.replace(hour=0, minute=0, second=0, microsecond=0),
                end_date=today.replace(hour=23, minute=59, second=59, microsecond=999999),
            )

            assert len(reports) == 1
            assert reports[0].total_cases == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

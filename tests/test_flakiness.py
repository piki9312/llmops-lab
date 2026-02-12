"""Tests for agentops.flakiness – stability/flakiness detection.

Covers:
- compute_flakiness() core logic
- Flaky vs stable classification
- min_runs filter
- Latency CV calculation
- flaky_cases() convenience filter
- render_flakiness_report() Markdown output
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

import pytest

from agentops.flakiness import (
    CaseStability,
    compute_flakiness,
    flaky_cases,
    render_flakiness_report,
)

# ========================================================================
# Minimal stub
# ========================================================================


@dataclass
class _R:
    """Minimal result stub."""

    case_id: str = "TC001"
    passed: bool = True
    failure_type: Optional[str] = None
    latency_ms: float = 50.0
    total_tokens: int = 0
    actual_output: str = ""
    metrics: Optional[Dict] = field(default_factory=lambda: {"severity": "S1", "category": "api"})


# ========================================================================
# compute_flakiness
# ========================================================================


class TestComputeFlakiness:
    def test_all_pass(self):
        """All passing → not flaky."""
        results = [_R(case_id="TC001", passed=True) for _ in range(3)]
        stats = compute_flakiness(results)
        assert len(stats) == 1
        assert stats[0].is_flaky is False
        assert stats[0].pass_rate == pytest.approx(100.0)

    def test_all_fail(self):
        """All failing → not flaky (consistent failure)."""
        results = [_R(case_id="TC001", passed=False, failure_type="timeout") for _ in range(3)]
        stats = compute_flakiness(results)
        assert len(stats) == 1
        assert stats[0].is_flaky is False
        assert stats[0].pass_rate == pytest.approx(0.0, abs=0.01)

    def test_flaky_case(self):
        """Mixed pass/fail → flaky."""
        results = [
            _R(case_id="TC001", passed=True),
            _R(case_id="TC001", passed=False, failure_type="bad_json"),
            _R(case_id="TC001", passed=True),
        ]
        stats = compute_flakiness(results)
        assert len(stats) == 1
        s = stats[0]
        assert s.is_flaky is True
        assert s.total_runs == 3
        assert s.passed_runs == 2
        assert s.failed_runs == 1
        assert s.pass_rate == pytest.approx(2 / 3 * 100)

    def test_min_runs_filter(self):
        """Single run filtered out by min_runs=2."""
        results = [_R(case_id="TC001", passed=True)]
        stats = compute_flakiness(results, min_runs=2)
        assert len(stats) == 0

    def test_min_runs_default(self):
        """min_runs=2 by default; 2 runs OK."""
        results = [
            _R(case_id="TC001", passed=True),
            _R(case_id="TC001", passed=False),
        ]
        stats = compute_flakiness(results, min_runs=2)
        assert len(stats) == 1
        assert stats[0].is_flaky is True

    def test_multiple_cases(self):
        """Two distinct cases."""
        results = [
            _R(case_id="TC001", passed=True),
            _R(case_id="TC001", passed=True),
            _R(case_id="TC002", passed=True),
            _R(case_id="TC002", passed=False),
        ]
        stats = compute_flakiness(results)
        by_id = {s.case_id: s for s in stats}
        assert by_id["TC001"].is_flaky is False
        assert by_id["TC002"].is_flaky is True

    def test_failure_types_collected(self):
        """Distinct failure types are tracked."""
        results = [
            _R(case_id="TC001", passed=False, failure_type="timeout"),
            _R(case_id="TC001", passed=False, failure_type="bad_json"),
            _R(case_id="TC001", passed=False, failure_type="timeout"),
        ]
        stats = compute_flakiness(results)
        assert set(stats[0].failure_types) == {"timeout", "bad_json"}

    def test_latency_cv(self):
        """Latency CV correctly computed."""
        results = [
            _R(case_id="TC001", latency_ms=100.0, passed=True),
            _R(case_id="TC001", latency_ms=100.0, passed=True),
            _R(case_id="TC001", latency_ms=100.0, passed=True),
        ]
        stats = compute_flakiness(results)
        # All same latency → std=0 → CV=0
        assert stats[0].latency_cv == pytest.approx(0.0, abs=0.01)

    def test_latency_cv_positive(self):
        """Nonzero latency CV for varying latencies."""
        results = [
            _R(case_id="TC001", latency_ms=100.0, passed=True),
            _R(case_id="TC001", latency_ms=200.0, passed=True),
        ]
        stats = compute_flakiness(results)
        assert stats[0].latency_cv > 0.0


# ========================================================================
# flaky_cases convenience
# ========================================================================


class TestFlakyCases:
    def test_filters_only_flaky(self):
        results = [
            _R(case_id="TC001", passed=True),
            _R(case_id="TC001", passed=True),
            _R(case_id="TC002", passed=True),
            _R(case_id="TC002", passed=False),
        ]
        flaky = flaky_cases(results)
        assert len(flaky) == 1
        assert flaky[0].case_id == "TC002"


# ========================================================================
# render_flakiness_report
# ========================================================================


class TestRenderFlakinessReport:
    def test_empty(self):
        assert render_flakiness_report([]) == ""

    def test_basic_render(self):
        stats = [
            CaseStability(
                case_id="TC001",
                severity="S1",
                category="api",
                total_runs=3,
                passed_runs=2,
                failed_runs=1,
                pass_rate=66.7,
                is_flaky=True,
                failure_types=["bad_json"],
                latency_std=12.3,
                latency_cv=0.15,
            )
        ]
        md = render_flakiness_report(stats)
        assert "Flakiness" in md or "Stability" in md
        assert "TC001" in md
        assert "🎲" in md

    def test_flaky_only_filter(self):
        stats = [
            CaseStability("TC001", "S1", "api", 3, 3, 0, 100.0, False, [], 0, 0),
            CaseStability("TC002", "S1", "api", 3, 2, 1, 66.7, True, ["bad_json"], 5, 0.1),
        ]
        md = render_flakiness_report(stats, flaky_only=True)
        assert "TC001" not in md
        assert "TC002" in md

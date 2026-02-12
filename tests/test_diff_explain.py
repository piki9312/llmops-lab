"""Tests for agentops.diff_explain – failure explanation engine.

Covers:
- explain_failures() with various failure scenarios
- Schema diff detection for S1 cases
- Failure type change detection
- Latency/token spike detection
- New vs persistent failure classification
- render_failure_explanations() Markdown output
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pytest

from agentops.diff_explain import (
    FailureExplanation,
    _detect_schema_diff,
    _dominant_failure_type,
    _latency_ratio,
    _token_ratio,
    explain_failures,
    render_failure_explanations,
)

# ========================================================================
# Minimal stub for TestResult-like objects
# ========================================================================


@dataclass
class _R:
    """Minimal result stub."""

    case_id: str = "TC001"
    passed: bool = True
    failure_type: Optional[str] = None
    actual_output: str = ""
    latency_ms: float = 50.0
    total_tokens: int = 0
    metrics: Optional[Dict] = field(default_factory=lambda: {"severity": "S1", "category": "api"})


# ========================================================================
# explain_failures
# ========================================================================


class TestExplainFailures:
    def test_new_regression(self):
        """Case passed in baseline, fails now → 新規回帰."""
        baseline = [_R(case_id="TC001", passed=True)]
        current = [_R(case_id="TC001", passed=False, failure_type="bad_json")]
        exps = explain_failures(current, baseline)
        assert len(exps) == 1
        assert "新規回帰" in exps[0].explanation

    def test_persistent_failure(self):
        """Case already failed in baseline → 継続失敗."""
        baseline = [_R(case_id="TC001", passed=False, failure_type="timeout")]
        current = [_R(case_id="TC001", passed=False, failure_type="timeout")]
        exps = explain_failures(current, baseline)
        assert len(exps) == 1
        assert "継続失敗" in exps[0].explanation

    def test_no_baseline_data(self):
        """Case has no baseline records."""
        current = [_R(case_id="TC001", passed=False)]
        exps = explain_failures(current, [])
        assert len(exps) == 1
        assert "ベースラインデータなし" in exps[0].explanation

    def test_failure_type_change(self):
        """Failure type changed between baseline and current."""
        baseline = [_R(case_id="TC001", passed=False, failure_type="timeout")]
        current = [_R(case_id="TC001", passed=False, failure_type="bad_json")]
        exps = explain_failures(current, baseline)
        assert "失敗タイプ変化" in exps[0].explanation
        assert "timeout → bad_json" in exps[0].explanation

    def test_passing_cases_excluded(self):
        """Only failing cases get explanations."""
        baseline = [_R(case_id="TC001", passed=True)]
        current = [_R(case_id="TC001", passed=True)]
        exps = explain_failures(current, baseline)
        assert len(exps) == 0

    def test_s1_sorted_first(self):
        """S1 failures should appear before S2."""
        baseline = [
            _R(case_id="TC001", passed=True, metrics={"severity": "S2", "category": "x"}),
            _R(case_id="TC002", passed=True, metrics={"severity": "S1", "category": "api"}),
        ]
        current = [
            _R(case_id="TC001", passed=False, metrics={"severity": "S2", "category": "x"}),
            _R(case_id="TC002", passed=False, metrics={"severity": "S1", "category": "api"}),
        ]
        exps = explain_failures(current, baseline)
        assert exps[0].severity == "S1"
        assert exps[1].severity == "S2"


# ========================================================================
# Schema diff (S1)
# ========================================================================


class TestSchemaDiff:
    def test_missing_keys(self):
        """Baseline has keys that current lacks."""
        baseline = [_R(actual_output='{"a": 1, "b": 2}')]
        current = [_R(actual_output='{"a": 1}', passed=False)]
        diff = _detect_schema_diff(current, baseline)
        assert diff is not None
        assert "b" in diff["missing_keys"]

    def test_extra_keys(self):
        """Current has keys that baseline lacks."""
        baseline = [_R(actual_output='{"a": 1}')]
        current = [_R(actual_output='{"a": 1, "c": 3}', passed=False)]
        diff = _detect_schema_diff(current, baseline)
        assert diff is not None
        assert "c" in diff["extra_keys"]

    def test_type_change(self):
        """Same key but different type."""
        baseline = [_R(actual_output='{"a": 1}')]
        current = [_R(actual_output='{"a": "string"}', passed=False)]
        diff = _detect_schema_diff(current, baseline)
        assert diff is not None
        assert "a" in diff["type_changes"]

    def test_no_diff(self):
        """Same schema → returns None."""
        baseline = [_R(actual_output='{"a": 1}')]
        current = [_R(actual_output='{"a": 2}', passed=False)]
        diff = _detect_schema_diff(current, baseline)
        assert diff is None

    def test_non_json_output(self):
        """Non-JSON output → no diff."""
        baseline = [_R(actual_output="hello")]
        current = [_R(actual_output="world", passed=False)]
        diff = _detect_schema_diff(current, baseline)
        assert diff is None

    def test_schema_diff_in_explanation(self):
        """S1 case with schema diff includes it in signals."""
        baseline = [_R(case_id="TC001", passed=True, actual_output='{"a": 1, "b": 2}')]
        current = [_R(case_id="TC001", passed=False, actual_output='{"a": 1}')]
        exps = explain_failures(current, baseline)
        assert any("schema不一致" in s for s in exps[0].signals)


# ========================================================================
# Latency / token ratio
# ========================================================================


class TestLatencyTokenRatio:
    def test_latency_spike(self):
        baseline = [_R(latency_ms=100.0)]
        current = [_R(latency_ms=250.0, passed=False)]
        ratio = _latency_ratio(current, baseline)
        assert ratio == pytest.approx(2.5)

    def test_latency_no_data(self):
        assert _latency_ratio([], []) is None
        assert _latency_ratio([_R(latency_ms=100)], []) is None

    def test_token_increase(self):
        baseline = [_R(total_tokens=100)]
        current = [_R(total_tokens=200, passed=False)]
        ratio = _token_ratio(current, baseline)
        assert ratio == pytest.approx(2.0)

    def test_latency_in_explanation(self):
        """Latency spike appears in explanation signals."""
        baseline = [_R(case_id="TC001", passed=True, latency_ms=50.0)]
        current = [_R(case_id="TC001", passed=False, latency_ms=150.0)]
        exps = explain_failures(current, baseline, latency_threshold=2.0)
        assert any("レイテンシ急増" in s for s in exps[0].signals)


# ========================================================================
# Rendering
# ========================================================================


class TestRenderFailureExplanations:
    def test_empty(self):
        assert render_failure_explanations([]) == ""

    def test_basic_render(self):
        exps = [
            FailureExplanation(
                case_id="TC001",
                severity="S1",
                category="api",
                signals=["新規回帰: ベースラインでは全パス", "失敗タイプ: bad_json"],
                current_failure_type="bad_json",
            )
        ]
        md = render_failure_explanations(exps)
        assert "Failure Explanations" in md
        assert "TC001" in md
        assert "bad_json" in md


# ========================================================================
# _dominant_failure_type
# ========================================================================


class TestDominantFailureType:
    def test_single(self):
        assert _dominant_failure_type([_R(failure_type="bad_json")]) == "bad_json"

    def test_majority(self):
        results = [
            _R(failure_type="bad_json"),
            _R(failure_type="bad_json"),
            _R(failure_type="timeout"),
        ]
        assert _dominant_failure_type(results) == "bad_json"

    def test_none(self):
        assert _dominant_failure_type([_R()]) is None

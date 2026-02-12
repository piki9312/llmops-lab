"""Tests for agentops.check – gate check logic.

Covers:
- run_check() with various JSONL data scenarios
- ThresholdResult / CheckResult data structures
- render_check_summary() Markdown output
- CLI check_gate() integration (exit codes, --write-summary)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

import pytest

from agentops.check import (
    CheckResult,
    ThresholdResult,
    render_check_summary,
    run_check,
)
from agentops.cli import check_gate

# ========================================================================
# Helpers
# ========================================================================


def _write_jsonl(path: Path, records: list) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


def _make_record(
    *,
    case_id: str = "TC001",
    severity: str = "S1",
    category: str = "api",
    passed: bool = True,
    run_id: str = "run-001",
    failure_type: str | None = None,
    latency_ms: float = 50.0,
) -> dict:
    rec: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "case_id": case_id,
        "severity": severity,
        "category": category,
        "passed": passed,
        "latency_ms": latency_ms,
        "reasons": [],
    }
    if failure_type:
        rec["failure_type"] = failure_type
    return rec


def _setup_jsonl(tmp_path: Path, records: list) -> Path:
    """Write records to today's JSONL and return the log dir."""
    log_dir = tmp_path / "runs" / "agentreg"
    log_dir.mkdir(parents=True)
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    _write_jsonl(log_dir / f"{today}.jsonl", records)
    return log_dir


# ========================================================================
# run_check
# ========================================================================


class TestRunCheck:
    def test_all_pass(self, tmp_path: Path):
        log_dir = _setup_jsonl(
            tmp_path,
            [
                _make_record(case_id="TC001", severity="S1", passed=True),
                _make_record(case_id="TC002", severity="S2", passed=True),
            ],
        )
        result = run_check(log_dir=str(log_dir), days=1, baseline_days=7)

        assert result.current_runs == 1
        assert result.overall_rate == 100.0
        assert result.s1_rate == 100.0
        assert result.s1_passed == 1
        assert result.s1_total == 1
        assert result.gate_passed is True

    def test_s1_failure_breaks_gate(self, tmp_path: Path):
        log_dir = _setup_jsonl(
            tmp_path,
            [
                _make_record(case_id="TC001", severity="S1", passed=False, failure_type="bad_json"),
                _make_record(case_id="TC002", severity="S2", passed=True),
            ],
        )
        result = run_check(
            log_dir=str(log_dir),
            days=1,
            baseline_days=7,
            s1_threshold=100.0,
            overall_threshold=0.0,
        )

        assert result.s1_rate == 0.0
        assert result.gate_passed is False
        # Check that the S1 threshold is the one that failed
        s1_thresh = [t for t in result.thresholds if t.name == "S1 pass rate"][0]
        assert s1_thresh.passed is False

    def test_overall_threshold_fail(self, tmp_path: Path):
        log_dir = _setup_jsonl(
            tmp_path,
            [
                _make_record(case_id="TC001", severity="S2", passed=False),
                _make_record(case_id="TC002", severity="S2", passed=False),
                _make_record(case_id="TC003", severity="S2", passed=True),
            ],
        )
        result = run_check(
            log_dir=str(log_dir),
            days=1,
            baseline_days=7,
            s1_threshold=100.0,
            overall_threshold=50.0,
        )

        assert result.overall_rate == pytest.approx(33.33, abs=0.1)
        assert result.gate_passed is False

    def test_no_s1_cases_skips_threshold(self, tmp_path: Path):
        log_dir = _setup_jsonl(
            tmp_path,
            [
                _make_record(case_id="TC001", severity="S2", passed=True),
            ],
        )
        result = run_check(log_dir=str(log_dir), days=1, baseline_days=7)

        assert result.s1_total == 0
        s1_thresh = [t for t in result.thresholds if t.name == "S1 pass rate"][0]
        assert s1_thresh.passed is True  # skip → pass

    def test_empty_log_dir(self, tmp_path: Path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        result = run_check(log_dir=str(empty_dir), days=1, baseline_days=7)
        assert result.current_runs == 0

    def test_custom_thresholds(self, tmp_path: Path):
        """50% S1 threshold with 1/2 S1 passed → gate passes."""
        log_dir = _setup_jsonl(
            tmp_path,
            [
                _make_record(case_id="TC001", severity="S1", passed=True),
                _make_record(case_id="TC002", severity="S1", passed=False),
            ],
        )
        result = run_check(
            log_dir=str(log_dir),
            days=1,
            baseline_days=7,
            s1_threshold=50.0,
            overall_threshold=50.0,
        )
        assert result.gate_passed is True

    def test_baseline_comparison(self, tmp_path: Path):
        """When baseline data exists, top_regressions should be populated."""
        log_dir = tmp_path / "runs" / "agentreg"
        log_dir.mkdir(parents=True)

        # Baseline: 2 days ago – all pass
        baseline_date = (datetime.now() - timedelta(days=2)).strftime("%Y%m%d")
        _write_jsonl(
            log_dir / f"{baseline_date}.jsonl",
            [
                _make_record(case_id="TC001", severity="S1", passed=True, run_id="baseline-run"),
                _make_record(case_id="TC002", severity="S2", passed=True, run_id="baseline-run"),
            ],
        )

        # Current: today – TC001 regressed
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        _write_jsonl(
            log_dir / f"{today}.jsonl",
            [
                _make_record(case_id="TC001", severity="S1", passed=False, run_id="current-run"),
                _make_record(case_id="TC002", severity="S2", passed=True, run_id="current-run"),
            ],
        )

        result = run_check(
            log_dir=str(log_dir),
            days=1,
            baseline_days=7,
        )
        assert result.baseline_runs >= 1
        assert len(result.top_regressions) >= 1
        assert result.top_regressions[0]["case_id"] == "TC001"

    # ---- baseline_dir tests ----

    def test_baseline_dir_used(self, tmp_path: Path):
        """--baseline-dir overrides --baseline-days: reads from separate dir."""
        # Current log dir (today)
        log_dir = _setup_jsonl(
            tmp_path,
            [
                _make_record(case_id="TC001", severity="S1", passed=False, run_id="pr-run"),
                _make_record(case_id="TC002", severity="S2", passed=True, run_id="pr-run"),
            ],
        )

        # Baseline dir (simulates downloaded artifact) – all pass
        baseline_dir = tmp_path / "baseline" / "runs" / "agentreg"
        baseline_dir.mkdir(parents=True)
        _write_jsonl(
            baseline_dir / "20260101.jsonl",
            [
                _make_record(case_id="TC001", severity="S1", passed=True, run_id="main-run"),
                _make_record(case_id="TC002", severity="S2", passed=True, run_id="main-run"),
            ],
        )

        result = run_check(
            log_dir=str(log_dir),
            days=1,
            baseline_dir=str(baseline_dir),
        )
        assert result.baseline_runs >= 1
        assert len(result.top_regressions) >= 1
        assert result.top_regressions[0]["case_id"] == "TC001"

    def test_baseline_dir_empty_falls_through(self, tmp_path: Path):
        """Empty baseline_dir → baseline_runs == 0, no regressions."""
        log_dir = _setup_jsonl(
            tmp_path,
            [
                _make_record(case_id="TC001", severity="S1", passed=True),
            ],
        )
        empty_baseline = tmp_path / "empty_baseline"
        empty_baseline.mkdir()

        result = run_check(
            log_dir=str(log_dir),
            days=1,
            baseline_dir=str(empty_baseline),
        )
        assert result.baseline_runs == 0
        assert result.top_regressions == []

    def test_baseline_dir_cli_integration(self, tmp_path: Path):
        """check_gate() accepts baseline_dir and passes it through."""
        log_dir = _setup_jsonl(
            tmp_path,
            [
                _make_record(case_id="TC001", severity="S1", passed=True),
            ],
        )
        baseline_dir = tmp_path / "baseline"
        baseline_dir.mkdir()
        _write_jsonl(
            baseline_dir / "20260101.jsonl",
            [
                _make_record(case_id="TC001", severity="S1", passed=True, run_id="main"),
            ],
        )

        rc = check_gate(log_dir=str(log_dir), days=1, baseline_dir=str(baseline_dir))
        assert rc == 0


# ========================================================================
# CheckResult / ThresholdResult
# ========================================================================


class TestDataStructures:
    def test_gate_passed_all_true(self):
        cr = CheckResult(
            current_runs=1,
            baseline_runs=0,
            overall_rate=100.0,
            s1_rate=100.0,
            s1_passed=5,
            s1_total=5,
            s2_rate=100.0,
            s2_passed=5,
            s2_total=5,
            thresholds=[
                ThresholdResult(name="S1", threshold=100, actual=100, passed=True),
                ThresholdResult(name="Overall", threshold=80, actual=100, passed=True),
            ],
        )
        assert cr.gate_passed is True

    def test_gate_passed_one_fail(self):
        cr = CheckResult(
            current_runs=1,
            baseline_runs=0,
            overall_rate=50.0,
            s1_rate=50.0,
            s1_passed=1,
            s1_total=2,
            s2_rate=100.0,
            s2_passed=1,
            s2_total=1,
            thresholds=[
                ThresholdResult(name="S1", threshold=100, actual=50, passed=False),
                ThresholdResult(name="Overall", threshold=80, actual=50, passed=False),
            ],
        )
        assert cr.gate_passed is False


# ========================================================================
# render_check_summary
# ========================================================================


class TestRenderCheckSummary:
    def test_pass_output(self):
        cr = CheckResult(
            current_runs=1,
            baseline_runs=0,
            overall_rate=100.0,
            s1_rate=100.0,
            s1_passed=5,
            s1_total=5,
            s2_rate=100.0,
            s2_passed=5,
            s2_total=5,
            thresholds=[
                ThresholdResult(
                    name="S1", threshold=100, actual=100, passed=True, detail="5/5 passed"
                ),
            ],
        )
        md = render_check_summary(cr)
        assert "✅ PASS" in md
        assert "S1" in md

    def test_fail_output(self):
        cr = CheckResult(
            current_runs=1,
            baseline_runs=0,
            overall_rate=50.0,
            s1_rate=0.0,
            s1_passed=0,
            s1_total=2,
            s2_rate=100.0,
            s2_passed=1,
            s2_total=1,
            thresholds=[
                ThresholdResult(
                    name="S1", threshold=100, actual=0, passed=False, detail="0/2 passed"
                ),
            ],
        )
        md = render_check_summary(cr)
        assert "❌ FAIL" in md
        assert "0/2" in md

    def test_regressions_section(self):
        cr = CheckResult(
            current_runs=1,
            baseline_runs=1,
            overall_rate=50.0,
            s1_rate=0.0,
            s1_passed=0,
            s1_total=1,
            s2_rate=100.0,
            s2_passed=1,
            s2_total=1,
            thresholds=[],
            top_regressions=[
                {
                    "case_id": "TC001",
                    "severity": "S1",
                    "baseline_rate": 100.0,
                    "current_rate": 0.0,
                    "delta": -100.0,
                    "failure_types": ["bad_json"],
                    "category": "api",
                }
            ],
        )
        md = render_check_summary(cr)
        assert "Top Regressions" in md
        assert "TC001" in md
        assert "bad_json" in md


# ========================================================================
# CLI integration – check_gate()
# ========================================================================


class TestCheckGateIntegration:
    def test_exit_0_all_pass(self, tmp_path: Path):
        log_dir = _setup_jsonl(
            tmp_path,
            [
                _make_record(severity="S1", passed=True),
                _make_record(severity="S2", passed=True, case_id="TC002"),
            ],
        )
        assert check_gate(log_dir=str(log_dir), days=1) == 0

    def test_exit_1_s1_failure(self, tmp_path: Path):
        log_dir = _setup_jsonl(
            tmp_path,
            [
                _make_record(severity="S1", passed=False),
            ],
        )
        assert check_gate(log_dir=str(log_dir), days=1) == 1

    def test_exit_1_no_data(self, tmp_path: Path):
        empty = tmp_path / "empty"
        empty.mkdir()
        assert check_gate(log_dir=str(empty), days=1) == 1

    def test_write_summary(self, tmp_path: Path, monkeypatch):
        log_dir = _setup_jsonl(
            tmp_path,
            [
                _make_record(severity="S1", passed=True),
            ],
        )
        summary_file = tmp_path / "summary.md"
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))
        rc = check_gate(log_dir=str(log_dir), days=1, write_summary=True)
        assert rc == 0
        content = summary_file.read_text(encoding="utf-8")
        assert "AgentReg Gate Check" in content
        assert "✅ PASS" in content

    def test_verbose_flag(self, tmp_path: Path, capsys):
        log_dir = _setup_jsonl(
            tmp_path,
            [
                _make_record(severity="S2", passed=True),
            ],
        )
        check_gate(log_dir=str(log_dir), days=1, verbose=True)
        captured = capsys.readouterr()
        assert "Gate check:" in captured.out

    def test_output_file_written(self, tmp_path: Path):
        """--output-file writes Markdown to disk for PR comments."""
        log_dir = _setup_jsonl(
            tmp_path,
            [
                _make_record(severity="S1", passed=True),
                _make_record(severity="S2", passed=True, case_id="TC002"),
            ],
        )
        out_file = tmp_path / "gate_summary.md"
        rc = check_gate(log_dir=str(log_dir), days=1, output_file=str(out_file))
        assert rc == 0
        content = out_file.read_text(encoding="utf-8")
        assert "AgentReg Gate Check" in content
        assert "✅ PASS" in content

    def test_output_file_on_failure(self, tmp_path: Path):
        """--output-file is written even when gate fails."""
        log_dir = _setup_jsonl(
            tmp_path,
            [
                _make_record(severity="S1", passed=False, failure_type="bad_json"),
            ],
        )
        out_file = tmp_path / "sub" / "gate_summary.md"
        rc = check_gate(log_dir=str(log_dir), days=1, output_file=str(out_file))
        assert rc == 1
        content = out_file.read_text(encoding="utf-8")
        assert "❌ FAIL" in content


# ========================================================================
# P1: Config integration
# ========================================================================


class TestConfigIntegration:
    """Tests for YAML config driving thresholds in run_check / check_gate."""

    def _write_config(self, tmp_path: Path, content: str) -> Path:
        p = tmp_path / ".agentreg.yml"
        p.write_text(content, encoding="utf-8")
        return p

    def test_config_thresholds_apply(self, tmp_path: Path):
        """Config with overall_pass_rate=50 makes 1/2 pass → gate pass."""
        from agentops.config import load_config

        log_dir = _setup_jsonl(
            tmp_path,
            [
                _make_record(case_id="TC001", severity="S2", passed=True),
                _make_record(case_id="TC002", severity="S2", passed=False),
            ],
        )
        cfg_path = self._write_config(
            tmp_path,
            """\
thresholds:
  s1_pass_rate: 100
  overall_pass_rate: 50
""",
        )
        cfg = load_config(str(cfg_path))
        result = run_check(log_dir=str(log_dir), days=1, config=cfg)
        assert result.gate_passed is True

    def test_cli_overrides_config(self, tmp_path: Path):
        """Explicit --overall-threshold=90 overrides config's 50."""
        from agentops.config import load_config

        log_dir = _setup_jsonl(
            tmp_path,
            [
                _make_record(case_id="TC001", severity="S2", passed=True),
                _make_record(case_id="TC002", severity="S2", passed=False),
            ],
        )
        cfg_path = self._write_config(
            tmp_path,
            """\
thresholds:
  overall_pass_rate: 50
""",
        )
        cfg = load_config(str(cfg_path))
        result = run_check(log_dir=str(log_dir), days=1, config=cfg, overall_threshold=90.0)
        assert result.gate_passed is False

    def test_label_rule_override(self, tmp_path: Path):
        """Hotfix label rule raises overall threshold → gate fails."""
        from agentops.config import load_config

        log_dir = _setup_jsonl(
            tmp_path,
            [
                _make_record(case_id="TC001", severity="S2", passed=True),
                _make_record(case_id="TC002", severity="S2", passed=False),
            ],
        )
        cfg_path = self._write_config(
            tmp_path,
            """\
thresholds:
  overall_pass_rate: 40
rules:
  - name: hotfix
    match:
      labels: ["hotfix"]
    thresholds:
      overall_pass_rate: 90
""",
        )
        cfg = load_config(str(cfg_path))
        # Without label → 50% >= 40% → pass
        result_no_label = run_check(log_dir=str(log_dir), days=1, config=cfg)
        assert result_no_label.gate_passed is True

        # With hotfix label → 50% < 90% → fail
        result_hotfix = run_check(
            log_dir=str(log_dir),
            days=1,
            config=cfg,
            labels=["hotfix"],
        )
        assert result_hotfix.gate_passed is False


# ========================================================================
# P1: Per-case min_pass_rate
# ========================================================================


class TestCaseMinPassRate:
    """Tests for per-case min_pass_rate from CSV."""

    def _write_cases(self, tmp_path: Path, rows: list) -> Path:
        import csv

        p = tmp_path / "cases.csv"
        with open(p, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "case_id",
                    "name",
                    "input_prompt",
                    "expected_output",
                    "category",
                    "severity",
                    "owner",
                    "tags",
                    "min_pass_rate",
                ],
            )
            writer.writeheader()
            writer.writerows(rows)
        return p

    def test_case_threshold_pass(self, tmp_path: Path):
        log_dir = _setup_jsonl(
            tmp_path,
            [
                _make_record(case_id="TC001", severity="S1", passed=True),
            ],
        )
        cases_file = self._write_cases(
            tmp_path,
            [
                {
                    "case_id": "TC001",
                    "name": "Test",
                    "input_prompt": "Hi",
                    "expected_output": "",
                    "category": "api",
                    "severity": "S1",
                    "owner": "team-a",
                    "tags": "core",
                    "min_pass_rate": "100",
                },
            ],
        )
        result = run_check(log_dir=str(log_dir), days=1, cases_file=str(cases_file))
        assert result.gate_passed is True
        assert len(result.case_thresholds) == 1
        assert result.case_thresholds[0].passed is True

    def test_case_threshold_fail(self, tmp_path: Path):
        log_dir = _setup_jsonl(
            tmp_path,
            [
                _make_record(case_id="TC001", severity="S1", passed=False),
            ],
        )
        cases_file = self._write_cases(
            tmp_path,
            [
                {
                    "case_id": "TC001",
                    "name": "Test",
                    "input_prompt": "Hi",
                    "expected_output": "",
                    "category": "api",
                    "severity": "S1",
                    "owner": "team-a",
                    "tags": "core",
                    "min_pass_rate": "100",
                },
            ],
        )
        result = run_check(
            log_dir=str(log_dir),
            days=1,
            cases_file=str(cases_file),
            s1_threshold=0.0,
            overall_threshold=0.0,
        )
        # Gate fails due to per-case threshold even though S1/overall thresholds are 0
        assert result.gate_passed is False
        assert len(result.case_thresholds) == 1
        assert result.case_thresholds[0].passed is False

    def test_case_without_min_rate_is_skipped(self, tmp_path: Path):
        log_dir = _setup_jsonl(
            tmp_path,
            [
                _make_record(case_id="TC001", severity="S2", passed=False),
            ],
        )
        cases_file = self._write_cases(
            tmp_path,
            [
                {
                    "case_id": "TC001",
                    "name": "Test",
                    "input_prompt": "Hi",
                    "expected_output": "",
                    "category": "api",
                    "severity": "S2",
                    "owner": "",
                    "tags": "",
                    "min_pass_rate": "",
                },
            ],
        )
        result = run_check(
            log_dir=str(log_dir),
            days=1,
            cases_file=str(cases_file),
            s1_threshold=0.0,
            overall_threshold=0.0,
        )
        assert len(result.case_thresholds) == 0
        assert result.gate_passed is True

    def test_no_cases_file_no_case_thresholds(self, tmp_path: Path):
        log_dir = _setup_jsonl(
            tmp_path,
            [
                _make_record(case_id="TC001", severity="S1", passed=True),
            ],
        )
        result = run_check(log_dir=str(log_dir), days=1)
        assert result.case_thresholds == []

    def test_render_includes_case_violations(self, tmp_path: Path):
        """render_check_summary includes case threshold violations section."""
        cr = CheckResult(
            current_runs=1,
            baseline_runs=0,
            overall_rate=100.0,
            s1_rate=100.0,
            s1_passed=1,
            s1_total=1,
            s2_rate=0.0,
            s2_passed=0,
            s2_total=0,
            thresholds=[],
            case_thresholds=[
                ThresholdResult(
                    name="Case TC042",
                    threshold=100.0,
                    actual=0.0,
                    passed=False,
                    detail="min_pass_rate=100%",
                ),
            ],
        )
        md = render_check_summary(cr)
        assert "Case Threshold Violations" in md
        assert "TC042" in md


# ========================================================================
# P1: check_gate CLI integration with config
# ========================================================================


class TestCheckGateConfigCLI:
    def test_config_path_passed(self, tmp_path: Path):
        """--config is forwarded to run_check."""
        log_dir = _setup_jsonl(
            tmp_path,
            [
                _make_record(severity="S2", passed=True),
                _make_record(severity="S2", passed=False, case_id="TC002"),
            ],
        )
        cfg_path = tmp_path / ".agentreg.yml"
        cfg_path.write_text("thresholds:\n  overall_pass_rate: 40\n", encoding="utf-8")
        rc = check_gate(log_dir=str(log_dir), days=1, config_path=str(cfg_path))
        assert rc == 0  # 50% >= 40%

    def test_labels_comma_separated(self, tmp_path: Path):
        """--labels hotfix,urgent parses into list."""
        log_dir = _setup_jsonl(
            tmp_path,
            [
                _make_record(severity="S2", passed=True),
            ],
        )
        cfg_path = tmp_path / ".agentreg.yml"
        cfg_path.write_text(
            """\
thresholds:
  overall_pass_rate: 50
rules:
  - name: strict
    match:
      labels: ["hotfix"]
    thresholds:
      overall_pass_rate: 200
""",
            encoding="utf-8",
        )
        # With hotfix label → threshold becomes 200% → always fails
        rc = check_gate(
            log_dir=str(log_dir),
            days=1,
            config_path=str(cfg_path),
            labels="hotfix,urgent",
        )
        assert rc == 1

    def test_cases_file_passed(self, tmp_path: Path):
        """--cases-file triggers per-case checks."""
        import csv

        log_dir = _setup_jsonl(
            tmp_path,
            [
                _make_record(case_id="TC001", severity="S1", passed=True),
            ],
        )
        cases_file = tmp_path / "cases.csv"
        with open(cases_file, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "case_id",
                    "name",
                    "input_prompt",
                    "expected_output",
                    "category",
                    "severity",
                    "min_pass_rate",
                ],
            )
            w.writeheader()
            w.writerow(
                {
                    "case_id": "TC001",
                    "name": "Test",
                    "input_prompt": "Hi",
                    "expected_output": "",
                    "category": "api",
                    "severity": "S1",
                    "min_pass_rate": "100",
                }
            )
        rc = check_gate(log_dir=str(log_dir), days=1, cases_file=str(cases_file))
        assert rc == 0

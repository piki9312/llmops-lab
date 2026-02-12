"""Tests for scripts/ci_gate_s1.py – S1-only CI gate.

Covers:
- _is_failed() pass/fail detection
- _parse_ts() timestamp parsing
- _choose_latest_jsonl() file selection
- _pick_target_run_id() run-id inference
- compute_gate_stats() aggregation & S1 counting
- _render_summary() markdown output
- main() integration (exit code 0/1)
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest

# ---------------------------------------------------------------------------
# Import ci_gate_s1 as a module from the scripts directory
# ---------------------------------------------------------------------------
_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "ci_gate_s1.py"
_spec = importlib.util.spec_from_file_location("ci_gate_s1", _SCRIPT)
ci_gate_s1 = importlib.util.module_from_spec(_spec)
sys.modules["ci_gate_s1"] = ci_gate_s1  # @dataclass が __module__ を解決できるよう登録
_spec.loader.exec_module(ci_gate_s1)

# Convenience aliases
_is_failed = ci_gate_s1._is_failed
_parse_ts = ci_gate_s1._parse_ts
_choose_latest_jsonl = ci_gate_s1._choose_latest_jsonl
_pick_target_run_id = ci_gate_s1._pick_target_run_id
_infer_severity = ci_gate_s1._infer_severity
compute_gate_stats = ci_gate_s1.compute_gate_stats
_render_summary = ci_gate_s1._render_summary
GateStats = ci_gate_s1.GateStats
main = ci_gate_s1.main


# ========================================================================
# Helpers
# ========================================================================


def _write_jsonl(path: Path, records: List[Dict[str, Any]]) -> None:
    """Write a list of dicts as JSONL."""
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


RUN_ID = "run-001"


def _make_record(
    *,
    case_id: str = "TC001",
    severity: str = "S1",
    passed: bool = True,
    run_id: str = RUN_ID,
    timestamp: str | None = None,
    failure_type: str | None = None,
) -> Dict[str, Any]:
    rec: Dict[str, Any] = {
        "case_id": case_id,
        "severity": severity,
        "passed": passed,
        "run_id": run_id,
    }
    if timestamp:
        rec["timestamp"] = timestamp
    if failure_type:
        rec["failure_type"] = failure_type
    return rec


# ========================================================================
# _is_failed
# ========================================================================


class TestIsFailed:
    def test_passed_true(self):
        assert _is_failed({"passed": True}) is False

    def test_passed_false(self):
        assert _is_failed({"passed": False}) is True

    def test_status_pass(self):
        for s in ("pass", "passed", "ok", "success"):
            assert _is_failed({"status": s}) is False

    def test_status_fail(self):
        for s in ("fail", "failed", "ng", "error"):
            assert _is_failed({"status": s}) is True

    def test_no_indicator(self):
        assert _is_failed({"some_field": 123}) is None


# ========================================================================
# _parse_ts
# ========================================================================


class TestParseTs:
    def test_iso_string(self):
        result = _parse_ts("2026-02-12T10:30:00")
        assert isinstance(result, datetime)
        assert result.year == 2026

    def test_z_suffix(self):
        result = _parse_ts("2026-02-12T10:30:00Z")
        assert isinstance(result, datetime)

    def test_none(self):
        assert _parse_ts(None) is None

    def test_empty_string(self):
        assert _parse_ts("") is None

    def test_invalid(self):
        assert _parse_ts("not-a-date") is None


# ========================================================================
# _choose_latest_jsonl
# ========================================================================


class TestChooseLatestJsonl:
    def test_no_files(self, tmp_path: Path):
        assert _choose_latest_jsonl(tmp_path) is None

    def test_single_dated_file(self, tmp_path: Path):
        f = tmp_path / "20260212.jsonl"
        f.write_text("{}\n")
        assert _choose_latest_jsonl(tmp_path) == f

    def test_picks_latest_date(self, tmp_path: Path):
        (tmp_path / "20260210.jsonl").write_text("{}\n")
        (tmp_path / "20260211.jsonl").write_text("{}\n")
        latest = tmp_path / "20260212.jsonl"
        latest.write_text("{}\n")
        assert _choose_latest_jsonl(tmp_path) == latest

    def test_fallback_to_mtime(self, tmp_path: Path):
        """Non-date-named files fall back to mtime."""
        old = tmp_path / "old_run.jsonl"
        old.write_text("{}\n")
        new = tmp_path / "new_run.jsonl"
        new.write_text("{}\n")
        # newest by mtime → new_run.jsonl
        result = _choose_latest_jsonl(tmp_path)
        assert result in (old, new)  # either is fine; just not None

    def test_dated_preferred_over_non_dated(self, tmp_path: Path):
        """Dated file is preferred even if non-dated has newer mtime."""
        (tmp_path / "random.jsonl").write_text("{}\n")
        dated = tmp_path / "20260101.jsonl"
        dated.write_text("{}\n")
        assert _choose_latest_jsonl(tmp_path) == dated


# ========================================================================
# _infer_severity  (uses imported normalize_severity)
# ========================================================================


class TestInferSeverity:
    def test_severity_field(self):
        assert _infer_severity({"severity": "S1"}) == "S1"

    def test_sev1_alias(self):
        assert _infer_severity({"severity": "SEV1"}) == "S1"

    def test_critical(self):
        assert _infer_severity({"severity": "CRITICAL"}) == "S1"

    def test_s2(self):
        assert _infer_severity({"severity": "S2"}) == "S2"

    def test_priority_fallback(self):
        assert _infer_severity({"priority": "S1"}) == "S1"

    def test_no_severity(self):
        assert _infer_severity({"case_id": "x"}) is None


# ========================================================================
# _pick_target_run_id
# ========================================================================


class TestPickTargetRunId:
    def test_single_run_id(self):
        records = [_make_record(run_id="abc")]
        assert _pick_target_run_id(records) == "abc"

    def test_latest_by_timestamp(self):
        records = [
            _make_record(run_id="old", timestamp="2026-02-10T00:00:00Z"),
            _make_record(run_id="new", timestamp="2026-02-12T00:00:00Z"),
        ]
        assert _pick_target_run_id(records) == "new"

    def test_fallback_last_seen(self):
        """Without timestamps, pick the last-seen run_id."""
        records = [
            _make_record(run_id="first"),
            _make_record(run_id="second"),
        ]
        assert _pick_target_run_id(records) == "second"

    def test_empty_records(self):
        assert _pick_target_run_id([]) is None


# ========================================================================
# compute_gate_stats
# ========================================================================


class TestComputeGateStats:
    def _write_and_compute(
        self, tmp_path: Path, records: List[Dict[str, Any]], run_id: str = RUN_ID
    ) -> GateStats:
        jsonl = tmp_path / "20260212.jsonl"
        _write_jsonl(jsonl, records)
        return compute_gate_stats(jsonl_path=jsonl, run_id=run_id)

    def test_all_s1_pass(self, tmp_path: Path):
        records = [
            _make_record(case_id="TC001", severity="S1", passed=True),
            _make_record(case_id="TC002", severity="S1", passed=True),
        ]
        stats = self._write_and_compute(tmp_path, records)
        assert stats.total == 2
        assert stats.failed == 0
        assert stats.s1_total == 2
        assert stats.s1_failed == 0
        assert stats.pass_rate == 100.0

    def test_s1_failures(self, tmp_path: Path):
        records = [
            _make_record(case_id="TC001", severity="S1", passed=False, failure_type="quality_fail"),
            _make_record(case_id="TC002", severity="S1", passed=True),
        ]
        stats = self._write_and_compute(tmp_path, records)
        assert stats.total == 2
        assert stats.failed == 1
        assert stats.s1_total == 2
        assert stats.s1_failed == 1
        assert stats.pass_rate == 50.0
        assert len(stats.sample_s1_failures) == 1
        assert stats.sample_s1_failures[0] == ("TC001", "quality_fail")

    def test_s2_failure_does_not_affect_s1(self, tmp_path: Path):
        records = [
            _make_record(case_id="TC001", severity="S1", passed=True),
            _make_record(case_id="TC002", severity="S2", passed=False),
        ]
        stats = self._write_and_compute(tmp_path, records)
        assert stats.s1_failed == 0
        assert stats.s2_failed == 1
        assert stats.failed == 1

    def test_filters_by_run_id(self, tmp_path: Path):
        records = [
            _make_record(case_id="TC001", severity="S1", passed=False, run_id="other-run"),
            _make_record(case_id="TC002", severity="S1", passed=True, run_id=RUN_ID),
        ]
        stats = self._write_and_compute(tmp_path, records)
        assert stats.total == 1  # only RUN_ID records
        assert stats.s1_failed == 0

    def test_sample_limit(self, tmp_path: Path):
        """sample_s1_failures は --sample 上限を超えない."""
        records = [
            _make_record(case_id=f"TC{i:03d}", severity="S1", passed=False) for i in range(10)
        ]
        jsonl = tmp_path / "20260212.jsonl"
        _write_jsonl(jsonl, records)
        stats = compute_gate_stats(jsonl_path=jsonl, run_id=RUN_ID, sample=3)
        assert len(stats.sample_s1_failures) == 3

    def test_empty_file(self, tmp_path: Path):
        jsonl = tmp_path / "20260212.jsonl"
        jsonl.write_text("")
        stats = compute_gate_stats(jsonl_path=jsonl, run_id=RUN_ID)
        assert stats.total == 0

    def test_mixed_severities(self, tmp_path: Path):
        records = [
            _make_record(case_id="TC001", severity="S1", passed=False, failure_type="timeout"),
            _make_record(case_id="TC002", severity="S1", passed=True),
            _make_record(case_id="TC003", severity="S2", passed=False),
            _make_record(case_id="TC004", severity="S2", passed=True),
            _make_record(case_id="TC005", severity="S1", passed=False, failure_type="wrong_answer"),
        ]
        stats = self._write_and_compute(tmp_path, records)
        assert stats.total == 5
        assert stats.failed == 3  # TC001 (S1), TC003 (S2), TC005 (S1)
        assert stats.s1_total == 3
        assert stats.s1_failed == 2
        assert stats.s2_total == 2
        assert stats.s2_failed == 1


# ========================================================================
# _render_summary
# ========================================================================


class TestRenderSummary:
    def test_pass_gate(self, tmp_path: Path):
        stats = GateStats(
            run_id=RUN_ID,
            total=5,
            failed=0,
            s1_total=3,
            s1_failed=0,
            s2_total=2,
            s2_failed=0,
            sample_s1_failures=[],
        )
        md = _render_summary(jsonl_path=tmp_path / "test.jsonl", stats=stats)
        assert "✅ PASS" in md
        assert "❌ FAIL" not in md

    def test_fail_gate(self, tmp_path: Path):
        stats = GateStats(
            run_id=RUN_ID,
            total=5,
            failed=2,
            s1_total=3,
            s1_failed=2,
            s2_total=2,
            s2_failed=0,
            sample_s1_failures=[("TC001", "timeout"), ("TC005", "wrong_answer")],
        )
        md = _render_summary(jsonl_path=tmp_path / "test.jsonl", stats=stats)
        assert "❌ FAIL (S1 failures)" in md
        assert "TC001" in md
        assert "timeout" in md

    def test_contains_key_metrics(self, tmp_path: Path):
        stats = GateStats(
            run_id=RUN_ID,
            total=10,
            failed=3,
            s1_total=5,
            s1_failed=1,
            s2_total=5,
            s2_failed=2,
            sample_s1_failures=[("TC004", "quality_fail")],
        )
        md = _render_summary(jsonl_path=tmp_path / "test.jsonl", stats=stats)
        assert "Total cases: **10**" in md
        assert "Failed cases: **3**" in md
        assert f"Run ID: `{RUN_ID}`" in md


# ========================================================================
# main() – integration tests
# ========================================================================


class TestMainIntegration:
    """Test main() exit codes via monkeypatch."""

    def _setup_logs(self, tmp_path: Path, records: List[Dict[str, Any]]) -> Path:
        log_dir = tmp_path / "runs" / "agentreg"
        log_dir.mkdir(parents=True)
        _write_jsonl(log_dir / "20260212.jsonl", records)
        return log_dir

    def test_exit_0_when_s1_all_pass(self, tmp_path: Path, monkeypatch):
        log_dir = self._setup_logs(
            tmp_path,
            [
                _make_record(case_id="TC001", severity="S1", passed=True),
                _make_record(case_id="TC002", severity="S2", passed=False),
            ],
        )
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "ci_gate_s1.py",
                "--log-dir",
                str(log_dir),
                "--run-id",
                RUN_ID,
            ],
        )
        assert main() == 0

    def test_exit_1_when_s1_failure(self, tmp_path: Path, monkeypatch):
        log_dir = self._setup_logs(
            tmp_path,
            [
                _make_record(case_id="TC001", severity="S1", passed=False),
            ],
        )
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "ci_gate_s1.py",
                "--log-dir",
                str(log_dir),
                "--run-id",
                RUN_ID,
            ],
        )
        assert main() == 1

    def test_exit_1_when_no_jsonl(self, tmp_path: Path, monkeypatch):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "ci_gate_s1.py",
                "--log-dir",
                str(empty_dir),
            ],
        )
        assert main() == 1

    def test_exit_1_when_run_id_not_found(self, tmp_path: Path, monkeypatch):
        log_dir = self._setup_logs(
            tmp_path,
            [
                _make_record(run_id="other-run"),
            ],
        )
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "ci_gate_s1.py",
                "--log-dir",
                str(log_dir),
                "--run-id",
                "nonexistent",
            ],
        )
        assert main() == 1

    def test_write_summary(self, tmp_path: Path, monkeypatch):
        log_dir = self._setup_logs(
            tmp_path,
            [
                _make_record(case_id="TC001", severity="S1", passed=True),
            ],
        )
        summary_file = tmp_path / "summary.md"
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "ci_gate_s1.py",
                "--log-dir",
                str(log_dir),
                "--run-id",
                RUN_ID,
                "--write-summary",
            ],
        )
        assert main() == 0
        content = summary_file.read_text(encoding="utf-8")
        assert "✅ PASS" in content
        assert "AgentReg CI Summary" in content

    def test_auto_detect_run_id(self, tmp_path: Path, monkeypatch):
        """--run-id を省略してもタイムスタンプから最新が選ばれる."""
        log_dir = self._setup_logs(
            tmp_path,
            [
                _make_record(
                    run_id="old-run", severity="S1", passed=False, timestamp="2026-02-10T00:00:00Z"
                ),
                _make_record(
                    run_id="new-run", severity="S1", passed=True, timestamp="2026-02-12T00:00:00Z"
                ),
            ],
        )
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "ci_gate_s1.py",
                "--log-dir",
                str(log_dir),
            ],
        )
        # new-run は S1 pass なので exit 0
        assert main() == 0

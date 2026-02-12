"""Gate check: compare current period against baseline and enforce thresholds.

Usage (CLI)::

    python -m agentops check --log-dir runs/agentreg \\
        --days 1 --baseline-days 7 \\
        --s1-threshold 100 --overall-threshold 80

Exit codes:
  0  All thresholds met
  1  At least one threshold violated (or no data found)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .aggregate import severity_pass_rate
from .analyze import compute_pass_rate_delta, compute_top_regressions
from .report_weekly import WeeklyReporter


# ------------------------------------------------------------------
# Data structures
# ------------------------------------------------------------------

@dataclass
class ThresholdResult:
    """Outcome of a single threshold check."""

    name: str
    threshold: float
    actual: float
    passed: bool
    detail: str = ""


@dataclass
class CheckResult:
    """Aggregate outcome of the ``check`` command."""

    current_runs: int
    baseline_runs: int
    overall_rate: float
    s1_rate: float
    s1_passed: int
    s1_total: int
    s2_rate: float
    s2_passed: int
    s2_total: int
    thresholds: List[ThresholdResult] = field(default_factory=list)
    top_regressions: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def gate_passed(self) -> bool:
        return all(t.passed for t in self.thresholds)


# ------------------------------------------------------------------
# Core logic
# ------------------------------------------------------------------

def run_check(
    *,
    log_dir: str = "runs/agentreg",
    days: int = 1,
    baseline_days: int = 7,
    baseline_dir: Optional[str] = None,
    s1_threshold: float = 100.0,
    overall_threshold: float = 80.0,
    top_n: int = 5,
) -> CheckResult:
    """Load JSONL, compute metrics, evaluate thresholds.

    When *baseline_dir* is given the baseline is loaded from that directory
    (all JSONL files, no date filter) instead of the trailing window inside
    *log_dir*.  This is the recommended pattern for PR runs that download
    the ``agentreg-baseline`` artifact produced by the latest main build.

    Returns a :class:`CheckResult` regardless of pass/fail so the caller
    can render output before deciding the exit code.
    """

    end_date = datetime.now()
    current_start = end_date - timedelta(days=days)

    reporter = WeeklyReporter()
    current_reports = reporter.load_from_jsonl(
        log_dir=log_dir, start_date=current_start, end_date=end_date,
    )

    if baseline_dir:
        # Load ALL JSONL from the baseline directory (artifact from main).
        baseline_reports = reporter.load_from_jsonl(log_dir=baseline_dir)
    else:
        # Fallback: trailing window inside the same log_dir.
        baseline_end = current_start - timedelta(days=1)
        baseline_start = baseline_end - timedelta(days=baseline_days)
        baseline_reports = reporter.load_from_jsonl(
            log_dir=log_dir, start_date=baseline_start, end_date=baseline_end,
        )

    # Flatten results across runs
    current_results = [r for rpt in current_reports for r in rpt.results]
    baseline_results = [r for rpt in baseline_reports for r in rpt.results]

    # Pass rates
    total = len(current_results)
    passed = sum(1 for r in current_results if r.passed)
    overall_rate = (passed / total * 100) if total else 0.0

    s1_stats = severity_pass_rate(current_results, "S1")  # (rate, passed, total)
    s2_stats = severity_pass_rate(current_results, "S2")

    # Top regressions (only when baseline exists)
    top_regs: List[Dict[str, Any]] = []
    if baseline_results:
        top_regs = compute_top_regressions(
            current_results, baseline_results, top_n=top_n,
        )

    # Threshold evaluation
    thresholds: List[ThresholdResult] = []

    # S1 threshold
    if s1_stats[2] > 0:
        thresholds.append(ThresholdResult(
            name="S1 pass rate",
            threshold=s1_threshold,
            actual=s1_stats[0],
            passed=s1_stats[0] >= s1_threshold,
            detail=f"{s1_stats[1]}/{s1_stats[2]} passed",
        ))
    else:
        thresholds.append(ThresholdResult(
            name="S1 pass rate",
            threshold=s1_threshold,
            actual=0.0,
            passed=True,
            detail="no S1 cases (skip)",
        ))

    # Overall threshold
    thresholds.append(ThresholdResult(
        name="Overall pass rate",
        threshold=overall_threshold,
        actual=overall_rate,
        passed=overall_rate >= overall_threshold,
        detail=f"{passed}/{total} passed",
    ))

    return CheckResult(
        current_runs=len(current_reports),
        baseline_runs=len(baseline_reports),
        overall_rate=overall_rate,
        s1_rate=s1_stats[0],
        s1_passed=s1_stats[1],
        s1_total=s1_stats[2],
        s2_rate=s2_stats[0],
        s2_passed=s2_stats[1],
        s2_total=s2_stats[2],
        thresholds=thresholds,
        top_regressions=top_regs,
    )


# ------------------------------------------------------------------
# Markdown rendering
# ------------------------------------------------------------------

def render_check_summary(result: CheckResult) -> str:
    """Render a Markdown summary suitable for ``$GITHUB_STEP_SUMMARY``."""

    gate = "✅ PASS" if result.gate_passed else "❌ FAIL"
    lines = [
        "## AgentReg Gate Check",
        "",
        f"**Gate:** {gate}",
        "",
        "| Metric | Threshold | Actual | Result |",
        "|--------|-----------|--------|--------|",
    ]
    for t in result.thresholds:
        icon = "✅" if t.passed else "❌"
        lines.append(
            f"| {t.name} | {t.threshold:.1f}% | {t.actual:.2f}% | {icon} {t.detail} |"
        )

    lines += [
        "",
        f"- Current period runs: **{result.current_runs}**",
        f"- Baseline period runs: **{result.baseline_runs}**",
        f"- S1: **{result.s1_passed}/{result.s1_total}** ({result.s1_rate:.2f}%)",
        f"- S2: **{result.s2_passed}/{result.s2_total}** ({result.s2_rate:.2f}%)",
    ]

    if result.top_regressions:
        lines += ["", "### Top Regressions"]
        for reg in result.top_regressions:
            ft = ", ".join(reg["failure_types"]) if reg["failure_types"] else "—"
            lines.append(
                f"- **{reg['case_id']}** [{reg['severity']}] "
                f"{reg['baseline_rate']:.0f}% → {reg['current_rate']:.0f}% "
                f"(Δ {reg['delta']:+.1f}%) — {ft}"
            )

    return "\n".join(lines) + "\n"

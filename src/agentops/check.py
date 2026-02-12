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
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .aggregate import severity_pass_rate, compute_case_pass_rates
from .analyze import compute_pass_rate_delta, compute_top_regressions
from .config import AgentRegConfig, Thresholds, load_config
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
    case_thresholds: List[ThresholdResult] = field(default_factory=list)

    @property
    def gate_passed(self) -> bool:
        return (
            all(t.passed for t in self.thresholds)
            and all(t.passed for t in self.case_thresholds)
        )


# ------------------------------------------------------------------
# Core logic
# ------------------------------------------------------------------

def run_check(
    *,
    log_dir: str = "runs/agentreg",
    days: int = 1,
    baseline_days: int = 7,
    baseline_dir: Optional[str] = None,
    s1_threshold: Optional[float] = None,
    overall_threshold: Optional[float] = None,
    top_n: Optional[int] = None,
    config: Optional[AgentRegConfig] = None,
    labels: Sequence[str] = (),
    changed_files: Sequence[str] = (),
    cases_file: Optional[str] = None,
) -> CheckResult:
    """Load JSONL, compute metrics, evaluate thresholds.

    When *config* is given, thresholds are resolved from the YAML config
    (with *labels* / *changed_files* for rule matching).  Explicit
    ``s1_threshold`` / ``overall_threshold`` / ``top_n`` CLI flags
    **override** values from the config.

    When *cases_file* is given, per-case ``min_pass_rate`` metadata
    is read from the CSV and checked against actual per-case pass rates.

    When *baseline_dir* is given the baseline is loaded from that directory
    (all JSONL files, no date filter) instead of the trailing window inside
    *log_dir*.  This is the recommended pattern for PR runs that download
    the ``agentreg-baseline`` artifact produced by the latest main build.

    Returns a :class:`CheckResult` regardless of pass/fail so the caller
    can render output before deciding the exit code.
    """

    # --- Resolve effective thresholds from config + CLI overrides ------
    if config is None:
        config = AgentRegConfig()  # built-in defaults

    resolved = config.resolve_thresholds(
        labels=labels, changed_files=changed_files,
    )

    eff_s1 = s1_threshold if s1_threshold is not None else resolved.s1_pass_rate
    eff_overall = overall_threshold if overall_threshold is not None else resolved.overall_pass_rate
    eff_top_n = top_n if top_n is not None else resolved.top_n

    # --- Load JSONL ----------------------------------------------------
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
            current_results, baseline_results, top_n=eff_top_n,
        )

    # Threshold evaluation
    thresholds: List[ThresholdResult] = []

    # S1 threshold
    if s1_stats[2] > 0:
        thresholds.append(ThresholdResult(
            name="S1 pass rate",
            threshold=eff_s1,
            actual=s1_stats[0],
            passed=s1_stats[0] >= eff_s1,
            detail=f"{s1_stats[1]}/{s1_stats[2]} passed",
        ))
    else:
        thresholds.append(ThresholdResult(
            name="S1 pass rate",
            threshold=eff_s1,
            actual=0.0,
            passed=True,
            detail="no S1 cases (skip)",
        ))

    # Overall threshold
    thresholds.append(ThresholdResult(
        name="Overall pass rate",
        threshold=eff_overall,
        actual=overall_rate,
        passed=overall_rate >= eff_overall,
        detail=f"{passed}/{total} passed",
    ))

    # --- Per-case min_pass_rate checks --------------------------------
    case_thresholds: List[ThresholdResult] = []
    case_min_rates = _load_case_min_rates(cases_file)
    if case_min_rates and current_results:
        case_pass_rates = compute_case_pass_rates(current_results)
        for case_id, min_rate in sorted(case_min_rates.items()):
            actual_rate = case_pass_rates.get(case_id)
            if actual_rate is None:
                continue  # case not in current run
            actual_pct = actual_rate * 100
            case_thresholds.append(ThresholdResult(
                name=f"Case {case_id}",
                threshold=min_rate,
                actual=actual_pct,
                passed=actual_pct >= min_rate,
                detail=f"min_pass_rate={min_rate}%",
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
        case_thresholds=case_thresholds,
    )


# ------------------------------------------------------------------
# Per-case min_pass_rate loader
# ------------------------------------------------------------------

def _load_case_min_rates(cases_file: Optional[str]) -> Dict[str, float]:
    """Read ``min_pass_rate`` from a CSV cases file.

    Returns a mapping ``case_id → min_pass_rate`` (only for cases that
    have the column set).  Returns an empty dict when *cases_file* is
    ``None`` or the file lacks the column.
    """
    if not cases_file:
        return {}
    p = Path(cases_file)
    if not p.exists():
        return {}
    import csv
    result: Dict[str, float] = {}
    with open(p, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = row.get("case_id", "")
            raw = row.get("min_pass_rate", "")
            if cid and raw:
                try:
                    result[cid] = float(raw)
                except ValueError:
                    pass
    return result


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

    # Per-case min_pass_rate violations
    failed_cases = [t for t in result.case_thresholds if not t.passed]
    if failed_cases:
        lines += ["", "### Case Threshold Violations"]
        for t in failed_cases:
            lines.append(
                f"- **{t.name}**: {t.actual:.1f}% < {t.threshold:.0f}% ({t.detail})"
            )

    return "\n".join(lines) + "\n"

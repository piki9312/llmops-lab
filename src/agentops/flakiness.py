"""Flakiness (stability) detection from repeated runs.

When the same case is executed **N** times within the same analysis
window, this module computes per-case stability metrics and flags
flaky tests.

A case is considered **flaky** when it has both passes and failures
across repetitions (0 < fail_rate < 100%).

Usage::

    from agentops.flakiness import compute_flakiness, render_flakiness_report
    stats = compute_flakiness(results, min_runs=3)
    md = render_flakiness_report(stats)
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ------------------------------------------------------------------
# Data structures
# ------------------------------------------------------------------

@dataclass
class CaseStability:
    """Stability metrics for a single case across N repetitions."""

    case_id: str
    severity: str
    category: str
    total_runs: int
    passed_runs: int
    failed_runs: int
    pass_rate: float  # 0.0 – 100.0
    is_flaky: bool
    failure_types: List[str] = field(default_factory=list)
    latency_std: Optional[float] = None  # std dev of latency_ms
    latency_cv: Optional[float] = None   # coefficient of variation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "severity": self.severity,
            "category": self.category,
            "total_runs": self.total_runs,
            "passed_runs": self.passed_runs,
            "failed_runs": self.failed_runs,
            "pass_rate": self.pass_rate,
            "is_flaky": self.is_flaky,
            "failure_types": self.failure_types,
            "latency_std": self.latency_std,
            "latency_cv": self.latency_cv,
        }


# ------------------------------------------------------------------
# Core logic
# ------------------------------------------------------------------

def compute_flakiness(
    results: List,
    min_runs: int = 2,
) -> List[CaseStability]:
    """Compute per-case stability from a flat list of results.

    Parameters
    ----------
    results :
        Flat list of ``TestResult`` (may contain multiple runs of the
        same ``case_id``).
    min_runs :
        Minimum number of runs for a case to be analysed.
        Cases with fewer runs are omitted.

    Returns
    -------
    List of :class:`CaseStability` sorted by flakiness (flaky first,
    then by pass_rate ascending, then S1 first).
    """
    # Group by case_id
    by_case: Dict[str, List] = {}
    for r in results:
        by_case.setdefault(r.case_id, []).append(r)

    stats: List[CaseStability] = []
    for case_id, runs in by_case.items():
        if len(runs) < min_runs:
            continue

        sev = (runs[0].metrics or {}).get("severity", "S2")
        cat = (runs[0].metrics or {}).get("category", "unknown")

        passed = sum(1 for r in runs if r.passed)
        failed = len(runs) - passed
        rate = passed / len(runs) * 100

        # Flaky = not all-pass and not all-fail
        is_flaky = 0 < failed < len(runs)

        # Failure types
        ft_set: set = set()
        for r in runs:
            ft = getattr(r, "failure_type", None)
            if ft and not r.passed:
                ft_set.add(ft)

        # Latency variability
        latencies = [r.latency_ms for r in runs if r.latency_ms > 0]
        lat_std: Optional[float] = None
        lat_cv: Optional[float] = None
        if len(latencies) >= 2:
            lat_std = statistics.stdev(latencies)
            mean = statistics.mean(latencies)
            lat_cv = (lat_std / mean) if mean > 0 else None

        stats.append(CaseStability(
            case_id=case_id,
            severity=sev,
            category=cat,
            total_runs=len(runs),
            passed_runs=passed,
            failed_runs=failed,
            pass_rate=rate,
            is_flaky=is_flaky,
            failure_types=sorted(ft_set),
            latency_std=lat_std,
            latency_cv=lat_cv,
        ))

    # Sort: flaky first → low pass_rate → S1 first
    stats.sort(
        key=lambda s: (
            0 if s.is_flaky else 1,
            s.pass_rate,
            0 if s.severity == "S1" else 1,
        )
    )
    return stats


def flaky_cases(results: List, min_runs: int = 2) -> List[CaseStability]:
    """Convenience: return only flaky cases."""
    return [s for s in compute_flakiness(results, min_runs) if s.is_flaky]


# ------------------------------------------------------------------
# Markdown rendering
# ------------------------------------------------------------------

def render_flakiness_report(
    stats: List[CaseStability],
    flaky_only: bool = False,
) -> str:
    """Render stability metrics as a Markdown section.

    Parameters
    ----------
    stats :
        Output from :func:`compute_flakiness`.
    flaky_only :
        If True, only flaky cases are shown.
    """
    items = [s for s in stats if s.is_flaky] if flaky_only else stats
    if not items:
        return ""

    flaky_count = sum(1 for s in items if s.is_flaky)
    lines = [
        "### Stability Report",
        "",
        f"Analysed **{len(items)}** cases "
        f"({flaky_count} flaky 🎲)",
        "",
        "| Case | Sev | Runs | Pass Rate | Flaky | Failure Types | Latency CV |",
        "|------|-----|------|-----------|-------|---------------|------------|",
    ]
    for s in items:
        flaky_icon = "🎲" if s.is_flaky else "✅"
        ft = ", ".join(s.failure_types) if s.failure_types else "—"
        cv = f"{s.latency_cv:.2f}" if s.latency_cv is not None else "—"
        lines.append(
            f"| {s.case_id} | {s.severity} | {s.total_runs} | "
            f"{s.pass_rate:.0f}% ({s.passed_runs}/{s.total_runs}) | "
            f"{flaky_icon} | {ft} | {cv} |"
        )

    return "\n".join(lines) + "\n"

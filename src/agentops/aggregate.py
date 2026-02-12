"""
Aggregation utilities for Agent Regression weekly reports.

Computes pass rates, latency percentiles, cost metrics,
and failure breakdowns from test results.
"""

import math
from typing import Dict, List, Optional, Tuple


def compute_case_pass_rates(results: List) -> Dict[str, float]:
    """
    Compute pass rate for each case_id.

    Returns:
        Dict mapping case_id -> pass_rate (0.0 to 1.0)
    """
    case_stats: Dict[str, Tuple[int, int]] = {}  # case_id -> (passed, total)
    for result in results:
        case_id = result.case_id
        if case_id not in case_stats:
            case_stats[case_id] = (0, 0)
        passed, total = case_stats[case_id]
        passed += 1 if result.passed else 0
        total += 1
        case_stats[case_id] = (passed, total)

    return {
        case_id: (p / t if t > 0 else 0.0)
        for case_id, (p, t) in case_stats.items()
    }


def normalize_severity(value: Optional[str]) -> Optional[str]:
    """Normalize severity strings to canonical S1/S2."""
    if value is None:
        return None
    value = str(value).strip().upper()
    if value in {"S1", "SEV1", "1", "CRITICAL"}:
        return "S1"
    if value in {"S2", "SEV2", "2", "HIGH"}:
        return "S2"
    return None


def severity_pass_rate(results: List, severity: str) -> Tuple[float, int, int]:
    """
    Compute pass rate for a specific severity level.

    Returns:
        (rate_percent, passed_count, total_count)
    """
    filtered = [
        r for r in results
        if normalize_severity(
            (r.metrics or {}).get("severity")
            or (r.metrics or {}).get("priority")
            or (r.metrics or {}).get("tier")
        ) == severity
    ]
    total = len(filtered)
    passed = sum(1 for r in filtered if r.passed)
    rate = (passed / total * 100) if total else 0.0
    return rate, passed, total


def format_rate(stats: Tuple[float, int, int]) -> str:
    """Format a severity pass rate tuple as a display string."""
    rate, _, total = stats
    return f"{rate:.2f}%" if total > 0 else "N/A"


def percentile(values: List[float], pct: int) -> float:
    """Compute the given percentile from a list of values."""
    if not values:
        return 0.0
    values = sorted(values)
    index = max(0, math.ceil((pct / 100) * len(values)) - 1)
    return values[index]


def failure_type_of(result) -> str:
    """Determine the failure type string for a single result."""
    if result.passed:
        return "none"
    if result.failure_type:
        return result.failure_type
    if result.error:
        return str(result.error)
    return "empty_output"


def failure_breakdown(results: List) -> Dict[str, int]:
    """
    Count failures by type.

    Returns:
        Dict mapping failure_type -> count  (sorted descending)
    """
    breakdown: Dict[str, int] = {}
    for r in results:
        if r.passed:
            continue
        ft = failure_type_of(r)
        breakdown[ft] = breakdown.get(ft, 0) + 1
    return dict(sorted(breakdown.items(), key=lambda x: x[1], reverse=True))


def top_failures(results: List, limit: int = 10) -> List[Tuple[str, str, int, str]]:
    """
    Return top N failure (case_id, failure_type) pairs sorted by severity then count.

    Returns:
        List of (case_id, failure_type, count, suspected_cause)
    """
    counts: Dict[Tuple[str, str], int] = {}
    severity_map: Dict[Tuple[str, str], str] = {}
    for r in results:
        if r.passed:
            continue
        ft = failure_type_of(r)
        sev = (r.metrics or {}).get("severity", "S2")
        key = (r.case_id, ft)
        counts[key] = counts.get(key, 0) + 1
        severity_map[key] = sev

    sorted_items = sorted(
        counts.items(),
        key=lambda x: (
            0 if severity_map.get(x[0]) == "S1" else 1,
            -x[1],
        ),
    )[:limit]
    return [
        (case_id, ft, count, suspected_cause(ft))
        for (case_id, ft), count in sorted_items
    ]


def suspected_cause(failure_type: str) -> str:
    """Map a failure type to a suspected root cause category."""
    mapping = {
        "timeout": "インフラ/プロバイダ",
        "bad_json": "prompt/schema",
        "loop": "tool/routing",
        "policy_violation": "安全設計",
        "quality_fail": "prompt/エージェントロジック",
        "provider_error": "インフラ/プロバイダ",
        "rate_limited": "レート制限設定",
        "empty_output": "モデル出力/プロンプト",
    }
    return mapping.get(failure_type, "要調査")

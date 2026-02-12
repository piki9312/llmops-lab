"""
Regression analysis for Agent Regression weekly reports.

Computes week-over-week deltas, failure type changes,
worst regressions, overall status judgments, and next-action suggestions.
"""

from typing import Any, Dict, List, Optional, Tuple

from .aggregate import compute_case_pass_rates


def compute_pass_rate_delta(
    current_results: List,
    baseline_results: List,
    severity: Optional[str] = None,
) -> Tuple[float, float, float]:
    """
    Compute pass rate delta between current and baseline periods.

    Args:
        current_results: Results from current period.
        baseline_results: Results from baseline period.
        severity: Optional severity filter (``"S1"`` or ``"S2"``).

    Returns:
        ``(baseline_rate, current_rate, delta)`` as percentages.
    """
    if severity:
        current_results = [
            r for r in current_results if r.metrics.get("severity") == severity
        ]
        baseline_results = [
            r for r in baseline_results if r.metrics.get("severity") == severity
        ]

    if not current_results:
        return (0.0, 0.0, 0.0)

    baseline_rate = (
        sum(1 for r in baseline_results if r.passed) / len(baseline_results) * 100
        if baseline_results
        else 0.0
    )
    current_rate = sum(1 for r in current_results if r.passed) / len(current_results) * 100
    delta = current_rate - baseline_rate

    return (baseline_rate, current_rate, delta)


def compute_failure_type_delta(
    current_results: List,
    baseline_results: List,
) -> Dict[str, int]:
    """
    Compute failure type count deltas between current and baseline.

    Returns:
        Dict mapping ``failure_type -> count_delta``.
    """

    def _count(results):
        counts: Dict[str, int] = {}
        for r in results:
            if not r.passed and r.failure_type:
                counts[r.failure_type] = counts.get(r.failure_type, 0) + 1
        return counts

    cur = _count(current_results)
    base = _count(baseline_results)
    all_types = set(cur.keys()) | set(base.keys())
    return {ft: cur.get(ft, 0) - base.get(ft, 0) for ft in all_types}


def compute_top_regressions(
    current_results: List,
    baseline_results: List,
    top_n: int = 5,
) -> List[Dict[str, Any]]:
    """
    Identify top *N* regressions (largest pass-rate decrease).

    S1 cases are prioritised when deltas are tied.

    Returns:
        List of dicts with keys ``case_id``, ``severity``, ``category``,
        ``baseline_rate``, ``current_rate``, ``delta``, ``failure_types``.
    """
    current_rates = compute_case_pass_rates(current_results)
    baseline_rates = compute_case_pass_rates(baseline_results)

    case_info: Dict[str, Dict[str, str]] = {}
    for r in current_results + baseline_results:
        if r.case_id not in case_info:
            case_info[r.case_id] = {
                "severity": r.metrics.get("severity", "S2"),
                "category": r.metrics.get("category", "unknown"),
            }

    regressions: List[Dict[str, Any]] = []
    for case_id, current_rate in current_rates.items():
        baseline_rate = baseline_rates.get(case_id, 1.0)
        delta = current_rate - baseline_rate

        if delta <= 0:
            sev = case_info[case_id]["severity"]
            cat = case_info[case_id]["category"]
            case_failures = [
                r for r in current_results if r.case_id == case_id and not r.passed
            ]
            failure_types = [r.failure_type for r in case_failures if r.failure_type]

            regressions.append(
                {
                    "case_id": case_id,
                    "severity": sev,
                    "category": cat,
                    "baseline_rate": baseline_rate * 100,
                    "current_rate": current_rate * 100,
                    "delta": delta * 100,
                    "failure_types": failure_types,
                }
            )

    regressions.sort(
        key=lambda x: (
            x["delta"],
            -(1 if x["severity"] == "S1" else 0),
        )
    )
    return regressions[:top_n]


def worst_regression(
    results: List, prev_results: List
) -> Tuple[str, Optional[float]]:
    """
    Find the single worst regression between two periods.

    Returns:
        ``(description_str, delta_value_or_None)``
    """
    if not prev_results:
        return "N/A（先週データなし）", None

    def _rates(items):
        stats: Dict[str, List[bool]] = {}
        for r in items:
            stats.setdefault(r.case_id, []).append(r.passed)
        return {k: (sum(v) / len(v) * 100) for k, v in stats.items() if v}

    curr = _rates(results)
    prev = _rates(prev_results)
    deltas = [
        (cid, curr[cid] - prev[cid]) for cid in curr if cid in prev
    ]
    if not deltas:
        return "N/A（比較対象なし）", None

    case_id, delta = min(deltas, key=lambda x: x[1])
    return f"{case_id}（先週比 {delta:+.2f}%）", delta


def overall_status(
    overall_pass_rate: float,
    s1_pass_rate: float,
    s1_total: int,
    s2_pass_rate: float,
    s2_total: int,
    worst_delta: Optional[float],
) -> str:
    """Return an emoji+label status string for the weekly report."""
    s1_ok = (s1_pass_rate >= 98) if s1_total > 0 else True
    s2_ok = (s2_pass_rate >= 98) if s2_total > 0 else True
    if (
        overall_pass_rate >= 98
        and s1_ok
        and s2_ok
        and (worst_delta is None or worst_delta >= -1)
    ):
        return "✅安定"
    if (
        overall_pass_rate < 95
        or (s1_total > 0 and s1_pass_rate < 95)
        or (worst_delta is not None and worst_delta <= -5)
    ):
        return "🔥重大"
    return "⚠️注意"


def next_actions(
    fb: Dict[str, int],
    worst_reg: Tuple[str, Optional[float]],
) -> List[str]:
    """Suggest up to 3 next actions based on failures and regressions."""
    actions: List[str] = []
    priority = [
        ("timeout", "タイムアウト多発: インフラ/プロバイダの遅延調査"),
        ("bad_json", "JSON不正: prompt/schema の調整"),
        ("loop", "ループ発生: tool/routing の停止条件見直し"),
        ("policy_violation", "ポリシー違反: 安全設計ルールの再確認"),
        ("quality_fail", "品質低下: プロンプト/評価ロジック改善"),
        ("provider_error", "プロバイダ障害: リトライ/フォールバック見直し"),
    ]
    for key, action in priority:
        if key in fb and action not in actions:
            actions.append(action)
    if worst_reg[1] is not None:
        actions.append(f"最重要回帰: {worst_reg[0]} の原因調査")
    while len(actions) < 3:
        actions.append("回帰ケースの追加と閾値の再確認")
    return actions[:3]

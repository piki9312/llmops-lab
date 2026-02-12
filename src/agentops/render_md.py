"""
Markdown rendering for Agent Regression weekly reports.

Pure functions that take computed metrics and produce Markdown strings.
No I/O or data loading—only string assembly.
"""

from typing import Any, Dict, List, Optional, Tuple

from . import aggregate as agg
from . import analyze


def render_report(
    *,
    week_start_str: str,
    week_end_str: str,
    overall_status: str,
    s1_stats: Tuple[float, int, int],
    s2_stats: Tuple[float, int, int],
    s1_delta: Optional[float],
    s2_delta: Optional[float],
    worst_regression: Tuple[str, Optional[float]],
    next_actions: List[str],
    total_runs: int,
    overall_pass_rate: float,
    latency_p50: float,
    latency_p95: float,
    cost_per_task: float,
    failure_breakdown: Dict[str, int],
    top_failures: List[Tuple[str, str, int, str]],
    # Regression analysis (may be empty / None)
    all_results: Optional[List] = None,
    prev_results: Optional[List] = None,
    baseline_rate: Optional[float] = None,
    current_all_rate: Optional[float] = None,
    all_delta: Optional[float] = None,
    failure_type_delta: Optional[Dict[str, int]] = None,
    top_regressions: Optional[List[Dict[str, Any]]] = None,
    # Individual runs
    reports: Optional[List] = None,
) -> str:
    """Assemble the full weekly report as a Markdown string."""
    lines: List[str] = [
        "# Agent Regression Weekly Report",
        "",
        f"**Week:** {week_start_str} to {week_end_str}",
        "",
    ]

    # --- Week-over-Week Summary (only when baseline exists) ----
    if prev_results and all_results:
        lines.extend(
            _section_wow_summary(
                all_results, prev_results, baseline_rate, current_all_rate, all_delta
            )
        )

    # --- Executive Summary ---
    lines.extend(
        _section_executive(
            overall_status,
            s1_stats,
            s2_stats,
            s1_delta,
            s2_delta,
            worst_regression,
            next_actions,
        )
    )

    # --- Key Metrics ---
    lines.extend(
        _section_metrics(
            total_runs,
            overall_pass_rate,
            s1_stats,
            s2_stats,
            latency_p50,
            latency_p95,
            cost_per_task,
            failure_breakdown,
        )
    )

    # --- Failure Type Delta ---
    if failure_type_delta:
        lines.extend(_section_failure_delta(failure_type_delta))

    # --- Top Failures ---
    lines.extend(_section_top_failures(top_failures))

    # --- Top Regressions ---
    if top_regressions:
        lines.extend(_section_top_regressions(top_regressions))

    # --- Individual Runs ---
    if reports:
        lines.extend(_section_individual_runs(reports))

    return "\n".join(lines)


# ====================================================================
# Private section builders
# ====================================================================


def _section_wow_summary(
    all_results: List,
    prev_results: List,
    baseline_rate: Optional[float],
    current_all_rate: Optional[float],
    all_delta: Optional[float],
) -> List[str]:
    lines = [
        "## Week-over-Week Summary",
        "",
        f"- 全体成功率: {current_all_rate:.2f}% (前週: {baseline_rate:.2f}%) → **{all_delta:+.2f}%**",
    ]
    s1_bl, s1_cur, s1_del = analyze.compute_pass_rate_delta(all_results, prev_results, "S1")
    s2_bl, s2_cur, s2_del = analyze.compute_pass_rate_delta(all_results, prev_results, "S2")
    lines.extend(
        [
            f"- S1成功率: {s1_cur:.2f}% (前週: {s1_bl:.2f}%) → **{s1_del:+.2f}%**",
            f"- S2成功率: {s2_cur:.2f}% (前週: {s2_bl:.2f}%) → **{s2_del:+.2f}%**",
            "",
        ]
    )
    return lines


def _section_executive(
    status: str,
    s1_stats: Tuple[float, int, int],
    s2_stats: Tuple[float, int, int],
    s1_delta: Optional[float],
    s2_delta: Optional[float],
    worst_reg: Tuple[str, Optional[float]],
    actions: List[str],
) -> List[str]:
    return [
        "## Summary（上の人向け）",
        "",
        f"- 総合判定: {status}",
        f"- S1成功率: {agg.format_rate(s1_stats)}"
        + (f"（先週比 {s1_delta:+.2f}%）" if s1_delta is not None else "（先週比 N/A）"),
        f"- S2成功率: {agg.format_rate(s2_stats)}"
        + (f"（先週比 {s2_delta:+.2f}%）" if s2_delta is not None else "（先週比 N/A）"),
        f"- 一番重要な回帰: {worst_reg[0]}",
        "- 来週のアクション:",
        f"  - {actions[0]}",
        f"  - {actions[1]}",
        f"  - {actions[2]}",
        "",
    ]


def _section_metrics(
    total_runs: int,
    overall_pass_rate: float,
    s1_stats: Tuple[float, int, int],
    s2_stats: Tuple[float, int, int],
    latency_p50: float,
    latency_p95: float,
    cost_per_task: float,
    fb: Dict[str, int],
) -> List[str]:
    lines = [
        "## 主要メトリクス（運用担当向け）",
        "",
        f"- 総実行数: {total_runs}",
        f"- 成功率（全体）: {overall_pass_rate:.2f}%",
        f"- 成功率（S1）: {agg.format_rate(s1_stats)}",
        f"- 成功率（S2）: {agg.format_rate(s2_stats)}",
        f"- レイテンシ p50/p95: {latency_p50:.2f}ms / {latency_p95:.2f}ms",
        f"- コスト/タスク: ${cost_per_task:.6f}",
        "- 失敗分類内訳:",
    ]
    if fb:
        total = max(1, sum(fb.values()))
        for ft, count in fb.items():
            ratio = count / total * 100
            lines.append(f"  - {ft}: {count}件 ({ratio:.1f}%)")
    else:
        lines.append("  - なし")
    return lines


def _section_failure_delta(delta: Dict[str, int]) -> List[str]:
    lines = [
        "",
        "## 失敗タイプの変化（前週比）",
        "",
    ]
    for ft, d in sorted(delta.items(), key=lambda x: x[1], reverse=True):
        sign = "+" if d >= 0 else ""
        lines.append(f"- {ft}: **{sign}{d}**件")
    return lines


def _section_top_failures(failures: List[Tuple[str, str, int, str]]) -> List[str]:
    lines = ["", "## 失敗トップ10（どこが壊れてるか）"]
    if failures:
        for case_id, ft, count, cause in failures:
            lines.append(f"- {case_id} / {ft} / {count}件 / 原因候補: {cause}")
    else:
        lines.append("- 失敗なし")
    return lines


def _section_top_regressions(regressions: List[Dict[str, Any]]) -> List[str]:
    lines = [
        "",
        "## トップ回帰ケース（前週比で最も悪化）",
        "",
        "| ケース | 重要度 | カテゴリ | 前週 | 今週 | 変化 | 主な失敗 |",
        "|--------|--------|---------|------|------|------|---------|",
    ]
    for reg in regressions:
        common_failure = reg["failure_types"][0] if reg["failure_types"] else "N/A"
        lines.append(
            f"| {reg['case_id']} | {reg['severity']} | "
            f"{reg['category']} | {reg['baseline_rate']:.1f}% | "
            f"{reg['current_rate']:.1f}% | **{reg['delta']:+.1f}%** | {common_failure} |"
        )
    return lines


def _section_individual_runs(reports: List) -> List[str]:
    lines = ["", "## Individual Runs", ""]
    for report in reports:
        lines.extend(
            [
                f"### Run {report.run_id[:8]}",
                f"- Timestamp: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
                f"- Cases: {report.total_cases}",
                f"- Passed: {report.passed_cases}",
                f"- Failed: {report.failed_cases}",
                f"- Pass Rate: {report.pass_rate:.2f}%",
                "",
            ]
        )
    return lines

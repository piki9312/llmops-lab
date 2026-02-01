"""
Weekly reporting functionality for Agent Regression.

This module generates weekly regression reports and summaries.
"""

from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
import math

from .models import RegressionReport


class WeeklyReporter:
    """Generates weekly regression reports."""
    
    def __init__(self, reports_dir: str = "reports/agentreg"):
        """
        Initialize the weekly reporter.
        
        Args:
            reports_dir: Directory where reports will be saved
        """
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_report(
        self,
        reports: List[RegressionReport],
        week_start: Optional[datetime] = None,
        previous_week_reports: Optional[List[RegressionReport]] = None,
    ) -> str:
        """
        Generate a weekly report from multiple regression reports.
        
        Args:
            reports: List of regression reports from the week
            week_start: Start date of the week (defaults to current week)
            
        Returns:
            Markdown formatted report string
        """
        if week_start is None:
            week_start = datetime.now() - timedelta(days=datetime.now().weekday())
        
        week_end = week_start + timedelta(days=6)
        
        # Flatten results
        all_results = [result for report in reports for result in report.results]
        prev_results = (
            [result for report in previous_week_reports for result in report.results]
            if previous_week_reports
            else []
        )

        # Calculate aggregates
        total_runs = len(reports)
        total_cases = sum(r.total_cases for r in reports)
        total_passed = sum(r.passed_cases for r in reports)
        overall_pass_rate = (total_passed / total_cases * 100) if total_cases else 0.0

        s1_stats = self._severity_pass_rate(all_results, "S1")
        s2_stats = self._severity_pass_rate(all_results, "S2")
        prev_s1_stats = self._severity_pass_rate(prev_results, "S1") if prev_results else None
        prev_s2_stats = self._severity_pass_rate(prev_results, "S2") if prev_results else None

        prev_s1 = prev_s1_stats[0] if prev_s1_stats and prev_s1_stats[2] > 0 else None
        prev_s2 = prev_s2_stats[0] if prev_s2_stats and prev_s2_stats[2] > 0 else None

        s1_delta = (s1_stats[0] - prev_s1) if prev_s1 is not None and s1_stats[2] > 0 else None
        s2_delta = (s2_stats[0] - prev_s2) if prev_s2 is not None and s2_stats[2] > 0 else None

        # Latency percentiles
        latencies = [r.latency_ms for r in all_results if r.latency_ms > 0]
        if not latencies:
            latencies = [r.latency_ms for r in all_results]
        latency_p50 = self._percentile(latencies, 50)
        latency_p95 = self._percentile(latencies, 95)

        # Cost per task
        total_cost = sum(r.cost_usd for r in all_results)
        cost_per_task = (total_cost / total_cases) if total_cases else 0.0

        # Failure breakdowns
        failure_breakdown = self._failure_breakdown(all_results)
        top_failures = self._top_failures(all_results)

        # Biggest regression
        worst_regression = self._worst_regression(all_results, prev_results)

        # Overall judgment
        overall_status = self._overall_status(
            overall_pass_rate,
            s1_stats[0],
            s1_stats[2],
            s2_stats[0],
            s2_stats[2],
            worst_regression[1],
        )

        # Next actions
        next_actions = self._next_actions(failure_breakdown, worst_regression)
        
        # Generate markdown report
        report_lines = [
            f"# Agent Regression Weekly Report",
            f"",
            f"**Week:** {week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}",
            f"",
            f"## Summary（上の人向け）",
            f"",
            f"- 総合判定: {overall_status}",
            f"- S1成功率: {self._format_rate(s1_stats)}" + (f"（先週比 {s1_delta:+.2f}%）" if s1_delta is not None else "（先週比 N/A）"),
            f"- S2成功率: {self._format_rate(s2_stats)}" + (f"（先週比 {s2_delta:+.2f}%）" if s2_delta is not None else "（先週比 N/A）"),
            f"- 一番重要な回帰: {worst_regression[0]}",
            f"- 来週のアクション:",
            f"  - {next_actions[0]}",
            f"  - {next_actions[1]}",
            f"  - {next_actions[2]}",
            f"",
            f"## 主要メトリクス（運用担当向け）",
            f"",
            f"- 総実行数: {total_runs}",
            f"- 成功率（全体）: {overall_pass_rate:.2f}%",
            f"- 成功率（S1）: {self._format_rate(s1_stats)}",
            f"- 成功率（S2）: {self._format_rate(s2_stats)}",
            f"- レイテンシ p50/p95: {latency_p50:.2f}ms / {latency_p95:.2f}ms",
            f"- コスト/タスク: ${cost_per_task:.6f}",
            f"- 失敗分類内訳:",
        ]

        if failure_breakdown:
            for failure_type, count in failure_breakdown.items():
                ratio = (count / max(1, sum(failure_breakdown.values()))) * 100
                report_lines.append(f"  - {failure_type}: {count}件 ({ratio:.1f}%)")
        else:
            report_lines.append("  - なし")

        report_lines.extend([
            f"",
            f"## 失敗トップ10（どこが壊れてるか）",
        ])

        if top_failures:
            for case_id, failure_type, count, cause in top_failures:
                report_lines.append(
                    f"- {case_id} / {failure_type} / {count}件 / 原因候補: {cause}"
                )
        else:
            report_lines.append("- 失敗なし")

        report_lines.extend([
            f"",
            f"## Individual Runs",
            f""
        ])
        
        for report in reports:
            report_lines.extend([
                f"### Run {report.run_id[:8]}",
                f"- Timestamp: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
                f"- Cases: {report.total_cases}",
                f"- Passed: {report.passed_cases}",
                f"- Failed: {report.failed_cases}",
                f"- Pass Rate: {report.pass_rate:.2f}%",
                f""
            ])
        
        return "\n".join(report_lines)

    @staticmethod
    def _normalize_severity(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = str(value).strip().upper()
        if value in {"S1", "SEV1", "1", "CRITICAL"}:
            return "S1"
        if value in {"S2", "SEV2", "2", "HIGH"}:
            return "S2"
        return None

    def _severity_pass_rate(self, results: List, severity: str) -> Tuple[float, int, int]:
        filtered = [r for r in results if self._normalize_severity(
            (r.metrics or {}).get("severity") or (r.metrics or {}).get("priority") or (r.metrics or {}).get("tier")
        ) == severity]
        total = len(filtered)
        passed = sum(1 for r in filtered if r.passed)
        rate = (passed / total * 100) if total else 0.0
        return rate, passed, total

    @staticmethod
    def _format_rate(stats: Tuple[float, int, int]) -> str:
        rate, _, total = stats
        return f"{rate:.2f}%" if total > 0 else "N/A"

    @staticmethod
    def _percentile(values: List[float], percentile: int) -> float:
        if not values:
            return 0.0
        values = sorted(values)
        index = max(0, math.ceil((percentile / 100) * len(values)) - 1)
        return values[index]

    @staticmethod
    def _failure_type(result) -> str:
        if result.passed:
            return "none"
        # Use failure_type if set, otherwise derive from error
        if result.failure_type:
            return result.failure_type
        if result.error:
            return str(result.error)
        return "empty_output"

    def _failure_breakdown(self, results: List) -> Dict[str, int]:
        breakdown: Dict[str, int] = {}
        for r in results:
            if r.passed:
                continue
            failure_type = self._failure_type(r)
            breakdown[failure_type] = breakdown.get(failure_type, 0) + 1
        return dict(sorted(breakdown.items(), key=lambda x: x[1], reverse=True))

    def _top_failures(self, results: List) -> List[Tuple[str, str, int, str]]:
        counts: Dict[Tuple[str, str], int] = {}
        severity_map: Dict[Tuple[str, str], str] = {}
        for r in results:
            if r.passed:
                continue
            failure_type = self._failure_type(r)
            severity = (r.metrics or {}).get('severity', 'S2')
            key = (r.case_id, failure_type)
            counts[key] = counts.get(key, 0) + 1
            severity_map[key] = severity
        
        # Sort by severity (S1 first), then by count
        sorted_items = sorted(
            counts.items(),
            key=lambda x: (
                0 if severity_map.get(x[0]) == 'S1' else 1,  # S1 first
                -x[1]  # Then by count descending
            )
        )[:10]
        return [
            (case_id, failure_type, count, self._suspected_cause(failure_type))
            for (case_id, failure_type), count in sorted_items
        ]

    @staticmethod
    def _suspected_cause(failure_type: str) -> str:
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

    def _worst_regression(self, results: List, prev_results: List) -> Tuple[str, Optional[float]]:
        if not prev_results:
            return "N/A（先週データなし）", None

        def _case_pass_rate(items: List) -> Dict[str, float]:
            stats: Dict[str, List[bool]] = {}
            for r in items:
                stats.setdefault(r.case_id, []).append(r.passed)
            return {k: (sum(v) / len(v) * 100) for k, v in stats.items() if v}

        curr_rates = _case_pass_rate(results)
        prev_rates = _case_pass_rate(prev_results)
        deltas: List[Tuple[str, float]] = []
        for case_id, curr_rate in curr_rates.items():
            if case_id in prev_rates:
                deltas.append((case_id, curr_rate - prev_rates[case_id]))
        if not deltas:
            return "N/A（比較対象なし）", None

        case_id, delta = min(deltas, key=lambda x: x[1])
        return f"{case_id}（先週比 {delta:+.2f}%）", delta

    @staticmethod
    def _overall_status(
        overall_pass_rate: float,
        s1_pass_rate: float,
        s1_total: int,
        s2_pass_rate: float,
        s2_total: int,
        worst_delta: Optional[float],
    ) -> str:
        s1_ok = (s1_pass_rate >= 98) if s1_total > 0 else True
        s2_ok = (s2_pass_rate >= 98) if s2_total > 0 else True
        if overall_pass_rate >= 98 and s1_ok and s2_ok and (worst_delta is None or worst_delta >= -1):
            return "✅安定"
        if overall_pass_rate < 95 or (s1_total > 0 and s1_pass_rate < 95) or (worst_delta is not None and worst_delta <= -5):
            return "🔥重大"
        return "⚠️注意"

    def _next_actions(self, failure_breakdown: Dict[str, int], worst_regression: Tuple[str, Optional[float]]) -> List[str]:
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
            if key in failure_breakdown and action not in actions:
                actions.append(action)
        if worst_regression[1] is not None:
            actions.append(f"最重要回帰: {worst_regression[0]} の原因調査")
        while len(actions) < 3:
            actions.append("回帰ケースの追加と閾値の再確認")
        return actions[:3]
    
    def save_report(self, report_content: str, filename: Optional[str] = None) -> Path:
        """
        Save a report to disk.
        
        Args:
            report_content: Markdown content of the report
            filename: Optional filename (defaults to timestamped name)
            
        Returns:
            Path where the report was saved
        """
        if filename is None:
            filename = f"weekly_report_{datetime.now().strftime('%Y%m%d')}.md"
        
        report_path = self.reports_dir / filename
        report_path.write_text(report_content, encoding='utf-8')
        
        return report_path

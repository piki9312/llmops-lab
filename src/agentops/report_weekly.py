"""
Weekly reporting functionality for Agent Regression.

This module generates weekly regression reports and summaries.

Orchestrator: data loading (``load_from_jsonl``), metric computation,
and rendering are delegated to:

* :mod:`agentops.aggregate`  – pass-rate / failure stats
* :mod:`agentops.analyze`    – week-over-week deltas & status
* :mod:`agentops.render_md`  – Markdown assembly
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Delegated modules
from . import aggregate as agg
from . import analyze, render_md
from .models import AgentRunRecord, RegressionReport, TestResult


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

    @staticmethod
    def load_from_jsonl(
        log_dir: str = "runs/agentreg",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[RegressionReport]:
        """
        Load test results from JSONL files and convert to RegressionReports.

        Args:
            log_dir: Directory containing YYYYMMDD.jsonl files
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of RegressionReports grouped by run_id
        """
        log_path = Path(log_dir)
        if not log_path.exists():
            return []

        # Collect all records
        records: List[AgentRunRecord] = []
        for jsonl_file in sorted(log_path.glob("*.jsonl")):
            # Parse date from filename (YYYYMMDD.jsonl)
            try:
                file_date = datetime.strptime(jsonl_file.stem, "%Y%m%d").replace(tzinfo=None)
                # Compare dates without time components
                start_date_cmp = (
                    start_date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
                    if start_date
                    else None
                )
                end_date_cmp = (
                    end_date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
                    if end_date
                    else None
                )

                if start_date_cmp and file_date < start_date_cmp:
                    continue
                if end_date_cmp and file_date > end_date_cmp:
                    continue
            except ValueError:
                continue

            # Load records from file
            with open(jsonl_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        record = AgentRunRecord(**data)
                        records.append(record)

        # Group by run_id
        runs: Dict[str, List[AgentRunRecord]] = {}
        for record in records:
            if record.run_id not in runs:
                runs[record.run_id] = []
            runs[record.run_id].append(record)

        # Convert to RegressionReports
        reports: List[RegressionReport] = []
        for run_id, run_records in runs.items():
            if not run_records:
                continue

            # Convert AgentRunRecords to TestResults
            results = [
                TestResult(
                    case_id=rec.case_id,
                    actual_output=rec.output_json if rec.output_json else "",
                    passed=rec.passed,
                    score=1.0 if rec.passed else 0.0,
                    execution_time=rec.latency_ms / 1000.0,  # Convert to seconds
                    timestamp=rec.timestamp,
                    failure_type=rec.failure_type,
                    error="; ".join(rec.reasons) if rec.reasons else None,
                    latency_ms=rec.latency_ms,
                    metrics={
                        "severity": rec.severity,
                        "category": rec.category,
                        "provider": rec.provider,
                        "model": rec.model,
                        "token_usage": rec.token_usage,
                        "cost_usd": rec.cost_usd,
                    },
                )
                for rec in run_records
            ]

            passed_count = sum(1 for r in results if r.passed)
            total_count = len(results)
            avg_score = sum(r.score for r in results) / total_count if total_count else 0.0

            report = RegressionReport(
                run_id=run_id,
                timestamp=run_records[0].timestamp,
                total_cases=total_count,
                passed_cases=passed_count,
                failed_cases=total_count - passed_count,
                average_score=avg_score,
                results=results,
            )
            reports.append(report)

        return reports

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
            previous_week_reports: Optional baseline reports for regression analysis

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

        # Calculate aggregates via aggregate module
        total_runs = len(reports)
        total_cases = sum(r.total_cases for r in reports)
        total_passed = sum(r.passed_cases for r in reports)
        overall_pass_rate = (total_passed / total_cases * 100) if total_cases else 0.0

        s1_stats = agg.severity_pass_rate(all_results, "S1")
        s2_stats = agg.severity_pass_rate(all_results, "S2")
        prev_s1_stats = agg.severity_pass_rate(prev_results, "S1") if prev_results else None
        prev_s2_stats = agg.severity_pass_rate(prev_results, "S2") if prev_results else None

        prev_s1 = prev_s1_stats[0] if prev_s1_stats and prev_s1_stats[2] > 0 else None
        prev_s2 = prev_s2_stats[0] if prev_s2_stats and prev_s2_stats[2] > 0 else None

        s1_delta = (s1_stats[0] - prev_s1) if prev_s1 is not None and s1_stats[2] > 0 else None
        s2_delta = (s2_stats[0] - prev_s2) if prev_s2 is not None and s2_stats[2] > 0 else None

        # Latency percentiles
        latencies = [r.latency_ms for r in all_results if r.latency_ms > 0]
        if not latencies:
            latencies = [r.latency_ms for r in all_results]
        latency_p50 = agg.percentile(latencies, 50)
        latency_p95 = agg.percentile(latencies, 95)

        # Cost per task
        total_cost = sum(r.cost_usd for r in all_results)
        cost_per_task = (total_cost / total_cases) if total_cases else 0.0

        # Failure breakdowns via aggregate module
        fb = agg.failure_breakdown(all_results)
        top_fail = agg.top_failures(all_results)

        # Regression analysis via analyze module
        worst_reg = analyze.worst_regression(all_results, prev_results)

        if prev_results:
            baseline_rate, current_all_rate, all_delta = analyze.compute_pass_rate_delta(
                all_results, prev_results
            )
            failure_type_delta = analyze.compute_failure_type_delta(all_results, prev_results)
            top_regressions = analyze.compute_top_regressions(all_results, prev_results)
        else:
            baseline_rate = None
            current_all_rate = overall_pass_rate
            all_delta = None
            failure_type_delta = {}
            top_regressions = []

        status = analyze.overall_status(
            overall_pass_rate,
            s1_stats[0],
            s1_stats[2],
            s2_stats[0],
            s2_stats[2],
            worst_reg[1],
        )

        actions = analyze.next_actions(fb, worst_reg)

        # Render via render_md module
        return render_md.render_report(
            week_start_str=week_start.strftime("%Y-%m-%d"),
            week_end_str=week_end.strftime("%Y-%m-%d"),
            overall_status=status,
            s1_stats=s1_stats,
            s2_stats=s2_stats,
            s1_delta=s1_delta,
            s2_delta=s2_delta,
            worst_regression=worst_reg,
            next_actions=actions,
            total_runs=total_runs,
            overall_pass_rate=overall_pass_rate,
            latency_p50=latency_p50,
            latency_p95=latency_p95,
            cost_per_task=cost_per_task,
            failure_breakdown=fb,
            top_failures=top_fail,
            all_results=all_results if prev_results else None,
            prev_results=prev_results if prev_results else None,
            baseline_rate=baseline_rate,
            current_all_rate=current_all_rate,
            all_delta=all_delta,
            failure_type_delta=failure_type_delta,
            top_regressions=top_regressions,
            reports=reports,
        )

    # ------------------------------------------------------------------
    # Backward-compatible delegators (thin wrappers around new modules)
    # Tests and external callers can still use WeeklyReporter._xxx()
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_severity(value):
        return agg.normalize_severity(value)

    def _severity_pass_rate(self, results, severity):
        return agg.severity_pass_rate(results, severity)

    @staticmethod
    def _format_rate(stats):
        return agg.format_rate(stats)

    @staticmethod
    def _percentile(values, pct):
        return agg.percentile(values, pct)

    @staticmethod
    def _failure_type(result):
        return agg.failure_type_of(result)

    def _failure_breakdown(self, results):
        return agg.failure_breakdown(results)

    def _top_failures(self, results):
        return agg.top_failures(results)

    @staticmethod
    def _suspected_cause(failure_type):
        return agg.suspected_cause(failure_type)

    def _worst_regression(self, results, prev_results):
        return analyze.worst_regression(results, prev_results)

    @staticmethod
    def _overall_status(
        overall_pass_rate, s1_pass_rate, s1_total, s2_pass_rate, s2_total, worst_delta
    ):
        return analyze.overall_status(
            overall_pass_rate, s1_pass_rate, s1_total, s2_pass_rate, s2_total, worst_delta
        )

    def _next_actions(self, fb, worst_reg):
        return analyze.next_actions(fb, worst_reg)

    @staticmethod
    def _compute_case_pass_rates(results):
        return agg.compute_case_pass_rates(results)

    @staticmethod
    def _compute_pass_rate_delta(current_results, baseline_results, severity=None):
        return analyze.compute_pass_rate_delta(current_results, baseline_results, severity)

    @staticmethod
    def _compute_failure_type_delta(current_results, baseline_results):
        return analyze.compute_failure_type_delta(current_results, baseline_results)

    @staticmethod
    def _compute_top_regressions(current_results, baseline_results, top_n=5):
        return analyze.compute_top_regressions(current_results, baseline_results, top_n)

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
        report_path.write_text(report_content, encoding="utf-8")

        return report_path

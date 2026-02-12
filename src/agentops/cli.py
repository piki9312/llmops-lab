"""
CLI interface for Agent Regression.

This module provides command-line tools for running regression tests.
"""

import argparse
import sys
import json
import uuid
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone, timedelta

from .load_cases import load_from_csv, load_from_directory
from .runner import RegressionRunner
from .evaluator import Evaluator
from .report_weekly import WeeklyReporter
from .models import AgentRunRecord
from .check import run_check, render_check_summary


def run_regression(
    cases_file: str,
    output_dir: Optional[str] = None,
    verbose: bool = False
) -> int:
    """
    Run regression tests from command line.
    
    Args:
        cases_file: Path to CSV file with test cases
        output_dir: Optional directory for output reports
        verbose: Enable verbose output
        
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        # Load test cases
        if verbose:
            print(f"Loading test cases from {cases_file}...")
        cases = load_from_csv(cases_file)
        if verbose:
            print(f"Loaded {len(cases)} test cases")
        
        # Run tests
        if verbose:
            print("Running regression tests...")
        runner = RegressionRunner(use_llmops=True)
        report = runner.run_all(cases)
        
        # Display results
        summary = Evaluator.generate_summary(report)
        print(f"\n=== Regression Test Results ===")
        print(f"Run ID: {summary['run_id']}")
        print(f"Total Cases: {summary['total_cases']}")
        print(f"Passed: {summary['passed_cases']}")
        print(f"Failed: {summary['failed_cases']}")
        print(f"Pass Rate: {summary['pass_rate_percent']:.2f}%")
        print(f"Average Score: {summary['average_score']:.2f}")
        print(f"Average Latency: {summary['avg_latency_ms']:.2f} ms")
        print(f"Total Cost: ${summary['total_cost_usd']:.6f}")
        
        # Save report if output directory specified
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            # TODO: Implement report saving
            if verbose:
                print(f"Report saved to {output_dir}")
        
        return 0 if report.failed_cases == 0 else 1
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def run_daily(
    cases_file: str,
    log_dir: str = "runs/agentreg",
    verbose: bool = False,
    run_id: Optional[str] = None,
) -> int:
    """
    Run daily regression tests and save results to JSONL.
    
    Args:
        cases_file: Path to CSV file with test cases
        log_dir: Directory for JSONL logs (default: runs/agentreg)
        verbose: Enable verbose output
        
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        # Load test cases
        if verbose:
            print(f"Loading test cases from {cases_file}...")
        cases = load_from_csv(cases_file)
        if verbose:
            print(f"Loaded {len(cases)} test cases")
        
        # Generate run ID (or use provided one for CI reproducibility)
        if run_id is None:
            run_id = str(uuid.uuid4())
        
        # Run tests
        if verbose:
            print(f"Running regression tests (run_id: {run_id})...")
        runner = RegressionRunner(use_llmops=True)
        report = runner.run_all(cases, run_id=run_id)
        
        # Prepare JSONL log file
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        jsonl_file = log_path / f"{today}.jsonl"
        
        # Convert results to AgentRunRecords and append to JSONL
        records_written = 0
        with open(jsonl_file, "a", encoding="utf-8") as f:
            for test_case, test_result in zip(cases, report.results):
                record = AgentRunRecord.from_test_result(
                    result=test_result,
                    run_id=run_id,
                    test_case=test_case
                )
                f.write(record.model_dump_json() + "\n")
                records_written += 1
        
        if verbose:
            print(f"Saved {records_written} records to {jsonl_file}")
        
        # Display summary
        summary = Evaluator.generate_summary(report)
        print(f"\n=== Daily Regression Results ===")
        print(f"Date: {today}")
        print(f"Run ID: {run_id}")
        print(f"Total Cases: {summary['total_cases']}")
        print(f"Passed: {summary['passed_cases']}")
        print(f"Failed: {summary['failed_cases']}")
        print(f"Pass Rate: {summary['pass_rate_percent']:.2f}%")
        print(f"S1 Pass Rate: {summary['pass_rate_s1']}  ({summary['s1_passed']}/{summary['s1_total']})")
        print(f"S2 Pass Rate: {summary['pass_rate_s2']}  ({summary['s2_passed']}/{summary['s2_total']})")
        print(f"Average Latency: {summary['avg_latency_ms']:.2f} ms")
        print(f"Total Cost: ${summary['total_cost_usd']:.6f}")
        print(f"\nLog: {jsonl_file}")
        
        # Note: this is a generic gate (any failure). CI can apply stricter gating
        # (e.g. S1-only) by parsing JSONL for the given run_id.
        return 0 if report.failed_cases == 0 else 1
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def generate_weekly_report(
    log_dir: str = "runs/agentreg",
    days: int = 7,
    baseline_days: Optional[int] = None,
    output: Optional[str] = None,
    verbose: bool = False
) -> int:
    """
    Generate weekly report from JSONL logs with optional baseline comparison.
    
    Args:
        log_dir: Directory containing JSONL logs
        days: Number of days to include in current period (default: 7)
        baseline_days: Number of days for baseline period (default: same as days)
        output: Output file path (default: print to stdout)
        verbose: Enable verbose output
        
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        if baseline_days is None:
            baseline_days = days
            
        if verbose:
            print(f"Loading JSONL logs from {log_dir}...")
        
        # Calculate date ranges (timezone naive for file date comparison)
        end_date = datetime.now()
        current_start = end_date - timedelta(days=days)
        baseline_end = current_start - timedelta(days=1)
        baseline_start = baseline_end - timedelta(days=baseline_days)
        
        # Load current period reports from JSONL
        reporter = WeeklyReporter()
        reports = reporter.load_from_jsonl(
            log_dir=log_dir,
            start_date=current_start,
            end_date=end_date
        )
        
        # Load baseline period reports from JSONL
        baseline_reports = reporter.load_from_jsonl(
            log_dir=log_dir,
            start_date=baseline_start,
            end_date=baseline_end
        )
        
        if not reports:
            msg = f"No reports found in {log_dir} for the last {days} days"
            if output:
                # Write a minimal placeholder so downstream steps don't break
                output_path = Path(output)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(
                    f"# AgentReg Report\n\n{msg}\n", encoding="utf-8"
                )
                print(f"Report saved to {output} (no data)")
            else:
                print(msg)
            return 0
        
        if verbose:
            print(f"Loaded {len(reports)} current regression runs")
            if baseline_reports:
                print(f"Loaded {len(baseline_reports)} baseline regression runs")
        
        # Generate report with baseline comparison
        report_content = reporter.generate_report(
            reports,
            previous_week_reports=baseline_reports if baseline_reports else None
        )
        
        # Output report
        if output:
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report_content, encoding='utf-8')
            print(f"Report saved to {output}")
        else:
            print(report_content)
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def check_gate(
    log_dir: str = "runs/agentreg",
    days: int = 1,
    baseline_days: int = 7,
    s1_threshold: float = 100.0,
    overall_threshold: float = 80.0,
    write_summary: bool = False,
    verbose: bool = False,
) -> int:
    """Compare current period against baseline and enforce thresholds.

    Returns:
        Exit code (0 = all thresholds met, 1 = violation or no data).
    """
    try:
        if verbose:
            print(
                f"Gate check: log_dir={log_dir} days={days} "
                f"baseline_days={baseline_days} "
                f"s1_threshold={s1_threshold}% overall_threshold={overall_threshold}%"
            )

        result = run_check(
            log_dir=log_dir,
            days=days,
            baseline_days=baseline_days,
            s1_threshold=s1_threshold,
            overall_threshold=overall_threshold,
        )

        if result.current_runs == 0:
            print(f"\u274c No runs found in {log_dir} for the last {days} day(s)", file=sys.stderr)
            return 1

        # Human-readable summary
        icon = "\u2705" if result.gate_passed else "\u274c"
        print(f"\n=== AgentReg Gate Check ===")
        print(f"Gate: {icon} {'PASS' if result.gate_passed else 'FAIL'}")
        print(f"Current runs : {result.current_runs}")
        print(f"Baseline runs: {result.baseline_runs}")
        print(f"Overall : {result.overall_rate:.2f}% (threshold {overall_threshold}%)")
        print(f"S1      : {result.s1_rate:.2f}% ({result.s1_passed}/{result.s1_total}, threshold {s1_threshold}%)")
        print(f"S2      : {result.s2_rate:.2f}% ({result.s2_passed}/{result.s2_total})")

        for t in result.thresholds:
            t_icon = "\u2705" if t.passed else "\u274c"
            print(f"  {t_icon} {t.name}: {t.actual:.2f}% >= {t.threshold:.1f}%  {t.detail}")

        if result.top_regressions:
            print(f"\nTop regressions:")
            for reg in result.top_regressions:
                ft = ", ".join(reg["failure_types"]) if reg["failure_types"] else "\u2014"
                print(
                    f"  {reg['case_id']} [{reg['severity']}] "
                    f"{reg['baseline_rate']:.0f}% \u2192 {reg['current_rate']:.0f}% "
                    f"(\u0394 {reg['delta']:+.1f}%) \u2014 {ft}"
                )

        # Markdown for GitHub Job Summary
        if write_summary:
            import os as _os
            md = render_check_summary(result)
            summary_path = _os.environ.get("GITHUB_STEP_SUMMARY")
            if summary_path:
                Path(summary_path).write_text(md, encoding="utf-8")
            print(f"\n{md}")

        return 0 if result.gate_passed else 1

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Agent Regression Testing Tool"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # run command (existing behavior)
    run_parser = subparsers.add_parser("run", help="Run regression tests")
    run_parser.add_argument(
        "cases_file",
        help="Path to CSV file containing test cases"
    )
    run_parser.add_argument(
        "-o", "--output",
        dest="output_dir",
        help="Output directory for reports"
    )
    run_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    # run-daily command (new JSONL persistence)
    daily_parser = subparsers.add_parser("run-daily", help="Run daily regression and save to JSONL")
    daily_parser.add_argument(
        "cases_file",
        help="Path to CSV file containing test cases"
    )
    daily_parser.add_argument(
        "--log-dir",
        default="runs/agentreg",
        help="Directory for JSONL logs (default: runs/agentreg)"
    )
    daily_parser.add_argument(
        "--run-id",
        default=None,
        help="Optional run_id (useful for CI correlation)"
    )
    daily_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    # report command (generate weekly report from JSONL)
    report_parser = subparsers.add_parser("report", help="Generate weekly report from JSONL logs")
    report_parser.add_argument(
        "--log-dir",
        default="runs/agentreg",
        help="Directory containing JSONL logs (default: runs/agentreg)"
    )
    report_parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to include in current period (default: 7)"
    )
    report_parser.add_argument(
        "--baseline-days",
        type=int,
        default=None,
        help="Number of days for baseline period (default: same as --days)"
    )
    report_parser.add_argument(
        "-o", "--output",
        help="Output file path (default: print to stdout)"
    )
    report_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    # check command (gate: compare current vs baseline)
    check_parser = subparsers.add_parser(
        "check", help="Gate check: compare current period against baseline"
    )
    check_parser.add_argument(
        "--log-dir",
        default="runs/agentreg",
        help="Directory containing JSONL logs (default: runs/agentreg)"
    )
    check_parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Days for current period (default: 1)"
    )
    check_parser.add_argument(
        "--baseline-days",
        type=int,
        default=7,
        help="Days for baseline period (default: 7)"
    )
    check_parser.add_argument(
        "--s1-threshold",
        type=float,
        default=100.0,
        help="S1 pass rate threshold in %% (default: 100)"
    )
    check_parser.add_argument(
        "--overall-threshold",
        type=float,
        default=80.0,
        help="Overall pass rate threshold in %% (default: 80)"
    )
    check_parser.add_argument(
        "--write-summary",
        action="store_true",
        help="Write markdown to $GITHUB_STEP_SUMMARY"
    )
    check_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    args = parser.parse_args()
    
    if args.command == "run":
        sys.exit(run_regression(args.cases_file, args.output_dir, args.verbose))
    elif args.command == "run-daily":
        sys.exit(run_daily(args.cases_file, args.log_dir, args.verbose, run_id=args.run_id))
    elif args.command == "report":
        sys.exit(generate_weekly_report(
            args.log_dir, args.days, args.baseline_days, args.output, args.verbose
        ))
    elif args.command == "check":
        sys.exit(check_gate(
            log_dir=args.log_dir,
            days=args.days,
            baseline_days=args.baseline_days,
            s1_threshold=args.s1_threshold,
            overall_threshold=args.overall_threshold,
            write_summary=args.write_summary,
            verbose=args.verbose,
        ))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

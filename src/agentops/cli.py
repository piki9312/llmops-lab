"""
CLI interface for Agent Regression.

This module provides command-line tools for running regression tests.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from .load_cases import load_from_csv, load_from_directory
from .runner import RegressionRunner
from .evaluator import Evaluator
from .report_weekly import WeeklyReporter


def dummy_agent(prompt: str) -> str:
    """Placeholder agent function for testing."""
    return f"Response to: {prompt}"


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
        runner = RegressionRunner(dummy_agent)
        report = runner.run_all(cases)
        
        # Display results
        summary = Evaluator.generate_summary(report)
        print(f"\n=== Regression Test Results ===")
        print(f"Run ID: {summary['run_id']}")
        print(f"Total Cases: {summary['total_cases']}")
        print(f"Passed: {summary['passed_cases']}")
        print(f"Failed: {summary['failed_cases']}")
        print(f"Pass Rate: {summary['pass_rate']:.2f}%")
        print(f"Average Score: {summary['average_score']:.2f}")
        
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


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Agent Regression Testing Tool"
    )
    
    parser.add_argument(
        "cases_file",
        help="Path to CSV file containing test cases"
    )
    
    parser.add_argument(
        "-o", "--output",
        dest="output_dir",
        help="Output directory for reports"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    sys.exit(run_regression(args.cases_file, args.output_dir, args.verbose))


if __name__ == "__main__":
    main()

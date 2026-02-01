"""
Weekly reporting functionality for Agent Regression.

This module generates weekly regression reports and summaries.
"""

from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional
import json

from .models import RegressionReport
from .evaluator import Evaluator


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
        week_start: Optional[datetime] = None
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
        
        # Calculate aggregates
        total_runs = len(reports)
        total_cases = sum(r.total_cases for r in reports)
        total_passed = sum(r.passed_cases for r in reports)
        avg_pass_rate = sum(r.pass_rate for r in reports) / total_runs if total_runs > 0 else 0.0
        
        # Generate markdown report
        report_lines = [
            f"# Agent Regression Weekly Report",
            f"",
            f"**Week:** {week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}",
            f"",
            f"## Summary",
            f"",
            f"- Total Runs: {total_runs}",
            f"- Total Test Cases: {total_cases}",
            f"- Total Passed: {total_passed}",
            f"- Average Pass Rate: {avg_pass_rate:.2f}%",
            f"",
            f"## Individual Runs",
            f""
        ]
        
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

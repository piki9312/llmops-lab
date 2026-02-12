#!/usr/bin/env python3
"""
Utility script to create synthetic baseline data for testing regression analysis.
"""

import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
from agentops.models import AgentRunRecord

def create_baseline_data(log_dir: str = "runs/agentreg"):
    """Create synthetic baseline data from 7-14 days ago."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Create baseline data for 8 days ago (all passing for contrast)
    baseline_date = datetime.now(timezone.utc) - timedelta(days=8)
    baseline_date_str = baseline_date.strftime("%Y%m%d")
    baseline_file = log_path / f"{baseline_date_str}.jsonl"
    
    records = []
    run_id = "baseline-run-001"
    
    # Create 10 passing test cases
    for i in range(10):
        record = AgentRunRecord(
            timestamp=baseline_date,
            run_id=run_id,
            case_id=f"TC{i:03d}",
            severity="S1" if i < 5 else "S2",
            category="api",
            passed=True,
            failure_type=None,
            latency_ms=100.0 + i,
            reasons=[],
            provider="mock",
            model="gpt-4-mock",
        )
        records.append(record)
    
    # Write to JSONL
    with open(baseline_file, "w", encoding="utf-8") as f:
        for record in records:
            f.write(record.model_dump_json() + "\n")
    
    print(f"Created baseline data: {baseline_file}")
    print(f"  - 10 test cases (5 S1, 5 S2)")
    print(f"  - All passing (100% pass rate)")
    return baseline_file

if __name__ == "__main__":
    create_baseline_data()

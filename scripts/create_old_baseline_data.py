#!/usr/bin/env python3
"""
Create baseline data from 22 days ago (for regression comparison).
This script creates 10 passing test cases dated from 22 days in the past.
"""

from datetime import datetime, timedelta
from pathlib import Path
import json
import sys
sys.path.insert(0, "src")

from agentops.models import AgentRunRecord


def create_baseline_records():
    """Create 10 synthetic baseline records from 22 days ago."""
    baseline_date = datetime.now() - timedelta(days=22)
    
    records = []
    for i in range(1, 11):
        case_id = f"TC{i:03d}"
        severity = "S1" if i <= 5 else "S2"
        
        record = AgentRunRecord(
            run_id="baseline",
            case_id=case_id,
            timestamp=baseline_date,
            passed=True,  # All passing for baseline
            output_json={"status": "success"},
            failure_type=None,
            reasons=[],
            severity=severity,
            category="api",
            provider="openai",
            model="gpt-4",
            token_usage={"prompt": 100, "completion": 50, "total": 150},
            cost_usd=0.003,
            latency_ms=100 + i * 5,
        )
        records.append(record)
    
    return records


def save_records(records):
    """Save records to JSONL file."""
    date_str = (datetime.now() - timedelta(days=22)).strftime("%Y%m%d")
    output_dir = Path("runs/agentreg")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / f"{date_str}.jsonl"
    
    with open(output_file, "w", encoding="utf-8") as f:
        for record in records:
            f.write(record.model_dump_json() + "\n")
    
    print(f"✓ Created baseline data: {output_file}")
    print(f"  - Records: {len(records)}")
    print(f"  - Pass rate: 100%")
    print(f"  - File date: {date_str} ({(datetime.now() - timedelta(days=22)).strftime('%Y-%m-%d')})")


if __name__ == "__main__":
    records = create_baseline_records()
    save_records(records)

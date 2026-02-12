"""CI gate: fail when S1 failures exist (AgentReg JSONL).

Design goals:
- Tiny, robust, and works with current JSONL schema.
- Selects the latest JSONL file (YYYYMMDD.jsonl) under ``--log-dir``.
- Within that file, evaluates ONLY the most recent run_id (by timestamp / last-seen).
- Optionally, you can pin a specific ``--run-id``.

Exit codes:
  0: S1 failures == 0
  1: S1 failures > 0, or required data not found

Usage:
  python scripts/ci_gate_s1.py --log-dir runs/agentreg
  python scripts/ci_gate_s1.py --log-dir runs/agentreg --run-id <uuid>
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from agentops.aggregate import normalize_severity


_JSONL_DATE_RE = re.compile(r"^(\d{8})\.jsonl$")


def _is_failed(rec: Dict[str, Any]) -> Optional[bool]:
    """Return True/False if pass/fail can be determined; otherwise None."""
    if "passed" in rec:
        return not bool(rec.get("passed"))
    status = rec.get("status")
    if isinstance(status, str):
        s = status.strip().lower()
        if s in {"pass", "passed", "ok", "success"}:
            return False
        if s in {"fail", "failed", "ng", "error"}:
            return True
    return None


def _parse_ts(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        s = value.strip()
        # Handle Z suffix
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            return None
    return None


def _choose_latest_jsonl(log_dir: Path) -> Optional[Path]:
    files = list(log_dir.glob("*.jsonl"))
    if not files:
        return None

    # Prefer date-stamped filenames (YYYYMMDD.jsonl)
    dated: List[Tuple[int, Path]] = []
    others: List[Path] = []
    for p in files:
        m = _JSONL_DATE_RE.match(p.name)
        if m:
            dated.append((int(m.group(1)), p))
        else:
            others.append(p)

    if dated:
        dated.sort(key=lambda x: x[0], reverse=True)
        return dated[0][1]

    # Fallback: newest mtime
    return max(others, key=lambda p: p.stat().st_mtime)


def _iter_records(jsonl_path: Path) -> Iterable[Dict[str, Any]]:
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                print(f"⚠️  skip invalid json (line {i}) in {jsonl_path.name}", file=sys.stderr)
                continue
            if isinstance(obj, dict):
                yield obj


def _infer_severity(rec: Dict[str, Any]) -> Optional[str]:
    # Common fields: severity (AgentRunRecord), or alternatives
    for key in ("severity", "priority", "tier", "importance", "level"):
        sev = normalize_severity(rec.get(key))
        if sev:
            return sev
    return None


def _pick_target_run_id(records: List[Dict[str, Any]]) -> Optional[str]:
    """Pick the most recent run_id among records.

    Strategy:
    - If timestamps exist, pick run_id with max timestamp.
    - Else, pick last-seen run_id while scanning file.
    """
    best: Tuple[Optional[datetime], Optional[str]] = (None, None)
    last_seen: Optional[str] = None

    for rec in records:
        rid = rec.get("run_id")
        if isinstance(rid, str) and rid:
            last_seen = rid
        ts = _parse_ts(rec.get("timestamp"))
        if ts and isinstance(rid, str) and rid:
            if best[0] is None or ts > best[0]:
                best = (ts, rid)

    return best[1] or last_seen


@dataclass
class GateStats:
    run_id: str
    total: int
    failed: int
    s1_total: int
    s1_failed: int
    s2_total: int
    s2_failed: int
    sample_s1_failures: List[Tuple[str, str]]  # (case_id, failure_type)

    @property
    def pass_rate(self) -> float:
        return (self.total - self.failed) / self.total * 100 if self.total else 0.0


def compute_gate_stats(*, jsonl_path: Path, run_id: str, sample: int = 5) -> GateStats:
    total = failed = 0
    s1_total = s1_failed = 0
    s2_total = s2_failed = 0
    samples: List[Tuple[str, str]] = []
    seen_case_ids = set()

    for rec in _iter_records(jsonl_path):
        if rec.get("run_id") != run_id:
            continue

        total += 1
        is_failed = _is_failed(rec)
        if is_failed is None:
            # Unknown line; be conservative and skip.
            continue
        if is_failed:
            failed += 1

        sev = _infer_severity(rec)
        if sev == "S1":
            s1_total += 1
            if is_failed:
                s1_failed += 1
                case_id = str(rec.get("case_id") or "")
                ft = str(rec.get("failure_type") or "")
                if case_id and case_id not in seen_case_ids and len(samples) < sample:
                    samples.append((case_id, ft or "(unknown)"))
                    seen_case_ids.add(case_id)
        elif sev == "S2":
            s2_total += 1
            if is_failed:
                s2_failed += 1

    return GateStats(
        run_id=run_id,
        total=total,
        failed=failed,
        s1_total=s1_total,
        s1_failed=s1_failed,
        s2_total=s2_total,
        s2_failed=s2_failed,
        sample_s1_failures=samples,
    )


def _render_summary(*, jsonl_path: Path, stats: GateStats) -> str:
    md: List[str] = []
    md.append("## AgentReg CI Summary")
    md.append("")
    md.append(f"- JSONL: `{jsonl_path}`")
    md.append(f"- Run ID: `{stats.run_id}`")
    md.append(f"- Total cases: **{stats.total}**")
    md.append(f"- Failed cases: **{stats.failed}**")
    md.append(f"- Pass rate: **{stats.pass_rate:.2f}%**")
    md.append(f"- S1 failed: **{stats.s1_failed}** / {stats.s1_total}")
    md.append(f"- S2 failed: **{stats.s2_failed}** / {stats.s2_total}")

    gate = "❌ FAIL (S1 failures)" if stats.s1_failed > 0 else "✅ PASS"
    md.append("")
    md.append(f"**Gate:** {gate}")

    if stats.s1_failed > 0 and stats.sample_s1_failures:
        md.append("")
        md.append("### Sample S1 failures")
        for case_id, ft in stats.sample_s1_failures:
            md.append(f"- `{case_id}` ({ft})")

    return "\n".join(md) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="AgentReg S1-only CI gate")
    parser.add_argument("--log-dir", default="runs/agentreg", help="Directory containing JSONL logs")
    parser.add_argument(
        "--run-id",
        default=None,
        help="Optional run_id to evaluate (default: latest run in latest JSONL)",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=5,
        help="How many unique S1 failing case_ids to show (default: 5)",
    )
    parser.add_argument(
        "--write-summary",
        action="store_true",
        help="Write markdown to $GITHUB_STEP_SUMMARY (and stdout)",
    )
    args = parser.parse_args()

    log_dir = Path(args.log_dir)
    jsonl_path = _choose_latest_jsonl(log_dir)
    if jsonl_path is None:
        print(f"❌ No JSONL files found under: {log_dir}", file=sys.stderr)
        return 1

    records = list(_iter_records(jsonl_path))
    if not records:
        print(f"❌ JSONL file is empty: {jsonl_path}", file=sys.stderr)
        return 1

    run_id = args.run_id or _pick_target_run_id(records)
    if not run_id:
        print(f"❌ Could not determine run_id from: {jsonl_path}", file=sys.stderr)
        return 1

    stats = compute_gate_stats(jsonl_path=jsonl_path, run_id=run_id, sample=args.sample)
    if stats.total == 0:
        print(f"❌ run_id not found in latest JSONL: {run_id}", file=sys.stderr)
        print(f"   JSONL: {jsonl_path}", file=sys.stderr)
        return 1

    # Human-readable line output
    print(
        "AgentReg gate: "
        f"jsonl={jsonl_path.name} run_id={run_id} "
        f"total={stats.total} failed={stats.failed} "
        f"S1_failed={stats.s1_failed}/{stats.s1_total} "
        f"S2_failed={stats.s2_failed}/{stats.s2_total}"
    )

    md = _render_summary(jsonl_path=jsonl_path, stats=stats)
    if args.write_summary:
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary_path:
            Path(summary_path).write_text(md, encoding="utf-8")
        print(md)

    if stats.s1_failed > 0:
        print("❌ S1 failures detected. Failing CI.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

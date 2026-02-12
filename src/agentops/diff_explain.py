"""Failure diff explanation engine.

Compares current failures against the baseline to produce
human-readable explanations of **why** each case regressed.

Heuristics detect:
- JSON schema mismatch (missing / extra keys)
- Failure-type change (e.g. ``quality_fail`` → ``bad_json``)
- Latency spike (>2× baseline median)
- Token usage increase (>50% above baseline median)
- New failure (case passed in baseline, fails now)
- Persistent failure (already failing in baseline)

Usage::

    explanations = explain_failures(current_results, baseline_results)
    for e in explanations:
        print(e["case_id"], e["explanation"])
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ------------------------------------------------------------------
# Data structures
# ------------------------------------------------------------------

@dataclass
class FailureExplanation:
    """Structured explanation for a single regressed case."""

    case_id: str
    severity: str
    category: str
    signals: List[str] = field(default_factory=list)
    current_failure_type: Optional[str] = None
    baseline_failure_type: Optional[str] = None
    schema_diff: Optional[Dict[str, Any]] = None
    latency_ratio: Optional[float] = None
    token_ratio: Optional[float] = None

    @property
    def explanation(self) -> str:
        """Single-line human-readable summary."""
        if not self.signals:
            return "原因不明（調査必要）"
        return "; ".join(self.signals)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "severity": self.severity,
            "category": self.category,
            "explanation": self.explanation,
            "signals": self.signals,
            "current_failure_type": self.current_failure_type,
            "baseline_failure_type": self.baseline_failure_type,
            "schema_diff": self.schema_diff,
            "latency_ratio": self.latency_ratio,
            "token_ratio": self.token_ratio,
        }


# ------------------------------------------------------------------
# Core logic
# ------------------------------------------------------------------

def explain_failures(
    current_results: List,
    baseline_results: List,
    latency_threshold: float = 2.0,
    token_threshold: float = 1.5,
) -> List[FailureExplanation]:
    """Produce explanations for each currently-failing case.

    Parameters
    ----------
    current_results :
        Flat list of ``TestResult`` from the current period.
    baseline_results :
        Flat list of ``TestResult`` from the baseline period.
    latency_threshold :
        Latency ratio above which a spike is reported (default 2×).
    token_threshold :
        Token ratio above which an increase is reported (default 1.5×).

    Returns
    -------
    List of :class:`FailureExplanation`, one per failing case.
    """
    # Index baseline by case_id
    bl_by_case: Dict[str, List] = {}
    for r in baseline_results:
        bl_by_case.setdefault(r.case_id, []).append(r)

    # Current failures grouped by case_id
    cur_failures: Dict[str, List] = {}
    for r in current_results:
        if not r.passed:
            cur_failures.setdefault(r.case_id, []).append(r)

    explanations: List[FailureExplanation] = []

    for case_id, fails in sorted(cur_failures.items()):
        sev = (fails[0].metrics or {}).get("severity", "S2")
        cat = (fails[0].metrics or {}).get("category", "unknown")
        bl_runs = bl_by_case.get(case_id, [])

        exp = FailureExplanation(case_id=case_id, severity=sev, category=cat)

        # --- 1. New vs persistent failure ---
        if bl_runs:
            bl_passed = all(r.passed for r in bl_runs)
            if bl_passed:
                exp.signals.append("新規回帰: ベースラインでは全パス")
            else:
                bl_fail_rate = sum(1 for r in bl_runs if not r.passed) / len(bl_runs)
                exp.signals.append(
                    f"継続失敗: ベースライン失敗率 {bl_fail_rate * 100:.0f}%"
                )
        else:
            exp.signals.append("ベースラインデータなし（新規ケースまたは初回実行）")

        # --- 2. Failure type change ---
        cur_ft = _dominant_failure_type(fails)
        bl_ft = _dominant_failure_type([r for r in bl_runs if not r.passed]) if bl_runs else None
        exp.current_failure_type = cur_ft
        exp.baseline_failure_type = bl_ft

        if cur_ft and bl_ft and cur_ft != bl_ft:
            exp.signals.append(
                f"失敗タイプ変化: {bl_ft} → {cur_ft}"
            )
        elif cur_ft:
            exp.signals.append(f"失敗タイプ: {cur_ft}")

        # --- 3. JSON schema diff (S1 cases) ---
        if sev == "S1":
            schema_diff = _detect_schema_diff(fails, bl_runs)
            if schema_diff:
                exp.schema_diff = schema_diff
                parts = []
                if schema_diff.get("missing_keys"):
                    parts.append(f"欠損キー: {', '.join(schema_diff['missing_keys'])}")
                if schema_diff.get("extra_keys"):
                    parts.append(f"余剰キー: {', '.join(schema_diff['extra_keys'])}")
                if schema_diff.get("type_changes"):
                    tc = schema_diff["type_changes"]
                    parts.append(f"型変化: {', '.join(f'{k}: {v}' for k, v in tc.items())}")
                if parts:
                    exp.signals.append("JSON schema不一致: " + "; ".join(parts))

        # --- 4. Latency spike ---
        latency_ratio = _latency_ratio(fails, bl_runs)
        if latency_ratio is not None:
            exp.latency_ratio = latency_ratio
            if latency_ratio >= latency_threshold:
                exp.signals.append(
                    f"レイテンシ急増: ベースライン比 {latency_ratio:.1f}×"
                )

        # --- 5. Token increase ---
        token_ratio = _token_ratio(fails, bl_runs)
        if token_ratio is not None:
            exp.token_ratio = token_ratio
            if token_ratio >= token_threshold:
                exp.signals.append(
                    f"トークン増加: ベースライン比 {token_ratio:.1f}×"
                )

        explanations.append(exp)

    # Sort: S1 first, then by number of signals descending
    explanations.sort(
        key=lambda e: (0 if e.severity == "S1" else 1, -len(e.signals))
    )
    return explanations


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _dominant_failure_type(results: List) -> Optional[str]:
    """Return the most common failure_type among failed results."""
    counts: Dict[str, int] = {}
    for r in results:
        ft = getattr(r, "failure_type", None)
        if ft:
            counts[ft] = counts.get(ft, 0) + 1
    if not counts:
        return None
    return max(counts, key=counts.get)  # type: ignore[arg-type]


def _detect_schema_diff(
    current_fails: List,
    baseline_runs: List,
) -> Optional[Dict[str, Any]]:
    """Compare JSON output schemas between current failures and baseline.

    Works on ``output_json`` (from ``AgentRunRecord`` via ``metrics``)
    or tries to parse ``actual_output`` as JSON.
    """
    cur_keys = _collect_json_keys(current_fails)
    bl_keys = _collect_json_keys(baseline_runs)

    if not cur_keys and not bl_keys:
        return None

    missing = bl_keys - cur_keys
    extra = cur_keys - bl_keys

    # Type changes: same key but different types
    cur_types = _collect_key_types(current_fails)
    bl_types = _collect_key_types(baseline_runs)
    type_changes: Dict[str, str] = {}
    for k in cur_types.keys() & bl_types.keys():
        if cur_types[k] != bl_types[k]:
            type_changes[k] = f"{bl_types[k]} → {cur_types[k]}"

    if not missing and not extra and not type_changes:
        return None

    return {
        "missing_keys": sorted(missing),
        "extra_keys": sorted(extra),
        "type_changes": type_changes,
    }


def _collect_json_keys(results: List) -> set:
    """Extract top-level JSON keys from results."""
    keys: set = set()
    for r in results:
        obj = _get_json_output(r)
        if isinstance(obj, dict):
            keys.update(obj.keys())
    return keys


def _collect_key_types(results: List) -> Dict[str, str]:
    """Map top-level keys to their type names (last seen wins)."""
    types: Dict[str, str] = {}
    for r in results:
        obj = _get_json_output(r)
        if isinstance(obj, dict):
            for k, v in obj.items():
                types[k] = type(v).__name__
    return types


def _get_json_output(result) -> Optional[dict]:
    """Try to extract parsed JSON from a result."""
    # AgentRunRecord path (via metrics round-trip)
    metrics = getattr(result, "metrics", None) or {}
    output_json = metrics.get("output_json")
    if isinstance(output_json, dict):
        return output_json

    # Try actual_output
    actual = getattr(result, "actual_output", None)
    if actual:
        try:
            parsed = json.loads(actual)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
    return None


def _latency_ratio(current_fails: List, baseline_runs: List) -> Optional[float]:
    """Compute median current latency / median baseline latency."""
    cur_lats = [r.latency_ms for r in current_fails if r.latency_ms > 0]
    bl_lats = [r.latency_ms for r in baseline_runs if r.latency_ms > 0]
    if not cur_lats or not bl_lats:
        return None
    cur_med = statistics.median(cur_lats)
    bl_med = statistics.median(bl_lats)
    if bl_med == 0:
        return None
    return cur_med / bl_med


def _token_ratio(current_fails: List, baseline_runs: List) -> Optional[float]:
    """Compute median current tokens / median baseline tokens."""
    def _tokens(r):
        direct = getattr(r, "total_tokens", 0)
        if direct:
            return direct
        metrics = getattr(r, "metrics", None) or {}
        usage = metrics.get("token_usage") or {}
        if isinstance(usage, dict):
            return usage.get("total", 0)
        return 0

    cur_toks = [_tokens(r) for r in current_fails if _tokens(r) > 0]
    bl_toks = [_tokens(r) for r in baseline_runs if _tokens(r) > 0]
    if not cur_toks or not bl_toks:
        return None
    cur_med = statistics.median(cur_toks)
    bl_med = statistics.median(bl_toks)
    if bl_med == 0:
        return None
    return cur_med / bl_med


# ------------------------------------------------------------------
# Markdown rendering
# ------------------------------------------------------------------

def render_failure_explanations(explanations: List[FailureExplanation]) -> str:
    """Render explanations as a Markdown section."""
    if not explanations:
        return ""

    lines = [
        "### Failure Explanations",
        "",
        "| Case | Sev | Type | Explanation |",
        "|------|-----|------|-------------|",
    ]
    for e in explanations:
        ft = e.current_failure_type or "—"
        # Truncate explanation for table
        expl = e.explanation
        if len(expl) > 120:
            expl = expl[:117] + "…"
        lines.append(f"| {e.case_id} | {e.severity} | {ft} | {expl} |")

    return "\n".join(lines) + "\n"

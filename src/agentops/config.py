"""Load and validate ``.agentreg.yml`` configuration.

Typical usage::

    from agentops.config import load_config
    cfg = load_config()                         # auto-detect .agentreg.yml
    cfg = load_config("path/to/.agentreg.yml")  # explicit

The returned :class:`AgentRegConfig` is a plain dataclass – easy to
inspect, test, and serialise.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

try:
    import yaml  # PyYAML – listed in [project.optional-dependencies]
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


# ------------------------------------------------------------------
# Data structures
# ------------------------------------------------------------------

@dataclass
class Thresholds:
    """Gate thresholds (all values in percent 0-100)."""

    s1_pass_rate: float = 100.0
    overall_pass_rate: float = 80.0
    top_n: int = 5


@dataclass
class RuleMatch:
    """Match conditions for a rule override."""

    labels: List[str] = field(default_factory=list)
    paths: List[str] = field(default_factory=list)


@dataclass
class Rule:
    """A single threshold-override rule."""

    name: str = ""
    match: RuleMatch = field(default_factory=RuleMatch)
    thresholds: Thresholds = field(default_factory=Thresholds)


@dataclass
class AgentRegConfig:
    """Top-level configuration loaded from ``.agentreg.yml``."""

    thresholds: Thresholds = field(default_factory=Thresholds)
    rules: List[Rule] = field(default_factory=list)
    owner_fallback: str = "platform-team"

    # --- helpers ---

    def resolve_thresholds(
        self,
        *,
        labels: Sequence[str] = (),
        changed_files: Sequence[str] = (),
    ) -> Thresholds:
        """Return the effective :class:`Thresholds` for a given context.

        Evaluates *rules* top-to-bottom; the **first match wins**.
        Only fields explicitly set in the matching rule override the defaults.
        """
        for rule in self.rules:
            if _rule_matches(rule, labels=labels, changed_files=changed_files):
                return _merge_thresholds(self.thresholds, rule.thresholds)
        return self.thresholds


# ------------------------------------------------------------------
# Default config (used when no file is found)
# ------------------------------------------------------------------

DEFAULT_CONFIG = AgentRegConfig()


# ------------------------------------------------------------------
# Loader
# ------------------------------------------------------------------

_SEARCH_NAMES = (".agentreg.yml", ".agentreg.yaml", "agentreg.yml")


def load_config(path: Optional[str] = None) -> AgentRegConfig:
    """Load config from *path* or auto-detect in the working directory.

    If no file is found, returns :data:`DEFAULT_CONFIG`.

    Raises:
        FileNotFoundError: If an explicit *path* does not exist.
        ValueError: If the YAML is syntactically invalid.
    """
    if yaml is None:  # pragma: no cover
        # PyYAML not installed – fall back to defaults silently.
        return DEFAULT_CONFIG

    if path is not None:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        return _parse(p)

    # Auto-detect
    for name in _SEARCH_NAMES:
        p = Path(name)
        if p.exists():
            return _parse(p)

    return DEFAULT_CONFIG


def _parse(path: Path) -> AgentRegConfig:
    """Parse a YAML file into :class:`AgentRegConfig`."""
    raw = path.read_text(encoding="utf-8")
    try:
        data: Dict[str, Any] = yaml.safe_load(raw) or {}
    except Exception as exc:
        raise ValueError(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping at top level in {path}")

    thresholds = _parse_thresholds(data.get("thresholds", {}))
    rules = [_parse_rule(r, defaults=thresholds) for r in data.get("rules", [])]
    owner_fallback = str(data.get("owner_fallback", "platform-team"))

    return AgentRegConfig(
        thresholds=thresholds,
        rules=rules,
        owner_fallback=owner_fallback,
    )


# ------------------------------------------------------------------
# Internal parsers
# ------------------------------------------------------------------

def _parse_thresholds(raw: Any) -> Thresholds:
    if not isinstance(raw, dict):
        return Thresholds()
    return Thresholds(
        s1_pass_rate=float(raw.get("s1_pass_rate", 100.0)),
        overall_pass_rate=float(raw.get("overall_pass_rate", 80.0)),
        top_n=int(raw.get("top_n", 5)),
    )


def _parse_rule(raw: Any, *, defaults: Thresholds) -> Rule:
    if not isinstance(raw, dict):
        return Rule()
    match_raw = raw.get("match", {})
    match = RuleMatch(
        labels=list(match_raw.get("labels", [])),
        paths=list(match_raw.get("paths", [])),
    )
    # Parse thresholds – missing fields inherit from defaults
    thresh_raw = raw.get("thresholds", {})
    thresh = Thresholds(
        s1_pass_rate=float(thresh_raw.get("s1_pass_rate", defaults.s1_pass_rate)),
        overall_pass_rate=float(thresh_raw.get("overall_pass_rate", defaults.overall_pass_rate)),
        top_n=int(thresh_raw.get("top_n", defaults.top_n)),
    )
    return Rule(
        name=str(raw.get("name", "")),
        match=match,
        thresholds=thresh,
    )


# ------------------------------------------------------------------
# Rule matching
# ------------------------------------------------------------------

def _rule_matches(
    rule: Rule,
    *,
    labels: Sequence[str],
    changed_files: Sequence[str],
) -> bool:
    """Return True if *rule* matches the given context.

    A rule matches when **all** specified conditions are satisfied:
    - ``labels``: at least one PR label matches any label in the rule
    - ``paths``: at least one changed file matches any glob in the rule

    If a match field is empty it is ignored (always satisfies).
    A rule with *both* fields empty never matches (safety net).
    """
    m = rule.match
    if not m.labels and not m.paths:
        return False

    label_ok = True
    if m.labels:
        label_set = {l.lower() for l in labels}
        rule_set = {l.lower() for l in m.labels}
        label_ok = bool(label_set & rule_set)

    path_ok = True
    if m.paths:
        path_ok = any(
            fnmatch.fnmatch(f, pat)
            for f in changed_files
            for pat in m.paths
        )

    return label_ok and path_ok


def _merge_thresholds(defaults: Thresholds, overrides: Thresholds) -> Thresholds:
    """Create a new Thresholds with *overrides* layered on *defaults*.

    Currently the rule parser already inherits defaults, so this is a
    pass-through — kept for future partial-override support.
    """
    return Thresholds(
        s1_pass_rate=overrides.s1_pass_rate,
        overall_pass_rate=overrides.overall_pass_rate,
        top_n=overrides.top_n,
    )

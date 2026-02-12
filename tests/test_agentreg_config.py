"""Tests for agentops.config – YAML configuration loader.

Covers:
- load_config() with explicit path / auto-detect / missing
- _parse() validation
- Thresholds / Rule / AgentRegConfig data structures
- resolve_thresholds() with labels / changed_files rule matching
- Edge cases: empty rules, both-match, no-match
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agentops.config import (
    AgentRegConfig,
    Rule,
    RuleMatch,
    Thresholds,
    load_config,
    _rule_matches,
)


# ========================================================================
# Helpers
# ========================================================================

MINIMAL_YAML = """\
thresholds:
  s1_pass_rate: 95
  overall_pass_rate: 70
  top_n: 3
"""

FULL_YAML = """\
thresholds:
  s1_pass_rate: 100
  overall_pass_rate: 80
  top_n: 5

rules:
  - name: hotfix
    match:
      labels: ["hotfix", "emergency"]
    thresholds:
      s1_pass_rate: 100
      overall_pass_rate: 95

  - name: api-paths
    match:
      paths: ["src/api/**"]
    thresholds:
      overall_pass_rate: 90

owner_fallback: my-team
"""


def _write(tmp_path: Path, content: str, name: str = ".agentreg.yml") -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


# ========================================================================
# load_config
# ========================================================================

class TestLoadConfig:
    def test_explicit_path(self, tmp_path: Path):
        p = _write(tmp_path, MINIMAL_YAML)
        cfg = load_config(str(p))
        assert cfg.thresholds.s1_pass_rate == 95
        assert cfg.thresholds.overall_pass_rate == 70
        assert cfg.thresholds.top_n == 3

    def test_full_yaml(self, tmp_path: Path):
        p = _write(tmp_path, FULL_YAML)
        cfg = load_config(str(p))
        assert len(cfg.rules) == 2
        assert cfg.rules[0].name == "hotfix"
        assert cfg.rules[1].name == "api-paths"
        assert cfg.owner_fallback == "my-team"

    def test_missing_explicit_raises(self):
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/.agentreg.yml")

    def test_default_when_no_file(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = load_config()
        assert cfg.thresholds.s1_pass_rate == 100.0
        assert cfg.thresholds.overall_pass_rate == 80.0

    def test_auto_detect(self, tmp_path: Path, monkeypatch):
        _write(tmp_path, MINIMAL_YAML)
        monkeypatch.chdir(tmp_path)
        cfg = load_config()
        assert cfg.thresholds.s1_pass_rate == 95

    def test_invalid_yaml_raises(self, tmp_path: Path):
        p = _write(tmp_path, "thresholds:\n  s1_pass_rate: [bad\n")
        with pytest.raises(ValueError, match="Invalid YAML"):
            load_config(str(p))

    def test_non_mapping_raises(self, tmp_path: Path):
        p = _write(tmp_path, "- just\n- a\n- list\n")
        with pytest.raises(ValueError, match="Expected mapping"):
            load_config(str(p))

    def test_empty_yaml_returns_defaults(self, tmp_path: Path):
        p = _write(tmp_path, "")
        cfg = load_config(str(p))
        assert cfg.thresholds.s1_pass_rate == 100.0


# ========================================================================
# Thresholds defaults
# ========================================================================

class TestThresholds:
    def test_defaults(self):
        t = Thresholds()
        assert t.s1_pass_rate == 100.0
        assert t.overall_pass_rate == 80.0
        assert t.top_n == 5


# ========================================================================
# Rule matching
# ========================================================================

class TestRuleMatching:
    def test_label_match(self):
        rule = Rule(
            name="hotfix",
            match=RuleMatch(labels=["hotfix", "emergency"]),
        )
        assert _rule_matches(rule, labels=["hotfix"], changed_files=[])
        assert _rule_matches(rule, labels=["HOTFIX"], changed_files=[])  # case insensitive
        assert not _rule_matches(rule, labels=["feature"], changed_files=[])

    def test_path_match(self):
        rule = Rule(
            name="api",
            match=RuleMatch(paths=["src/api/**"]),
        )
        assert _rule_matches(rule, labels=[], changed_files=["src/api/handler.py"])
        assert not _rule_matches(rule, labels=[], changed_files=["src/web/app.py"])

    def test_both_must_match(self):
        rule = Rule(
            name="strict",
            match=RuleMatch(labels=["hotfix"], paths=["src/api/**"]),
        )
        # Both match
        assert _rule_matches(rule, labels=["hotfix"], changed_files=["src/api/x.py"])
        # Only label matches
        assert not _rule_matches(rule, labels=["hotfix"], changed_files=["src/web/x.py"])
        # Only path matches
        assert not _rule_matches(rule, labels=["feature"], changed_files=["src/api/x.py"])

    def test_empty_match_never_matches(self):
        rule = Rule(name="empty", match=RuleMatch())
        assert not _rule_matches(rule, labels=["any"], changed_files=["any/file.py"])


# ========================================================================
# resolve_thresholds
# ========================================================================

class TestResolveThresholds:
    def test_no_rules_returns_defaults(self):
        cfg = AgentRegConfig(thresholds=Thresholds(s1_pass_rate=90, overall_pass_rate=70))
        resolved = cfg.resolve_thresholds()
        assert resolved.s1_pass_rate == 90
        assert resolved.overall_pass_rate == 70

    def test_first_matching_rule_wins(self, tmp_path: Path):
        p = _write(tmp_path, FULL_YAML)
        cfg = load_config(str(p))
        resolved = cfg.resolve_thresholds(labels=["hotfix"])
        assert resolved.overall_pass_rate == 95  # from hotfix rule

    def test_path_rule_match(self, tmp_path: Path):
        p = _write(tmp_path, FULL_YAML)
        cfg = load_config(str(p))
        resolved = cfg.resolve_thresholds(changed_files=["src/api/handler.py"])
        assert resolved.overall_pass_rate == 90  # from api-paths rule

    def test_no_rule_matches_returns_defaults(self, tmp_path: Path):
        p = _write(tmp_path, FULL_YAML)
        cfg = load_config(str(p))
        resolved = cfg.resolve_thresholds(labels=["docs"])
        assert resolved.overall_pass_rate == 80  # default

    def test_rule_inherits_unset_from_defaults(self, tmp_path: Path):
        """api-paths rule only sets overall_pass_rate; s1 should inherit."""
        p = _write(tmp_path, FULL_YAML)
        cfg = load_config(str(p))
        resolved = cfg.resolve_thresholds(changed_files=["src/api/x.py"])
        assert resolved.s1_pass_rate == 100  # inherited from defaults
        assert resolved.overall_pass_rate == 90  # from rule

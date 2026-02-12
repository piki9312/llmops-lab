"""Tests for agentops.load_cases – CSV loader with P1 extended columns."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from agentops.load_cases import load_from_csv


def _write_csv(tmp_path: Path, rows: list, fieldnames: list) -> Path:
    p = tmp_path / "cases.csv"
    with open(p, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return p


class TestLoadFromCsvExtended:
    def test_legacy_csv_still_works(self, tmp_path: Path):
        """CSV without owner/tags/min_pass_rate columns loads fine."""
        p = _write_csv(tmp_path, [
            {"case_id": "TC001", "name": "Test", "input_prompt": "Hi",
             "expected_output": "Hello", "category": "greeting", "severity": "S2"},
        ], fieldnames=["case_id", "name", "input_prompt", "expected_output", "category", "severity"])
        cases = load_from_csv(str(p))
        assert len(cases) == 1
        assert cases[0].metadata["severity"] == "S2"
        assert "owner" not in cases[0].metadata

    def test_extended_columns_parsed(self, tmp_path: Path):
        p = _write_csv(tmp_path, [
            {"case_id": "TC001", "name": "Test", "input_prompt": "Hi",
             "expected_output": "Hello", "category": "api", "severity": "S1",
             "owner": "api-team", "tags": "core;payment", "min_pass_rate": "100"},
        ], fieldnames=["case_id", "name", "input_prompt", "expected_output",
                       "category", "severity", "owner", "tags", "min_pass_rate"])
        cases = load_from_csv(str(p))
        assert cases[0].metadata["owner"] == "api-team"
        assert cases[0].metadata["tags"] == ["core", "payment"]
        assert cases[0].metadata["min_pass_rate"] == 100.0

    def test_empty_extended_columns_omitted(self, tmp_path: Path):
        p = _write_csv(tmp_path, [
            {"case_id": "TC001", "name": "Test", "input_prompt": "Hi",
             "expected_output": "Hello", "category": "greeting", "severity": "S2",
             "owner": "", "tags": "", "min_pass_rate": ""},
        ], fieldnames=["case_id", "name", "input_prompt", "expected_output",
                       "category", "severity", "owner", "tags", "min_pass_rate"])
        cases = load_from_csv(str(p))
        assert "owner" not in cases[0].metadata
        assert "tags" not in cases[0].metadata
        assert "min_pass_rate" not in cases[0].metadata

    def test_invalid_min_pass_rate_ignored(self, tmp_path: Path):
        p = _write_csv(tmp_path, [
            {"case_id": "TC001", "name": "Test", "input_prompt": "Hi",
             "expected_output": "Hello", "category": "api", "severity": "S1",
             "owner": "", "tags": "", "min_pass_rate": "not_a_number"},
        ], fieldnames=["case_id", "name", "input_prompt", "expected_output",
                       "category", "severity", "owner", "tags", "min_pass_rate"])
        cases = load_from_csv(str(p))
        assert "min_pass_rate" not in cases[0].metadata

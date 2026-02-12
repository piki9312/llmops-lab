"""
Tests for agentops.load_cases module.
"""

from pathlib import Path

import pytest

from agentops.load_cases import load_from_csv


def test_load_from_csv():
    """Test loading test cases from CSV file."""
    # Test that the function exists and can be called
    # Actual functionality test would require a test CSV file
    assert callable(load_from_csv)


def test_load_from_csv_with_real_file():
    """Test loading from the actual test cases file."""
    cases_file = Path("cases/agent_regression.csv")

    if cases_file.exists():
        cases = load_from_csv(str(cases_file))
        assert len(cases) > 0
        assert cases[0].case_id is not None
        assert cases[0].name is not None
        assert cases[0].input_prompt is not None

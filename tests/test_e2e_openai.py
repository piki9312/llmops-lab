"""E2E tests using OpenAI provider (requires OPENAI_API_KEY).

Run explicitly with::

    pytest tests/test_e2e_openai.py -v -k openai

These tests are skipped by default in the regular test suite
(the keyword "openai" is excluded via ``-k "not openai"``).
"""

from __future__ import annotations

import json
import os
import pytest

from agentops.runner import RegressionRunner
from agentops.models import TestCase

# Skip entire module if no API key
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)

OPENAI_CONFIG = {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "timeout_seconds": 30,
    "max_retries": 2,
}


class TestOpenAIE2E:
    """End-to-end tests hitting the real OpenAI API."""

    # ------------------------------------------------------------------
    # S1: JSON contract validation
    # ------------------------------------------------------------------

    def test_s1_valid_json_contract(self):
        """S1 case: model should return JSON matching the expected schema."""
        runner = RegressionRunner(use_llmops=True, llmops_config=OPENAI_CONFIG)

        expected = json.dumps({
            "location": "Tokyo",
            "temperature": 15,
            "condition": "cloudy",
        })

        case = TestCase(
            case_id="E2E_S1_001",
            name="Weather API JSON",
            input_prompt="Call weather API for Tokyo",
            expected_output=expected,
            metadata={"severity": "S1", "category": "api"},
        )

        result = runner.run_case(case)

        print(f"\n--- E2E_S1_001 ---")
        print(f"  passed: {result.passed}")
        print(f"  failure_type: {result.failure_type}")
        print(f"  latency_ms: {result.latency_ms:.1f}")
        print(f"  tokens: {result.total_tokens}")
        print(f"  cost: ${result.cost_usd:.6f}")
        print(f"  output: {result.actual_output[:200]}")

        # Must be valid JSON
        parsed = json.loads(result.actual_output)
        assert isinstance(parsed, dict)
        # Contract keys present
        assert "location" in parsed
        # Real metrics captured
        assert result.latency_ms > 0
        assert result.total_tokens > 0
        assert result.cost_usd > 0

    def test_s1_payment_contract(self):
        """S1 case: payment processing JSON contract."""
        runner = RegressionRunner(use_llmops=True, llmops_config=OPENAI_CONFIG)

        expected = json.dumps({
            "transaction_id": "tx_123",
            "amount": 100.00,
            "currency": "USD",
            "status": "completed",
        })

        case = TestCase(
            case_id="E2E_S1_002",
            name="Payment Processing",
            input_prompt="Process payment of $100",
            expected_output=expected,
            metadata={"severity": "S1", "category": "api"},
        )

        result = runner.run_case(case)

        print(f"\n--- E2E_S1_002 ---")
        print(f"  passed: {result.passed}")
        print(f"  failure_type: {result.failure_type}")
        print(f"  latency_ms: {result.latency_ms:.1f}")
        print(f"  output: {result.actual_output[:200]}")

        # Should produce valid JSON
        parsed = json.loads(result.actual_output)
        assert isinstance(parsed, dict)
        # Should have the required keys (contract check)
        for key in ["transaction_id", "amount", "currency", "status"]:
            assert key in parsed, f"Missing key: {key}"
        assert result.passed is True

    # ------------------------------------------------------------------
    # S2: Semantic / text-based evaluation
    # ------------------------------------------------------------------

    def test_s2_factual_question(self):
        """S2 case: factual question (capital of France)."""
        runner = RegressionRunner(use_llmops=True, llmops_config=OPENAI_CONFIG)

        case = TestCase(
            case_id="E2E_S2_001",
            name="Capital of France",
            input_prompt="What is the capital of France?",
            expected_output="Paris",
            metadata={"severity": "S2", "category": "factual"},
        )

        result = runner.run_case(case)

        print(f"\n--- E2E_S2_001 ---")
        print(f"  passed: {result.passed}")
        print(f"  output: {result.actual_output[:200]}")
        print(f"  latency_ms: {result.latency_ms:.1f}")

        assert result.passed is True
        assert "paris" in result.actual_output.lower()
        assert result.latency_ms > 0

    def test_s2_math(self):
        """S2 case: math calculation."""
        runner = RegressionRunner(use_llmops=True, llmops_config=OPENAI_CONFIG)

        case = TestCase(
            case_id="E2E_S2_002",
            name="Math 15×8",
            input_prompt="What is 15 multiplied by 8?",
            expected_output="120",
            metadata={"severity": "S2", "category": "math"},
        )

        result = runner.run_case(case)

        print(f"\n--- E2E_S2_002 ---")
        print(f"  passed: {result.passed}")
        print(f"  output: {result.actual_output[:200]}")

        assert result.passed is True
        assert "120" in result.actual_output

    # ------------------------------------------------------------------
    # Full suite via run_all
    # ------------------------------------------------------------------

    def test_mini_suite_run_all(self):
        """Run a small mixed S1/S2 suite via run_all()."""
        runner = RegressionRunner(use_llmops=True, llmops_config=OPENAI_CONFIG)

        cases = [
            TestCase(
                case_id="MINI_S1",
                name="Auth JSON",
                input_prompt="Authenticate user with token xyz123",
                expected_output=json.dumps({
                    "user_id": "usr_456",
                    "authenticated": True,
                }),
                metadata={"severity": "S1", "category": "api"},
            ),
            TestCase(
                case_id="MINI_S2",
                name="Greeting",
                input_prompt="Hello! How are you today?",
                expected_output="A polite greeting response",
                metadata={"severity": "S2", "category": "greeting"},
            ),
        ]

        report = runner.run_all(cases, run_id="e2e-mini")

        print(f"\n--- Mini Suite ---")
        print(f"  total: {report.total_cases}")
        print(f"  passed: {report.passed_cases}")
        print(f"  failed: {report.failed_cases}")
        for r in report.results:
            print(f"  {r.case_id}: passed={r.passed} lat={r.latency_ms:.0f}ms "
                  f"tokens={r.total_tokens} ${r.cost_usd:.6f}")

        assert report.total_cases == 2
        # At least one should pass
        assert report.passed_cases >= 1
        # All results have real metrics
        for r in report.results:
            assert r.latency_ms > 0
            assert r.total_tokens > 0

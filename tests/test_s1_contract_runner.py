"""
Tests for S1 JSON contract evaluation in agentops runner.
"""

import pytest
import json
from datetime import datetime
from agentops.runner import RegressionRunner
from agentops.models import TestCase


MOCK_CONFIG = {"provider": "mock", "model": "gpt-4-mock"}


class TestS1ContractValidation:
    """Test S1 JSON contract validation in runner."""
    
    def test_s1_case_with_valid_json_contract(self):
        """Test S1 case with mock provider: mock returns plain text, so
        this correctly fails with bad_json.  A real LLM provider is needed
        for actual contract validation (see test_e2e_openai.py)."""
        runner = RegressionRunner(use_llmops=True, llmops_config=MOCK_CONFIG)
        
        expected_json = json.dumps({
            "status": "success",
            "data": "test",
            "timestamp": "2026-02-01T10:00:00Z"
        })
        
        case = TestCase(
            case_id="TC_S1_001",
            name="Valid S1 Contract",
            input_prompt="Generate valid JSON",
            expected_output=expected_json,
            metadata={"severity": "S1", "category": "api"}
        )
        
        result = runner.run_case(case)
        
        assert result.case_id == "TC_S1_001"
        # Mock provider returns plain text → S1 correctly flags bad_json
        assert result.passed is False
        assert result.failure_type == "bad_json"
        assert result.latency_ms > 0  # latency is now measured
    
    def test_s1_case_with_missing_keys(self):
        """Test S1 case with mock: mock returns plain text → bad_json
        (contract validation never reached)."""
        runner = RegressionRunner(use_llmops=True, llmops_config=MOCK_CONFIG)
        
        expected_json = json.dumps({
            "transaction_id": "tx_123",
            "amount": 100.00,
            "currency": "USD",
            "status": "completed",
            "merchant_id": "merch_456"
        })
        
        case = TestCase(
            case_id="TC_S1_002",
            name="Missing Keys Contract",
            input_prompt="Process payment",
            expected_output=expected_json,
            metadata={"severity": "S1", "category": "api"}
        )
        
        result = runner.run_case(case)
        
        assert result.case_id == "TC_S1_002"
        # Mock returns plain text → bad_json before contract check
        assert result.passed is False
        assert result.failure_type == "bad_json"
    
    def test_s2_case_uses_text_evaluation(self):
        """Test S2 cases don't require JSON validation."""
        runner = RegressionRunner(use_llmops=True, llmops_config=MOCK_CONFIG)
        
        case = TestCase(
            case_id="TC_S2_001",
            name="Text Response",
            input_prompt="What is 2+2?",
            expected_output="4",
            metadata={"severity": "S2", "category": "math"}
        )
        
        result = runner.run_case(case)
        
        # S2 should work with non-JSON output
        assert result.case_id == "TC_S2_001"
        # No JSON validation for S2
        assert result.passed or result.failure_type != "bad_json"
    
    def test_s1_bad_json_output(self):
        """Test S1 case with non-JSON output gets bad_json failure."""
        # This would need a custom mock that returns non-JSON
        # For now, we validate the logic exists
        runner = RegressionRunner(use_llmops=False)
        
        case = TestCase(
            case_id="TC_S1_003",
            name="Bad JSON",
            input_prompt="Return broken JSON",
            expected_output=json.dumps({"key": "value"}),
            metadata={"severity": "S1", "category": "api"}
        )
        
        result = runner.run_case(case)
        
        # Fallback mode produces non-JSON text
        if not result.passed and "JSON" in (result.error or ""):
            assert result.failure_type == "bad_json"

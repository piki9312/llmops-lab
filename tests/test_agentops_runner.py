"""
Tests for agentops.runner module.
"""

import pytest
from agentops.runner import RegressionRunner
from agentops.models import TestCase


MOCK_CONFIG = {"provider": "mock", "model": "gpt-4-mock"}


def test_runner_creation():
    """Test RegressionRunner can be instantiated with llmops integration."""
    runner = RegressionRunner(use_llmops=True, llmops_config=MOCK_CONFIG)
    assert runner is not None
    assert runner.use_llmops is True
    # llm_client should be initialized when use_llmops=True
    assert runner.llm_client is not None


def test_runner_without_llmops():
    """Test RegressionRunner can be instantiated without llmops."""
    runner = RegressionRunner(use_llmops=False)
    assert runner is not None
    assert runner.use_llmops is False
    assert runner.llm_client is None


@pytest.mark.asyncio
async def test_run_single_case():
    """Test running a single test case via llmops."""
    runner = RegressionRunner(use_llmops=True, llmops_config=MOCK_CONFIG)
    
    case = TestCase(
        case_id="TC001",
        name="Test",
        input_prompt="Hello"
    )
    
    # Run in sync context but handle the async nature properly
    result = runner.run_case(case)
    
    assert result.case_id == "TC001"
    # Verify llmops metrics are populated
    assert result.provider == "mock"
    assert result.model is not None
    assert result.latency_ms >= 0

"""Unit tests for pricing module."""

import pytest

from llmops.pricing import calculate_cost_usd, format_cost_usd, OPENAI_PRICING


class TestCalculateCostUSD:
    """Test calculate_cost_usd function."""

    def test_gpt4o_pricing(self):
        """Test GPT-4o pricing calculation."""
        cost = calculate_cost_usd(
            model="gpt-4o",
            prompt_tokens=1000,
            completion_tokens=1000,
            provider="openai",
        )
        # Input: 1000 * 0.005 / 1000 = 0.005
        # Output: 1000 * 0.015 / 1000 = 0.015
        # Total: 0.020
        assert cost == pytest.approx(0.020, abs=1e-6)

    def test_gpt4o_mini_pricing(self):
        """Test GPT-4o Mini pricing calculation."""
        cost = calculate_cost_usd(
            model="gpt-4o-mini",
            prompt_tokens=1000,
            completion_tokens=1000,
            provider="openai",
        )
        # Input: 1000 * 0.00015 / 1000 = 0.00015
        # Output: 1000 * 0.0006 / 1000 = 0.0006
        # Total: 0.00075
        assert cost == pytest.approx(0.00075, abs=1e-6)

    def test_gpt35_pricing(self):
        """Test GPT-3.5 Turbo pricing."""
        cost = calculate_cost_usd(
            model="gpt-3.5-turbo",
            prompt_tokens=1000,
            completion_tokens=500,
            provider="openai",
        )
        # Input: 1000 * 0.0005 / 1000 = 0.0005
        # Output: 500 * 0.0015 / 1000 = 0.00075
        # Total: 0.00125
        assert cost == pytest.approx(0.00125, abs=1e-6)

    def test_mock_provider_is_free(self):
        """Test that mock provider has zero cost."""
        cost = calculate_cost_usd(
            model="gpt-4-mock",
            prompt_tokens=10000,
            completion_tokens=10000,
            provider="mock",
        )
        assert cost == 0.0

    def test_zero_tokens(self):
        """Test zero token calculation."""
        cost = calculate_cost_usd(
            model="gpt-4o",
            prompt_tokens=0,
            completion_tokens=0,
            provider="openai",
        )
        assert cost == 0.0

    def test_large_token_count(self):
        """Test large token count."""
        cost = calculate_cost_usd(
            model="gpt-4o",
            prompt_tokens=1000000,
            completion_tokens=1000000,
            provider="openai",
        )
        # Input: 1000000 / 1000 * 0.005 = 5000
        # Output: 1000000 / 1000 * 0.015 = 15000
        # Total: 20.0 (wait, this is wrong)
        # Actually: (1000000 / 1000) * 0.005 = 1000 * 0.005 = 5.0
        #          (1000000 / 1000) * 0.015 = 1000 * 0.015 = 15.0
        # Total: 20.0
        assert cost == pytest.approx(20.0, abs=1e-3)

    def test_unknown_model_defaults_to_free(self):
        """Test that unknown models return 0.0 cost."""
        cost = calculate_cost_usd(
            model="unknown-model",
            prompt_tokens=1000,
            completion_tokens=1000,
            provider="openai",
        )
        # Unknown model returns 0.0
        assert cost == 0.0


class TestFormatCostUSD:
    """Test format_cost_usd function."""

    def test_format_large_cost(self):
        """Test formatting large cost."""
        formatted = format_cost_usd(1.234567)
        assert formatted == "$1.2346"  # 4 decimal places for >= 0.001

    def test_format_small_cost(self):
        """Test formatting small cost."""
        formatted = format_cost_usd(0.00015)
        assert formatted == "$0.000150"  # 6 decimal places for < 0.001

    def test_format_zero_cost(self):
        """Test formatting zero cost."""
        formatted = format_cost_usd(0.0)
        assert formatted == "$0.00"  # Special case for zero

    def test_format_contains_dollar_sign(self):
        """Test that formatted cost contains dollar sign."""
        formatted = format_cost_usd(0.5)
        assert formatted.startswith("$")

    def test_format_mid_range(self):
        """Test formatting mid-range cost."""
        formatted = format_cost_usd(0.05)
        # >= 0.001, so 4 decimal places
        assert formatted == "$0.0500"


class TestPricingTable:
    """Test pricing table integrity."""

    def test_all_models_have_input_output_rates(self):
        """Test that all models have input and output rates."""
        for model, rates in OPENAI_PRICING.items():
            assert "input" in rates, f"Model {model} missing input rate"
            assert "output" in rates, f"Model {model} missing output rate"
            assert isinstance(rates["input"], (int, float))
            assert isinstance(rates["output"], (int, float))
            assert rates["input"] >= 0
            assert rates["output"] >= 0

    def test_gpt4o_is_defined(self):
        """Test that GPT-4o pricing is defined."""
        assert "gpt-4o" in OPENAI_PRICING
        assert OPENAI_PRICING["gpt-4o"]["input"] == 0.005
        assert OPENAI_PRICING["gpt-4o"]["output"] == 0.015

    def test_mock_is_free(self):
        """Test that mock provider is free."""
        assert "gpt-4-mock" in OPENAI_PRICING
        assert OPENAI_PRICING["gpt-4-mock"]["input"] == 0.0
        assert OPENAI_PRICING["gpt-4-mock"]["output"] == 0.0

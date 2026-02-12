"""Tests for configuration and environment variable overrides."""

import os

import pytest

from llmops.config import (
    apply_env_overrides,
    get_env_bool,
    get_env_float,
    get_env_int,
)


class TestEnvHelpers:
    """Test environment variable helper functions."""

    def test_get_env_bool_true(self, monkeypatch):
        """Test get_env_bool with true values."""
        for value in ["true", "True", "TRUE", "1", "yes", "YES", "on", "ON"]:
            monkeypatch.setenv("TEST_BOOL", value)
            assert get_env_bool("TEST_BOOL", False) is True

    def test_get_env_bool_false(self, monkeypatch):
        """Test get_env_bool with false values."""
        for value in ["false", "False", "FALSE", "0", "no", "NO", "off", "OFF"]:
            monkeypatch.setenv("TEST_BOOL", value)
            assert get_env_bool("TEST_BOOL", True) is False

    def test_get_env_bool_default(self, monkeypatch):
        """Test get_env_bool returns default when not set."""
        monkeypatch.delenv("TEST_BOOL", raising=False)
        assert get_env_bool("TEST_BOOL", True) is True
        assert get_env_bool("TEST_BOOL", False) is False

    def test_get_env_int_valid(self, monkeypatch):
        """Test get_env_int with valid integer."""
        monkeypatch.setenv("TEST_INT", "42")
        assert get_env_int("TEST_INT", 0) == 42

    def test_get_env_int_invalid(self, monkeypatch):
        """Test get_env_int with invalid value returns default."""
        monkeypatch.setenv("TEST_INT", "not_a_number")
        assert get_env_int("TEST_INT", 10) == 10

    def test_get_env_int_default(self, monkeypatch):
        """Test get_env_int returns default when not set."""
        monkeypatch.delenv("TEST_INT", raising=False)
        assert get_env_int("TEST_INT", 99) == 99

    def test_get_env_float_valid(self, monkeypatch):
        """Test get_env_float with valid float."""
        monkeypatch.setenv("TEST_FLOAT", "3.14")
        assert get_env_float("TEST_FLOAT", 0.0) == 3.14

    def test_get_env_float_invalid(self, monkeypatch):
        """Test get_env_float with invalid value returns default."""
        monkeypatch.setenv("TEST_FLOAT", "not_a_number")
        assert get_env_float("TEST_FLOAT", 2.5) == 2.5

    def test_get_env_float_default(self, monkeypatch):
        """Test get_env_float returns default when not set."""
        monkeypatch.delenv("TEST_FLOAT", raising=False)
        assert get_env_float("TEST_FLOAT", 1.5) == 1.5


class TestApplyEnvOverrides:
    """Test configuration override with environment variables."""

    def test_no_env_vars_returns_original(self, monkeypatch):
        """Test that config is unchanged when no env vars set."""
        # Clear all relevant env vars
        for key in ["LLM_PROVIDER", "LLM_MODEL", "CACHE_ENABLED"]:
            monkeypatch.delenv(key, raising=False)

        config = {"provider": "mock", "model": "test"}
        result = apply_env_overrides(config)

        assert result["provider"] == "mock"
        assert result["model"] == "test"

    def test_provider_override(self, monkeypatch):
        """Test LLM_PROVIDER override."""
        monkeypatch.setenv("LLM_PROVIDER", "openai")

        config = {"provider": "mock"}
        result = apply_env_overrides(config)

        assert result["provider"] == "openai"

    def test_model_override(self, monkeypatch):
        """Test LLM_MODEL override."""
        monkeypatch.setenv("LLM_MODEL", "gpt-4o")

        config = {"model": "gpt-4-mock"}
        result = apply_env_overrides(config)

        assert result["model"] == "gpt-4o"

    def test_timeout_override(self, monkeypatch):
        """Test LLM_TIMEOUT_SECONDS override."""
        monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "60")

        config = {"timeout_seconds": 30}
        result = apply_env_overrides(config)

        assert result["timeout_seconds"] == 60

    def test_max_retries_override(self, monkeypatch):
        """Test LLM_MAX_RETRIES override."""
        monkeypatch.setenv("LLM_MAX_RETRIES", "5")

        config = {"max_retries": 2}
        result = apply_env_overrides(config)

        assert result["max_retries"] == 5

    def test_cache_enabled_override(self, monkeypatch):
        """Test CACHE_ENABLED override."""
        monkeypatch.setenv("CACHE_ENABLED", "false")

        config = {"cache_enabled": True}
        result = apply_env_overrides(config)

        assert result["cache_enabled"] is False

    def test_cache_ttl_override(self, monkeypatch):
        """Test CACHE_TTL_SECONDS override."""
        monkeypatch.setenv("CACHE_TTL_SECONDS", "1200")

        config = {"cache_ttl_seconds": 600}
        result = apply_env_overrides(config)

        assert result["cache_ttl_seconds"] == 1200

    def test_cache_max_entries_override(self, monkeypatch):
        """Test CACHE_MAX_ENTRIES override."""
        monkeypatch.setenv("CACHE_MAX_ENTRIES", "512")

        config = {"cache_max_entries": 256}
        result = apply_env_overrides(config)

        assert result["cache_max_entries"] == 512

    def test_rate_limit_qps_override(self, monkeypatch):
        """Test RATE_LIMIT_QPS override."""
        monkeypatch.setenv("RATE_LIMIT_QPS", "20.5")

        config = {"rate_limit_qps": None}
        result = apply_env_overrides(config)

        assert result["rate_limit_qps"] == 20.5

    def test_rate_limit_tpm_override(self, monkeypatch):
        """Test RATE_LIMIT_TPM override."""
        monkeypatch.setenv("RATE_LIMIT_TPM", "50000")

        config = {"rate_limit_tpm": None}
        result = apply_env_overrides(config)

        assert result["rate_limit_tpm"] == 50000.0

    def test_prompt_version_override(self, monkeypatch):
        """Test PROMPT_VERSION override."""
        monkeypatch.setenv("PROMPT_VERSION", "2.0")

        config = {"prompt_version": "1.0"}
        result = apply_env_overrides(config)

        assert result["prompt_version"] == "2.0"

    def test_log_dir_override(self, monkeypatch):
        """Test LOG_DIR override."""
        monkeypatch.setenv("LOG_DIR", "/var/log/llm")

        config = {"log_dir": "runs/logs"}
        result = apply_env_overrides(config)

        assert result["log_dir"] == "/var/log/llm"

    def test_multiple_overrides(self, monkeypatch):
        """Test multiple environment variables at once."""
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("LLM_MODEL", "gpt-4o")
        monkeypatch.setenv("CACHE_ENABLED", "false")
        monkeypatch.setenv("RATE_LIMIT_QPS", "10")

        config = {
            "provider": "mock",
            "model": "gpt-4-mock",
            "cache_enabled": True,
            "rate_limit_qps": None,
        }
        result = apply_env_overrides(config)

        assert result["provider"] == "openai"
        assert result["model"] == "gpt-4o"
        assert result["cache_enabled"] is False
        assert result["rate_limit_qps"] == 10.0

    def test_does_not_mutate_original(self, monkeypatch):
        """Test that original config is not mutated."""
        monkeypatch.setenv("LLM_PROVIDER", "openai")

        config = {"provider": "mock"}
        original_provider = config["provider"]

        result = apply_env_overrides(config)

        assert config["provider"] == original_provider  # Original unchanged
        assert result["provider"] == "openai"  # Result has override

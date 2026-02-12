"""Configuration utilities for environment variable overrides.

Supports loading config from YAML and overriding with environment variables.
"""

import os
from typing import Any, Dict, Optional


def get_env_bool(key: str, default: bool) -> bool:
    """Get boolean from environment variable.

    Args:
        key: Environment variable name
        default: Default value if not set

    Returns:
        Boolean value
    """
    value = os.getenv(key)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes", "on")


def get_env_int(key: str, default: Optional[int]) -> Optional[int]:
    """Get integer from environment variable.

    Args:
        key: Environment variable name
        default: Default value if not set

    Returns:
        Integer value or None
    """
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def get_env_float(key: str, default: Optional[float]) -> Optional[float]:
    """Get float from environment variable.

    Args:
        key: Environment variable name
        default: Default value if not set

    Returns:
        Float value or None
    """
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def apply_env_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    """Apply environment variable overrides to config.

    Supported environment variables:
    - LLM_PROVIDER: Provider name (mock, openai)
    - LLM_MODEL: Model name
    - LLM_TIMEOUT_SECONDS: Request timeout
    - LLM_MAX_RETRIES: Maximum retry attempts
    - CACHE_ENABLED: Enable/disable caching (true/false)
    - CACHE_TTL_SECONDS: Cache TTL in seconds
    - CACHE_MAX_ENTRIES: Maximum cache entries
    - RATE_LIMIT_QPS: Queries per second limit
    - RATE_LIMIT_TPM: Tokens per minute limit
    - PROMPT_VERSION: Default prompt version
    - LOG_DIR: Log directory path
    - OPENAI_API_KEY: OpenAI API key (handled by OpenAI SDK)

    Args:
        config: Base configuration dict

    Returns:
        Configuration with env var overrides applied
    """
    # Create a copy to avoid mutating original
    config = config.copy()

    # Provider settings
    if os.getenv("LLM_PROVIDER"):
        config["provider"] = os.getenv("LLM_PROVIDER")

    if os.getenv("LLM_MODEL"):
        config["model"] = os.getenv("LLM_MODEL")

    # Execution settings
    config["timeout_seconds"] = get_env_int(
        "LLM_TIMEOUT_SECONDS", config.get("timeout_seconds", 30)
    )

    config["max_retries"] = get_env_int("LLM_MAX_RETRIES", config.get("max_retries", 2))

    # Cache settings
    config["cache_enabled"] = get_env_bool("CACHE_ENABLED", config.get("cache_enabled", True))

    config["cache_ttl_seconds"] = get_env_int(
        "CACHE_TTL_SECONDS", config.get("cache_ttl_seconds", 600)
    )

    config["cache_max_entries"] = get_env_int(
        "CACHE_MAX_ENTRIES", config.get("cache_max_entries", 256)
    )

    # Rate limiting
    rate_limit_qps = get_env_float("RATE_LIMIT_QPS", config.get("rate_limit_qps"))
    if rate_limit_qps is not None:
        config["rate_limit_qps"] = rate_limit_qps

    rate_limit_tpm = get_env_float("RATE_LIMIT_TPM", config.get("rate_limit_tpm"))
    if rate_limit_tpm is not None:
        config["rate_limit_tpm"] = rate_limit_tpm

    # Observability
    if os.getenv("PROMPT_VERSION"):
        config["prompt_version"] = os.getenv("PROMPT_VERSION")

    if os.getenv("LOG_DIR"):
        config["log_dir"] = os.getenv("LOG_DIR")

    return config

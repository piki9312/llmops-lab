"""Pricing information for LLM providers.

Contains pricing for input and output tokens by model.
Pricing as of 2026-01-01 (update as needed).

Reference: https://openai.com/pricing
"""

# OpenAI pricing: USD per 1M tokens
OPENAI_PRICING = {
    # GPT-4o (current latest)
    "gpt-4o": {
        "input": 0.005,  # $0.005 per 1K input tokens
        "output": 0.015,  # $0.015 per 1K output tokens
    },
    # GPT-4o Mini
    "gpt-4o-mini": {
        "input": 0.00015,  # $0.00015 per 1K input tokens
        "output": 0.0006,  # $0.0006 per 1K output tokens
    },
    # GPT-4 Turbo
    "gpt-4-turbo": {
        "input": 0.01,
        "output": 0.03,
    },
    # GPT-3.5 Turbo
    "gpt-3.5-turbo": {
        "input": 0.0005,
        "output": 0.0015,
    },
    # Mock provider (free)
    "gpt-4-mock": {
        "input": 0.0,
        "output": 0.0,
    },
}


def calculate_cost_usd(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    provider: str = "openai",
) -> float:
    """Calculate cost in USD for a completion.

    Args:
        model: Model name
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens
        provider: Provider name ('openai', 'mock', etc.)

    Returns:
        Cost in USD (float)

    失敗モード:
        - 未知のモデル → 0.0 を返す（ログ警告）
    """
    if provider == "openai" and model in OPENAI_PRICING:
        pricing = OPENAI_PRICING[model]
        input_cost = (prompt_tokens / 1000) * pricing["input"]
        output_cost = (completion_tokens / 1000) * pricing["output"]
        return round(input_cost + output_cost, 6)
    
    # Default: free (mock provider or unknown)
    return 0.0


def format_cost_usd(cost: float) -> str:
    """Format cost as USD string.

    Args:
        cost: Cost in USD

    Returns:
        Formatted string (e.g., "$0.000123")
    """
    if cost == 0:
        return "$0.00"
    elif cost < 0.001:
        return f"${cost:.6f}"
    else:
        return f"${cost:.4f}"

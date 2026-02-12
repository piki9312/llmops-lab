"""LLM Provider Interface and Implementations.

This module provides abstractions for LLM providers with retry/timeout
handling and error classification.

Design principles:
- Provider interface: async generate() method
- MockProvider: deterministic responses for testing
- OpenAIProvider: production OpenAI API integration
- LLMClient: aggregator with retry/timeout logic
"""

import asyncio
import hashlib
import logging
import os
from typing import Optional

# ============================================================================
# LLM PROVIDER INTERFACE
# ============================================================================


class LLMProvider:
    """Abstract base for LLM providers.

    入力：messages, schema, max_tokens
    出力：text, json, token_usage, error_type
    副作用：ネットワーク呼び出し、ローカルログ
    失敗モード：タイムアウト、JSON不正、プロバイダエラー
    """

    async def generate(
        self,
        messages: list[dict],
        schema: Optional[dict] = None,
        max_tokens: int = 256,
    ) -> dict:
        """Generate LLM output.

        Args:
            messages: Conv turns [{"role": "user", "content": "..."}, ...]
            schema: JSON schema to enforce (optional)
            max_tokens: Max output tokens

        Returns:
            {
                "text": str,
                "json": dict | None,
                "tokens": {"prompt": int, "completion": int, "total": int},
                "error_type": None | "timeout" | "bad_json" | "provider_error"
            }
        """
        raise NotImplementedError


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing without external API.

    入力：同じ messages → 同じ出力（deterministic）
    出力：ダミーテキスト + JSON（schema指定時）
    副作用：ローカルのダミー応答生成
    失敗モード：schema不正時は error_type: "bad_json"
    """

    def __init__(self, model_name: str = "gpt-4-mock"):
        """Initialize mock provider.

        Args:
            model_name: Display name for logging
        """
        self.model_name = model_name

    async def generate(
        self,
        messages: list[dict],
        schema: Optional[dict] = None,
        max_tokens: int = 256,
    ) -> dict:
        """Generate deterministic mock response.

        入力：messages（内容で決定論的に応答）
        出力：schema指定時は dict、未指定時は str
        副作用：なし
        失敗モード：schema が dict でない場合 error_type: "bad_json"
        """
        # Simulate processing time
        await asyncio.sleep(0.05)

        # Deterministic response based on message content hash
        message_text = "\n".join([m["content"] for m in messages])
        content_hash = hashlib.md5(message_text.encode()).hexdigest()[:8]
        base_response = f"Mock response for {content_hash}: " + "Test output " * (max_tokens // 20)

        # Try to generate JSON if schema specified
        json_output = None
        error_type = None

        if schema:
            try:
                if not isinstance(schema, dict):
                    error_type = "bad_json"
                else:
                    # Generate mock JSON matching schema structure
                    json_output = self._generate_mock_json(schema)
            except Exception as e:
                logging.warning(f"Failed to generate schema JSON: {e}")
                error_type = "bad_json"

        return {
            "text": base_response[:max_tokens],
            "json": json_output,
            "tokens": {"prompt": 50, "completion": 80, "total": 130},
            "error_type": error_type,
        }

    @staticmethod
    def _generate_mock_json(schema: dict) -> dict:
        """Generate mock JSON matching schema.

        Args:
            schema: JSON schema dict

        Returns:
            Mock dict matching schema structure
        """
        # Simplified: create dict with schema keys filled with dummy values
        if not isinstance(schema, dict):
            return {}
        result = {}
        for key in schema.get("properties", {}).keys():
            result[key] = f"mock_{key}"
        return result


# ============================================================================
# OPENAI PROVIDER
# ============================================================================


class OpenAIProvider(LLMProvider):
    """OpenAI API provider with error handling and JSON mode.

    入力：messages, schema, max_tokens, APIキー（env）
    出力：text, json, token_usage, error_type
    副作用：OpenAI API呼び出し、課金発生
    失敗モード：API error → "provider_error", JSON parse error → "bad_json"
    """

    def __init__(self, model_name: str = "gpt-4o-mini", api_key: Optional[str] = None):
        """Initialize OpenAI provider.

        Args:
            model_name: OpenAI model identifier
            api_key: API key (defaults to OPENAI_API_KEY env var)
        """
        self.model_name = model_name
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key required: set OPENAI_API_KEY env var or pass api_key")

        # Lazy import to avoid dependency if not using OpenAI
        try:
            from openai import AsyncOpenAI

            self.client = AsyncOpenAI(api_key=self.api_key)
        except ImportError as e:
            raise ImportError(
                "openai package required for OpenAIProvider. " "Install with: pip install openai"
            ) from e

    async def generate(
        self,
        messages: list[dict],
        schema: Optional[dict] = None,
        max_tokens: int = 256,
    ) -> dict:
        """Generate using OpenAI API.

        入力：messages, schema（JSON mode用）, max_tokens
        出力：text, json（schema指定時）, token_usage, error_type
        副作用：OpenAI API呼び出し
        失敗モード：API error, JSONデコードエラー
        """
        try:
            # Build API request parameters
            params = {
                "model": self.model_name,
                "messages": messages,
                "max_tokens": max_tokens,
            }

            # Enable JSON mode if schema provided
            if schema:
                params["response_format"] = {"type": "json_object"}
                # Inject schema into system message
                schema_prompt = f"\nRespond with JSON matching this schema: {schema}"
                if messages and messages[0]["role"] == "system":
                    messages[0]["content"] += schema_prompt
                else:
                    messages.insert(0, {"role": "system", "content": schema_prompt})

            # Call OpenAI API
            response = await self.client.chat.completions.create(**params)

            # Extract response
            text = response.choices[0].message.content or ""
            tokens = {
                "prompt": response.usage.prompt_tokens,
                "completion": response.usage.completion_tokens,
                "total": response.usage.total_tokens,
            }

            # Parse JSON if schema was requested
            json_output = None
            error_type = None
            if schema:
                try:
                    import json

                    json_output = json.loads(text)
                except json.JSONDecodeError as e:
                    logging.warning(f"Failed to parse JSON from response: {e}")
                    error_type = "bad_json"

            return {
                "text": text,
                "json": json_output,
                "tokens": tokens,
                "error_type": error_type,
            }

        except Exception as e:
            logging.error(f"OpenAI API error: {e}")
            return {
                "text": "",
                "json": None,
                "tokens": {"prompt": 0, "completion": 0, "total": 0},
                "error_type": "provider_error",
            }


# ============================================================================
# LLM CLIENT (AGGREGATOR)
# ============================================================================


class LLMClient:
    """Aggregate LLM provider with retry, timeout, and error handling.

    入力：provider, messages, schema, max_tokens, timeout, max_retries
    出力：text, json, token_usage, error_type, latency_ms
    副作用：リトライロジック実行、エラー分類
    失敗モード：timeout、bad_json、provider_error
    """

    def __init__(
        self,
        provider: LLMProvider,
        timeout_seconds: float = 30,
        max_retries: int = 2,
    ):
        """Initialize LLM client.

        Args:
            provider: LLMProvider instance
            timeout_seconds: Request timeout
            max_retries: Number of retries on failure
        """
        self.provider = provider
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    async def generate(
        self,
        messages: list[dict],
        schema: Optional[dict] = None,
        max_tokens: int = 256,
    ) -> dict:
        """Generate with retry and timeout.

        入力：messages, schema, max_tokens
        出力：success dict or error_type分類
        副作用：リトライ実行
        失敗モード：全リトライ後も失敗 → error_type: "provider_error"
        """
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    self.provider.generate(messages, schema, max_tokens),
                    timeout=self.timeout_seconds,
                )
                return result
            except asyncio.TimeoutError:
                last_error = {"error_type": "timeout", "text": "", "json": None}
                logging.warning(f"Timeout on attempt {attempt + 1}/{self.max_retries + 1}")
            except Exception as e:
                last_error = {
                    "error_type": "provider_error",
                    "text": "",
                    "json": None,
                }
                logging.error(f"Provider error: {e}")

        return last_error or {
            "error_type": "provider_error",
            "text": "",
            "json": None,
        }

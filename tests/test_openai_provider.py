"""Tests for OpenAI Provider.

Tests cover:
- Mock-based testing (no actual API calls)
- Error handling
- JSON mode functionality
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from llmops.llm_client import OpenAIProvider


class TestOpenAIProviderInit:
    """Test OpenAI provider initialization."""

    def test_init_with_api_key(self):
        """Provider initializes with explicit API key."""
        provider = OpenAIProvider(api_key="test-key-123")
        assert provider.api_key == "test-key-123"
        assert provider.model_name == "gpt-4o-mini"

    def test_init_with_custom_model(self):
        """Provider accepts custom model name."""
        provider = OpenAIProvider(model_name="gpt-4o", api_key="test-key")
        assert provider.model_name == "gpt-4o"

    def test_init_without_api_key_raises(self):
        """Provider raises error when no API key available."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="OpenAI API key required"):
                OpenAIProvider()

    def test_init_uses_env_var(self):
        """Provider uses OPENAI_API_KEY from environment."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "env-key"}):
            provider = OpenAIProvider()
            assert provider.api_key == "env-key"


class TestOpenAIProviderGenerate:
    """Test OpenAI provider generation (mocked)."""

    @pytest.mark.asyncio
    async def test_generate_success(self):
        """Provider returns valid response on success."""
        provider = OpenAIProvider(api_key="test-key")

        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Generated text response"))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=20, total_tokens=30)

        provider.client.chat.completions.create = AsyncMock(return_value=mock_response)

        messages = [{"role": "user", "content": "Hello"}]
        result = await provider.generate(messages, max_tokens=100)

        assert result["text"] == "Generated text response"
        assert result["error_type"] is None
        assert result["tokens"]["total"] == 30

    @pytest.mark.asyncio
    async def test_generate_with_schema_json_mode(self):
        """Provider enables JSON mode when schema provided."""
        provider = OpenAIProvider(api_key="test-key")

        # Mock valid JSON response
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"name": "test", "age": 25}'))
        ]
        mock_response.usage = MagicMock(prompt_tokens=15, completion_tokens=10, total_tokens=25)

        provider.client.chat.completions.create = AsyncMock(return_value=mock_response)

        messages = [{"role": "user", "content": "Generate user"}]
        schema = {"properties": {"name": "string", "age": "number"}}
        result = await provider.generate(messages, schema=schema)

        assert result["json"] == {"name": "test", "age": 25}
        assert result["error_type"] is None

    @pytest.mark.asyncio
    async def test_generate_bad_json_error(self):
        """Provider handles invalid JSON response."""
        provider = OpenAIProvider(api_key="test-key")

        # Mock invalid JSON response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Not valid JSON{"))]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

        provider.client.chat.completions.create = AsyncMock(return_value=mock_response)

        messages = [{"role": "user", "content": "Generate"}]
        schema = {"properties": {"data": "string"}}
        result = await provider.generate(messages, schema=schema)

        assert result["error_type"] == "bad_json"
        assert result["json"] is None

    @pytest.mark.asyncio
    async def test_generate_api_error(self):
        """Provider handles API errors gracefully."""
        provider = OpenAIProvider(api_key="test-key")

        # Mock API exception
        provider.client.chat.completions.create = AsyncMock(
            side_effect=Exception("API connection failed")
        )

        messages = [{"role": "user", "content": "Test"}]
        result = await provider.generate(messages)

        assert result["error_type"] == "provider_error"
        assert result["text"] == ""
        assert result["tokens"]["total"] == 0

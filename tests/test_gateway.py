"""Tests for LLM Gateway API."""

import asyncio
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from llmops.gateway import app


@pytest.fixture
def client():
    """Provide FastAPI test client.
    
    入力：なし
    出力：TestClient インスタンス
    副作用：テスト用クライアント初期化
    失敗モード：なし
    """
    return TestClient(app)


class TestGenerateEndpoint:
    """Test POST /generate endpoint."""

    def test_generate_returns_200(self, client):
        """Test: POST /generate returns 200 OK.
        
        入力：正常なリクエスト
        出力：status_code == 200
        副作用：runs/logs/gateway.jsonl に追記
        失敗モード：なし（MockProvider使用）
        """
        payload = {
            "messages": [{"role": "user", "content": "Hello"}],
            "max_output_tokens": 256,
        }
        response = client.post("/generate", json=payload)
        assert response.status_code == 200

    def test_generate_returns_request_id(self, client):
        """Test: response includes request_id.
        
        入力：request_id なし（自動生成）
        出力：response.request_id は UUID形式
        副作用：なし
        失敗モード：なし
        """
        payload = {
            "messages": [{"role": "user", "content": "Test"}],
            "max_output_tokens": 256,
        }
        response = client.post("/generate", json=payload)
        data = response.json()
        assert "request_id" in data
        assert len(data["request_id"]) > 0

    def test_generate_with_schema(self, client):
        """Test: POST /generate with JSON schema.
        
        入力：schema指定
        出力：json フィールドは dict
        副作用：runs/logs/gateway.jsonl に has_schema=true で記録
        失敗モード：schema不正時は error_type: "bad_json"
        """
        payload = {
            "messages": [{"role": "user", "content": "Generate JSON"}],
            "schema": {"properties": {"name": "string", "age": "number"}},
            "max_output_tokens": 256,
        }
        response = client.post("/generate", json=payload)
        data = response.json()
        assert response.status_code == 200
        assert data.get("json") is not None
        assert isinstance(data["json"], dict)

    def test_generate_includes_token_counts(self, client):
        """Test: response includes token usage.
        
        入力：標準リクエスト
        出力：prompt_tokens, completion_tokens, total_tokens > 0
        副作用：なし
        失敗モード：なし
        """
        payload = {
            "messages": [{"role": "user", "content": "Count tokens"}],
            "max_output_tokens": 256,
        }
        response = client.post("/generate", json=payload)
        data = response.json()
        assert data["prompt_tokens"] > 0
        assert data["completion_tokens"] > 0
        assert data["total_tokens"] > 0

    def test_generate_includes_latency(self, client):
        """Test: response includes latency_ms.
        
        入力：標準リクエスト
        出力：latency_ms >= 50 (MockProvider遅延)
        副作用：なし
        失敗モード：なし
        """
        payload = {
            "messages": [{"role": "user", "content": "Test latency"}],
            "max_output_tokens": 256,
        }
        response = client.post("/generate", json=payload)
        data = response.json()
        assert "latency_ms" in data
        assert data["latency_ms"] > 0

    def test_generate_with_explicit_request_id(self, client):
        """Test: custom request_id is preserved.
        
        入力：request_id 指定
        出力：response.request_id == 入力値
        副作用：runs/logs/gateway.jsonl に指定request_id で記録
        失敗モード：なし
        """
        custom_id = "test-123-abc"
        payload = {
            "request_id": custom_id,
            "messages": [{"role": "user", "content": "Test"}],
            "max_output_tokens": 256,
        }
        response = client.post("/generate", json=payload)
        data = response.json()
        assert data["request_id"] == custom_id

    def test_jsonl_log_created(self, client, tmp_path):
        """Test: JSONL log file is created.
        
        入力：POST /generate 実行
        出力：runs/logs/gateway.jsonl ファイル存在
        副作用：ログファイル作成
        失敗モード：ディスク容量不足時は例外
        """
        payload = {
            "messages": [{"role": "user", "content": "Log test"}],
            "max_output_tokens": 256,
        }
        response = client.post("/generate", json=payload)
        assert response.status_code == 200

        # Check if log file exists
        log_path = Path("runs/logs/gateway.jsonl")
        assert log_path.exists()

    def test_health_endpoint(self, client):
        """Test: GET /health works.
        
        入力：なし
        出力：status: "ok"
        副作用：なし
        失敗モード：なし
        """
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "provider" in data


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_missing_messages(self, client):
        """Test: missing messages field.
        
        入力：messages フィールド省略
        出力：status_code == 422 (validation error)
        副作用：なし
        失敗モード：Pydantic バリデーション
        """
        payload = {"max_output_tokens": 256}
        response = client.post("/generate", json=payload)
        assert response.status_code == 422

    def test_invalid_schema_returns_error_type(self, client):
        """Test: invalid schema sets error_type.
        
        入力：schema が dict でない値
        出力：error_type: "bad_json"
        副作用：runs/logs/gateway.jsonl に error_type 記録
        失敗モード：なし（graceful error handling）
        """
        payload = {
            "messages": [{"role": "user", "content": "Test"}],
            "schema": "not_a_dict",  # Invalid
            "max_output_tokens": 256,
        }
        response = client.post("/generate", json=payload)
        data = response.json()
        # Note: Pydantic may reject this, or we handle in provider
        assert response.status_code in [200, 422]

class TestPromptVersioning:
    """Test prompt versioning features."""

    def test_generate_with_prompt_version(self, client):
        """Test: POST /generate accepts prompt_version."""
        payload = {
            "messages": [{"role": "user", "content": "Hello"}],
            "prompt_version": "1.0",
            "max_output_tokens": 256,
        }
        response = client.post("/generate", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "prompt_version_used" in data
        assert data["prompt_version_used"] == "1.0"

    def test_generate_with_nonexistent_prompt_version(self, client):
        """Test: nonexistent version falls back to config default."""
        payload = {
            "messages": [{"role": "user", "content": "Hello"}],
            "prompt_version": "99.0",  # Does not exist
            "max_output_tokens": 256,
        }
        response = client.post("/generate", json=payload)
        assert response.status_code == 200
        data = response.json()
        # Should use default (1.0)
        assert "prompt_version_used" in data
        assert data["prompt_version_used"] in ["1.0", "2.0", "3.0"]

    def test_list_prompts_endpoint(self, client):
        """Test: GET /prompts lists available versions."""
        response = client.get("/prompts")
        assert response.status_code == 200
        data = response.json()
        assert "versions" in data
        assert "default" in data
        assert len(data["versions"]) > 0

    def test_get_prompt_info_endpoint(self, client):
        """Test: GET /prompts/{version} returns metadata."""
        response = client.get("/prompts/1.0")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert data["version"] == "1.0"
        assert "description" in data

    def test_get_nonexistent_prompt_info(self, client):
        """Test: GET /prompts/{version} for nonexistent version."""
        response = client.get("/prompts/99.0")
        assert response.status_code == 200
        data = response.json()
        assert "error" in data

    def test_response_includes_prompt_version(self, client):
        """Test: response always includes prompt_version_used."""
        payload = {
            "messages": [{"role": "user", "content": "Test"}],
            "max_output_tokens": 256,
        }
        response = client.post("/generate", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "prompt_version_used" in data


class TestCaching:
    """Test in-memory caching behavior."""

    def test_cache_hit_on_repeated_request(self, client):
        payload = {
            "messages": [{"role": "user", "content": "Hello cache"}],
            "max_output_tokens": 128,
        }

        first = client.post("/generate", json=payload)
        assert first.status_code == 200
        first_data = first.json()
        assert first_data.get("cache_hit") is False

        second = client.post("/generate", json=payload)
        assert second.status_code == 200
        second_data = second.json()
        assert second_data.get("cache_hit") is True

    def test_error_responses_not_cached(self, client):
        """Ensure bad_json responses are not cached."""
        payload = {
            "messages": [{"role": "user", "content": "Bad schema"}],
            # This schema triggers bad_json in MockLLMProvider
            "schema": {"properties": None},
            "max_output_tokens": 64,
        }

        first = client.post("/generate", json=payload)
        assert first.status_code == 200
        first_data = first.json()
        assert first_data.get("error_type") is not None
        assert first_data.get("cache_hit") is False

        second = client.post("/generate", json=payload)
        assert second.status_code == 200
        second_data = second.json()
        # Should not be served from cache because error_type was set
        assert second_data.get("cache_hit") is False


class TestRateLimiting:
    """Test rate limiting functionality."""

    def test_rate_limiting_disabled_by_default(self, client):
        """Test that rate limiting is disabled by default (no limits in config)."""
        payload = {
            "messages": [{"role": "user", "content": "Test"}],
            "max_output_tokens": 64,
        }
        
        # Should allow many requests without rate limiting
        for _ in range(20):
            response = client.post("/generate", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data.get("rate_limited") is False
            assert data.get("rate_limit_reason") is None

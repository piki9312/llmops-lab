"""LLM Gateway API - Central hub for LLM operations with observability.

Design:
- Aggregates LLM provider calls via LLMClient
- Enforces request/response schemas with JSON support
- Logs all operations to JSONL for observability
- Handles retries, timeouts, and error classification
"""

import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml
from fastapi import FastAPI
from pydantic import BaseModel, Field, ConfigDict

from .llm_client import LLMClient, MockLLMProvider, OpenAIProvider

# ============================================================================
# DATA MODELS
# ============================================================================


class Message(BaseModel):
    """Single message in conversation."""

    role: str = Field(..., description="'user', 'assistant', 'system'")
    content: str = Field(..., description="Message text")


class GenerateRequest(BaseModel):
    """Request to generate LLM output.

    入力：
        - request_id：トレース用ID（省略時は自動生成）
        - messages：会話ターン
        - schema_：JSON出力スキーマ（任意）
        - max_output_tokens：最大トークン数

    副作用：JSONLログ出力
    失敗モード：request_id 重複時は警告ログのみ
    """

    request_id: Optional[str] = Field(
        default=None, description="Trace ID (auto-generated if omitted)"
    )
    messages: list[Message] = Field(..., description="Conversation turns")
    schema_: Optional[dict] = Field(
        default=None, alias="schema", description="JSON output schema (optional)"
    )
    max_output_tokens: int = Field(default=256, ge=1, le=4096)


class GenerateResponse(BaseModel):
    """Response from LLM generation.

    出力：
        - request_id：リクエスト追跡用ID
        - text：生成テキスト
        - json_：JSON形式出力（schema指定時）
        - provider：使用プロバイダ
        - model：使用モデル
        - latency_ms：処理時間
        - token_usage：{prompt, completion, total}
        - error_type_：null（成功）、"timeout"、"bad_json"、"provider_error"

    副作用：なし（ログ出力はgateway層で処理）
    失敗モード：error_type_ が null でない場合は部分的な結果を返す
    """

    request_id: str
    text: str
    json_: Optional[dict] = Field(None, alias="json")
    provider: str
    model: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    error_type_: Optional[str] = Field(None, alias="error_type")

    # Pydantic v2 config
    model_config = ConfigDict(populate_by_name=True)


# ============================================================================
# LOGGING
# ============================================================================


def _mask_messages(messages: list[dict]) -> list[dict]:
    """Mask sensitive content in messages for logging.

    入力：messages list
    出力：マスク済み messages
    副作用：なし
    失敗モード：なし（常に正常）
    """
    masked = []
    for msg in messages:
        content_hash = hashlib.sha256(msg.get("content", "").encode()).hexdigest()[
            :8
        ]
        masked.append(
            {
                "role": msg.get("role", "unknown"),
                "content_hash": content_hash,
                "content_length": len(msg.get("content", "")),
            }
        )
    return masked


def _write_jsonl_log(log_entry: dict, log_path: Path) -> None:
    """Append JSON log entry to JSONL file.

    入力：log_entry dict, log_path
    出力：ファイル追記
    副作用：ディスク I/O
    失敗モード：ファイル書き込み失敗時は例外発生
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as f:
        f.write(json.dumps(log_entry) + "\n")


# ============================================================================
# FASTAPI APP
# ============================================================================

# Initialize FastAPI
app = FastAPI(title="LLM Gateway", version="0.1.0")

# Load configuration
config_path = Path(__file__).parent.parent.parent / "configs" / "default.yaml"
if config_path.exists():
    with open(config_path) as f:
        CONFIG = yaml.safe_load(f)
else:
    CONFIG = {
        "provider": "mock",
        "model": "gpt-4-mock",
        "timeout_seconds": 30,
        "max_retries": 2,
        "prompt_version": "v1",
        "log_dir": "runs/logs",
    }

# Initialize provider and client
if CONFIG["provider"] == "openai":
    provider = OpenAIProvider(
        model_name=CONFIG["model"],
        api_key=CONFIG.get("api_key")  # Falls back to OPENAI_API_KEY env var
    )
else:
    # Default to mock provider
    provider = MockLLMProvider(CONFIG["model"])

llm_client = LLMClient(
    provider=provider,
    timeout_seconds=CONFIG["timeout_seconds"],
    max_retries=CONFIG["max_retries"],
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest) -> GenerateResponse:
    """Generate LLM output with observability.

    入力：
        - request_id: trace ID
        - messages: conversation
        - schema: JSON schema (optional)
        - max_output_tokens: token limit

    出力：
        - GenerateResponse（text, json, tokens, error_type）
        - JSONLログ自動出力

    副作用：
        - runs/logs/gateway.jsonl に1行追記
        - ログにリクエスト/レスポンス情報

    失敗モード：
        - error_type != null の場合も 200 で応答
        - request_id 重複時は警告ログ
    """
    # Generate request ID if not provided
    request_id = request.request_id or str(uuid.uuid4())

    # Record start time
    start_time = time.time()

    # Convert request to provider format
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    # Call LLM client
    result = await llm_client.generate(
        messages=messages,
        schema=request.schema_,
        max_tokens=request.max_output_tokens,
    )

    # Calculate latency
    latency_ms = (time.time() - start_time) * 1000

    # Extract token usage
    tokens = result.get("tokens", {"prompt": 0, "completion": 0, "total": 0})

    # Build response
    response = GenerateResponse(
        request_id=request_id,
        text=result.get("text", ""),
        json=result.get("json"),
        provider=CONFIG["provider"],
        model=CONFIG["model"],
        latency_ms=latency_ms,
        prompt_tokens=tokens.get("prompt", 0),
        completion_tokens=tokens.get("completion", 0),
        total_tokens=tokens.get("total", 0),
        error_type=result.get("error_type"),
    )

    # Write JSONL log (mask sensitive content)
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "provider": CONFIG["provider"],
        "model": CONFIG["model"],
        "latency_ms": latency_ms,
        "token_usage": {
            "prompt": tokens.get("prompt", 0),
            "completion": tokens.get("completion", 0),
            "total": tokens.get("total", 0),
        },
        "error_type": result.get("error_type"),
        "prompt_version": CONFIG["prompt_version"],
        "messages_masked": _mask_messages(messages),
        "has_schema": request.schema_ is not None,
        "json_generated": response.json_ is not None,
    }

    log_path = Path(CONFIG["log_dir"]) / "gateway.jsonl"  # runs/logs/gateway.jsonl
    try:
        _write_jsonl_log(log_entry, log_path)
    except Exception as e:
        logger.error(f"Failed to write log: {e}")

    logger.info(f"[{request_id}] Generated (error={response.error_type_})")

    return response


@app.get("/health")
async def health():
    """Health check endpoint.
    
    入力：なし
    出力：{"status": "ok", "provider": "..."}
    副作用：なし
    失敗モード：なし
    """
    return {"status": "ok", "provider": CONFIG["provider"]}

"""
LLMOps Lab - システムアーキテクチャ図

【全体フロー】

┌─────────────────────────────────────────────────────────────────────┐
│                        FastAPI Gateway                               │
│                                                                       │
│  POST /generate                                                       │
│  ├─ GenerateRequest (messages, schema, max_tokens, prompt_version)   │
│  ├─ Request ID生成 (uuid.uuid4())                                    │
│  ├─ 開始時刻記録                                                      │
│  └─ メッセージ変換                                                    │
└──────────────────┬──────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      LLMClient.generate()                             │
│                 (Retry / Timeout / Error Handling)                   │
│                                                                       │
│  for attempt in range(max_retries + 1):  # デフォルト: 3回           │
│    try:                                                               │
│      result = await asyncio.wait_for(                                │
│          provider.generate(...),                                     │
│          timeout=timeout_seconds  # デフォルト: 30秒                 │
│      )                                                                │
│      return result                                                    │
│    except asyncio.TimeoutError:                                      │
│      error_type = "timeout"                                          │
│    except Exception:                                                  │
│      error_type = "provider_error"                                   │
└──────────────────┬──────────────────────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
   ┌─────────────────┐  ┌──────────────────┐
   │ MockProvider    │  │ OpenAIProvider   │
   │ .generate()     │  │ .generate()      │
   └────────┬────────┘  └────────┬─────────┘
            │                    │
            ▼                    ▼
    ┌──────────────────┐  ┌──────────────────┐
    │ schema チェック   │  │ JSON Mode有効化   │
    │ JSON生成 (mock)  │  │ API呼び出し      │
    └────────┬─────────┘  └────────┬─────────┘
             │                     │
             ▼                     ▼
    result = {                result = {
      "text": str,            "text": str,
      "json": dict|None,      "json": dict|None,
      "tokens": {...},        "tokens": {...},
      "error_type": str|None  "error_type": str|None
    }                         }
             │                     │
             └──────────┬──────────┘
                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│           Calculate Metrics & Build Response                         │
│                                                                       │
│  ├─ latency_ms = time.time() - start_time                            │
│  ├─ tokens = result["tokens"]                                        │
│  ├─ cost_usd = calculate_cost_usd(model, prompt_tokens, ...)        │
│  ├─ prompt_version_used (request or config default)                 │
│  ├─ GenerateResponse を構築                                          │
│  └─ JSONL ログ作成                                                   │
└──────────────────┬──────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      JSONL Log Writing                                │
│                                                                       │
│  log_entry = {                                                        │
│    "timestamp": "2026-01-26T...",                                    │
│    "request_id": "uuid",                                             │
│    "provider": "mock|openai",                                        │
│    "model": "gpt-4o|gpt-4-mock",                                     │
│    "latency_ms": 54.5,                                               │
│    "token_usage": {                                                   │
│      "prompt": 50,                                                    │
│      "completion": 80,                                                │
│      "total": 130                                                     │
│    },                                                                 │
│    "cost_usd": 0.0025,                                               │
│    "prompt_version_used": "1.0",                                     │
│    "prompt_version_requested": "1.0",                                │
│    "error_type": None|"timeout"|"bad_json"|"provider_error",         │
│    "messages_masked": [                                              │
│      {"role": "user", "content_hash": "sha256[:8]", "length": 45}   │
│    ],                                                                 │
│    "has_schema": True,                                               │
│    "json_generated": True                                            │
│  }                                                                    │
│                                                                       │
│  _write_jsonl_log(log_entry, "runs/logs/gateway.jsonl")             │
│  └─ 1行の JSON として追記                                            │
└──────────────────┬──────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       HTTP Response                                   │
│                                                                       │
│  GenerateResponse (JSON) {                                           │
│    "request_id": "uuid",                                             │
│    "text": "LLM output",                                             │
│    "json": {...},                  # schema指定時のみ               │
│    "provider": "mock",                                               │
│    "model": "gpt-4-mock",                                            │
│    "latency_ms": 54.5,                                               │
│    "prompt_tokens": 50,                                              │
│    "completion_tokens": 80,                                          │
│    "total_tokens": 130,                                              │
│    "cost_usd": 0.0025,                                               │
│    "prompt_version_used": "1.0",                                     │
│    "error_type": null                                                │
│  }                                                                    │
└─────────────────────────────────────────────────────────────────────┘


【error_type の決定ツリー】

LLMClient.generate()
│
├─ asyncio.wait_for() でタイムアウト
│  └─ error_type: "timeout" ✓
│
├─ provider.generate() で例外
│  └─ error_type: "provider_error" ✓
│
└─ provider.generate() 成功
   │
   ├─ MockProvider.generate()
   │  ├─ schema が指定されている
   │  │  ├─ isinstance(schema, dict) = False
   │  │  │  └─ error_type: "bad_json" ✓
   │  │  └─ isinstance(schema, dict) = True
   │  │     ├─ mock JSON生成成功
   │  │     │  └─ error_type: None ✓
   │  │     └─ mock JSON生成失敗 (Exception)
   │  │        └─ error_type: "bad_json" ✓
   │  └─ schema が None
   │     └─ error_type: None ✓
   │
   └─ OpenAIProvider.generate()
      ├─ schema が指定されている
      │  ├─ JSON Mode有効 + API呼び出し
      │  │  ├─ 返却テキスト = 有効なJSON
      │  │  │  └─ json.loads() 成功 → error_type: None ✓
      │  │  └─ 返却テキスト = 無効なJSON
      │  │     └─ json.loads() 失敗 → error_type: "bad_json" ✓
      │  └─ schema が None
      │     └─ error_type: None ✓
      └─ API呼び出し失敗 (Exception)
         └─ except ブロック → error_type: "provider_error" ✓


【PII対策】

元のメッセージ:
{
  "role": "user",
  "content": "My email is user@example.com and password is secret123"
}

_mask_messages() で変換:
{
  "role": "user",
  "content_hash": "f47ac10b",    # SHA256[:8]
  "content_length": 60            # 元の長さ
}

保存: ✓ content_hash, content_length
破棄: ✗ content の実際のテキスト


【リトライ とタイムアウト】

設定値（configs/default.yaml）:
  timeout_seconds: 30
  max_retries: 2

実行:
  Attempt 1
    ├─ 開始
    ├─ asyncio.wait_for(timeout=30秒)
    ├─ provider.generate() 実行
    └─ 成功/失敗判定
        ├─ 成功 → 終了、返却
        ├─ TimeoutError (30秒以上) → Attempt 2へ
        └─ Exception → Attempt 2へ
  
  Attempt 2 (同じ処理)
    └─ 失敗 → Attempt 3へ
  
  Attempt 3 (最後)
    └─ 失敗 → last_error を返却

最大実行時間: timeout_seconds × (max_retries + 1) = 30秒 × 3 = 90秒

※ただし、各リトライは独立した30秒タイムアウト


【config ファイルの役割】

configs/default.yaml:
  provider: "mock"              # MockProvider or OpenAIProvider
  model: "gpt-4-mock"           # モデル識別子
  timeout_seconds: 30           # タイムアウト秒数
  max_retries: 2                # リトライ回数
  prompt_version: "1.0"         # デフォルトプロンプトバージョン
  log_dir: "runs/logs"          # ログディレクトリ

読み込み: gateway.py 初期化時 (160-177行)
使用: 各エンドポイントで CONFIG["key"] でアクセス


【ファイルの責務分離】

llm_client.py:
  - 責務: Provider インターフェース、リトライ/タイムアウト
  - 返す: error_type (timeout, provider_error, bad_json)

gateway.py:
  - 責務: HTTP API、リクエスト処理、ログ出力
  - 返す: GenerateResponse（エラーを含む）
  - 呼ぶ: llm_client.generate()
  - 記録: JSONL ログ

pricing.py:
  - 責務: コスト計算
  - 返す: cost_usd (float)

prompt_manager.py:
  - 責務: プロンプトテンプレート管理
  - 返す: PromptTemplate

dashboard.py:
  - 責務: ログ可視化
  - 読む: runs/logs/gateway.jsonl
  - 表示: メトリクス、チャート
"""

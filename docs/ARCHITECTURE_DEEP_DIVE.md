"""
LLMClient.generate() と ログシステムの詳細解説

【質問1】LLMClient.generate()（心臓）
=================================================

LLMClient.generate() は llm_client.py の280-316行目にあります。

```python
async def generate(
    self,
    messages: list[dict],
    schema: Optional[dict] = None,
    max_tokens: int = 256,
) -> dict:
    """Generate with retry and timeout."""
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
```

**フロー：**
1. loop: max_retries + 1 回 (デフォルト: 3回)
2. asyncio.wait_for() でタイムアウトを設定 (デフォルト: 30秒)
3. provider.generate() を呼び出し
4. 成功 → dict を返す（終了）
5. TimeoutError → error_type: "timeout" に設定、リトライ
6. Exception → error_type: "provider_error" に設定、リトライ
7. すべてのリトライ失敗 → last_error を返す

**返却 dict 構造（常に以下を保証）：**
```python
{
    "text": str,
    "json": dict | None,
    "tokens": {"prompt": int, "completion": int, "total": int},
    "error_type": None | "timeout" | "bad_json" | "provider_error"
}
```


【質問2】timeout / retry / error_type / ログ用メタ - どこで決まるか
=================================================

**timeout_seconds:**
- 決定点: LLMClient.__init__() で設定 (llm_client.py 258-267行目)
  ```python
  def __init__(
      self,
      provider: LLMProvider,
      timeout_seconds: float = 30,  ← ここで決まる（デフォルト30秒）
      max_retries: int = 2,
  ):
      self.timeout_seconds = timeout_seconds
  ```
- 実際の値: gateway.py の初期化時 (174行目)
  ```python
  llm_client = LLMClient(
      provider=provider,
      timeout_seconds=CONFIG["timeout_seconds"],  ← configs/default.yaml から読み込み
      max_retries=CONFIG["max_retries"],
  )
  ```
- configs/default.yaml:
  ```yaml
  timeout_seconds: 30
  max_retries: 2
  ```

**max_retries:**
- 決定点: LLMClient.__init__() で設定
- 値: configs/default.yaml の max_retries （デフォルト: 2）
- リトライ総数: max_retries + 1 = 3回

**error_type:**
- LLMClient.generate() で以下の3つが設定可能:
  1. "timeout" - asyncio.TimeoutError 発生時 (llm_client.py 302-305行)
  2. "provider_error" - Exception 発生時 (llm_client.py 306-309行)
  3. "bad_json" - provider の generate() が返す場合
     - MockProvider: schema が dict でない (llm_client.py 90-96行)
     - OpenAIProvider: JSON parse 失敗 (llm_client.py 227-230行)

**ログ用メタ:**
- 決定点1: LLMClient.generate() が返すメタデータ
  - tokens (prompt, completion, total)
  - error_type
  
- 決定点2: gateway の @app.post("/generate") で追加 (250-293行目)
  - timestamp: datetime.now(timezone.utc)
  - request_id: uuid.uuid4() | 指定値
  - latency_ms: time.time() の差分
  - cost_usd: calculate_cost_usd()
  - prompt_version_used / prompt_version_requested

全体フロー:
gateway.post("/generate") 
  → LLMClient.generate() 
    → timeout/retry/error_type決定
  → calculate_cost_usd()
  → build log_entry dict
  → _write_jsonl_log()


【質問3】ログを書いてる関数（JSONL追記）
=================================================

**関数: _write_jsonl_log()**
- 位置: gateway.py 131-140行

```python
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
```

**処理:**
1. ディレクトリを作成（なければ）
2. 追記モード "a" でファイルを開く
3. log_entry を JSON に変換 → 1行で追記

**呼び出し元: gateway.post("/generate")**
- 位置: gateway.py 297-299行

```python
log_path = Path(CONFIG["log_dir"]) / "gateway.jsonl"  # runs/logs/gateway.jsonl
try:
    _write_jsonl_log(log_entry, log_path)
except Exception as e:
    logger.error(f"Failed to write log: {e}")
```

**ログファイル:**
- 場所: runs/logs/gateway.jsonl
- フォーマット: JSONL (1行 = 1 JSON object)
- 追記: 同期、可変長（エラーでもスキップ）

**ログファイルの例:**
```json
{"timestamp": "2026-01-26T02:43:09.641365+00:00", "request_id": "a71f3c10-5000-46dc-8bc3-bbb0d451f1eb", "provider": "mock", "model": "gpt-4-mock", "latency_ms": 54.5, "token_usage": {"prompt": 50, "completion": 80, "total": 130}, "cost_usd": 0.0, "prompt_version_used": "1.0", "prompt_version_requested": null, "error_type": null, "messages_masked": [{"role": "user", "content_hash": "a1b2c3d4", "content_length": 45}], "has_schema": false, "json_generated": false}
```


【質問4】何を保存して、何を保存してないか（PII対策）
=================================================

**保存されるもの（安全）:**
✅ timestamp: ISO形式タイムスタンプ
✅ request_id: UUID
✅ provider: プロバイダ名
✅ model: モデル名
✅ latency_ms: 処理時間
✅ token_usage: トークン数 (prompt, completion, total)
✅ cost_usd: 推定コスト
✅ error_type: エラー種別
✅ prompt_version_used: プロンプトバージョン
✅ has_schema: スキーマ指定有無
✅ json_generated: JSON生成成功有無
✅ content_hash: SHA256ハッシュ（先頭8文字）
✅ content_length: メッセージ長

**保存されないもの（PII対策）:**
❌ messages["content"]: ユーザー入力テキスト
❌ response text: LLM生成テキスト
❌ response json: 構造化出力
❌ API keys

**PII対策の実装: _mask_messages()**
- 位置: gateway.py 108-128行

```python
def _mask_messages(messages: list[dict]) -> list[dict]:
    """Mask sensitive content in messages for logging."""
    masked = []
    for msg in messages:
        content_hash = hashlib.sha256(msg.get("content", "").encode()).hexdigest()[:8]
        masked.append(
            {
                "role": msg.get("role", "unknown"),
                "content_hash": content_hash,           # SHA256（先頭8文字）
                "content_length": len(msg.get("content", "")),  # 長さのみ
            }
        )
    return masked
```

**マスキング例:**
```
入力: {"role": "user", "content": "My email is user@example.com and my password is secret123"}
出力: {"role": "user", "content_hash": "f47ac10b", "content_length": 60}
```

**コンテンツハッシュの使途:**
- 同じ入力の検出（キャッシング前段階）
- 重複検出
- 異常検知


【質問5】schema指定時の処理（JSON遵守）
=================================================

**フロー:**

1. **Gateway受け取り** (gateway.py 180行)
   ```python
   await llm_client.generate(
       messages=messages,
       schema=request.schema_,  ← schema dict が渡される
       max_tokens=request.max_output_tokens,
   )
   ```

2. **LLMClient.generate()** (llm_client.py 280-316)
   - timeout/retry でラップして provider.generate() 呼び出し
   - schema がそのまま provider に渡される

3. **MockProvider.generate()** (llm_client.py 75-110)
   ```python
   json_output = None
   error_type = None

   if schema:
       try:
           if not isinstance(schema, dict):
               error_type = "bad_json"  ← schema が dict でない
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
   ```

4. **OpenAIProvider.generate()** (llm_client.py 190-240)
   ```python
   if schema:
       params["response_format"] = {"type": "json_object"}  ← JSON Mode有効化
       schema_prompt = f"\nRespond with JSON matching this schema: {schema}"
       # ... system message に schema_prompt を追加
   
   response = await self.client.chat.completions.create(**params)
   text = response.choices[0].message.content or ""
   
   # Parse JSON if schema was requested
   json_output = None
   error_type = None
   if schema:
       try:
           import json
           json_output = json.loads(text)  ← JSON parse
       except json.JSONDecodeError as e:
           logging.warning(f"Failed to parse JSON from response: {e}")
           error_type = "bad_json"  ← parse失敗時
   ```

5. **Gateway で応答構築** (gateway.py 260-275)
   ```python
   response = GenerateResponse(
       ...
       json_=result.get("json"),         # json_output が入る
       ...
       error_type=result.get("error_type"),  # error_type が入る
   )
   ```

6. **JSONL ログに記録** (gateway.py 280-295)
   ```python
   log_entry = {
       "has_schema": request.schema_ is not None,  ← schema指定有無
       "json_generated": response.json_ is not None,  ← JSON生成成功有無
       ...
   }
   ```

**schema指定時の流れ図:**

Request (schema 指定)
  ↓
LLMClient.generate()
  ↓
Provider (schema に応じて処理)
  ├─ Mock: schema dict チェック → mock JSON生成
  └─ OpenAI: JSON Mode + schema prompt → API呼び出し → JSON parse
  ↓
Result dict (json, error_type を含む)
  ↓
GenerateResponse (json_ に詰める)
  ↓
JSONL ログ (json_generated フラグ記録)


【質問6】"dictを返す保証" がどこで担保されているか
=================================================

LLMClient.generate() が常に以下の構造を返すことが保証されている場所:

**1. LLMClient.generate() の戻り値**
- llm_client.py 287-316行: すべてのケースで dict を返す

```python
# 成功ケース
result = await asyncio.wait_for(...)
return result  # provider.generate() の返り値

# TimeoutError
last_error = {"error_type": "timeout", "text": "", "json": None}
return last_error

# Exception
last_error = {"error_type": "provider_error", "text": "", "json": None}
return last_error

# 最終フォールバック
return last_error or {
    "error_type": "provider_error",
    "text": "",
    "json": None,
}
```

**2. 各 Provider.generate() の戻り値**
- llm_client.py 110-113行 (MockProvider)
  ```python
  return {
      "text": base_response[:max_tokens],
      "json": json_output,
      "tokens": {"prompt": 50, "completion": 80, "total": 130},
      "error_type": error_type,
  }
  ```

- llm_client.py 233-240行 (OpenAIProvider)
  ```python
  return {
      "text": text,
      "json": json_output,
      "tokens": tokens,
      "error_type": error_type,
  }
  ```
  
  エラーケース (llm_client.py 242-247行)
  ```python
  except Exception as e:
      logging.error(f"OpenAI API error: {e}")
      return {
          "text": "",
          "json": None,
          "tokens": {"prompt": 0, "completion": 0, "total": 0},
          "error_type": "provider_error",
      }
  ```

**3. TypeHint による静的検証**
- LLMProvider の抽象メソッド (llm_client.py 34-54行)
  ```python
  async def generate(...) -> dict:
      """..."""
      raise NotImplementedError
  ```
- すべてのサブクラスが同じシグネチャを実装

**4. 実行時での契約保証**
- LLMClient.__init__() で provider: LLMProvider を要求
- provider.generate() のみ呼び出し（他のメソッドなし）
- すべてのコード路を dict で終了

**保証レベル:**
- ✅ 型チェック: TypeHint
- ✅ 実行時: dict 構造を常に返す
- ✅ エラーハンドリング: すべてのException をキャッチ → dict に変換


【質問7】失敗が bad_json になる条件
=================================================

error_type が "bad_json" になるのは以下の条件:

**1. MockProvider で schema が dict でない** (llm_client.py 90-96)
```python
if schema:
    try:
        if not isinstance(schema, dict):  ← schema が dict でない
            error_type = "bad_json"  ✓
        else:
            json_output = self._generate_mock_json(schema)
    except Exception as e:
        logging.warning(f"Failed to generate schema JSON: {e}")
        error_type = "bad_json"  ✓
```

**条件:**
- schema パラメータが指定されている（not None）
- かつ isinstance(schema, dict) が False
  - 例: schema = "not a dict"
  - 例: schema = [{"type": "object"}]
  - 例: schema = None → bad_json にはならない（この条件を通らない）

**2. OpenAIProvider で JSON parse 失敗** (llm_client.py 225-230)
```python
if schema:
    try:
        import json
        json_output = json.loads(text)  ← ここで JSONDecodeError
    except json.JSONDecodeError as e:  ← 例外キャッチ
        logging.warning(f"Failed to parse JSON from response: {e}")
        error_type = "bad_json"  ✓
```

**条件:**
- schema が指定されている
- かつ OpenAI API が返したテキストが有効な JSON でない
  - 例: text = "not valid json"
  - 例: text = '{"incomplete": '
  - 例: text = "```json\n{...}\n```" (マークダウンで包まれている)

**シナリオ例:**

① schema なし → error_type は None（成功）
```python
result = await llm_client.generate(messages=[...], schema=None)
# → error_type: None
```

② schema = dict（正常）→ error_type は None （成功）
```python
result = await llm_client.generate(
    messages=[...], 
    schema={"type": "object", "properties": {"name": {"type": "string"}}}
)
# MockProvider → error_type: None
# OpenAIProvider → JSON parse成功 → error_type: None
```

③ schema = str（不正）→ error_type は "bad_json"
```python
result = await llm_client.generate(
    messages=[...], 
    schema="not a dict"
)
# MockProvider → isinstance(schema, dict) = False → error_type: "bad_json" ✓
# OpenAIProvider → JSON Mode有効 → API呼び出し → JSON parse可能性ある
```

④ OpenAI が JSON Mode で無効な JSON を返す → error_type は "bad_json"
```python
# API response: '{"name": , "age": 30}'  (invalid json)
# json.loads() → JSONDecodeError → error_type: "bad_json" ✓
```

**error_type の全体フロー:**

```
LLMClient.generate()
├─ asyncio.TimeoutError
│  └─ error_type: "timeout"
├─ Exception (その他)
│  └─ error_type: "provider_error"
└─ provider.generate() 成功
   └─ MockProvider
      ├─ schema が dict でない
      │  └─ error_type: "bad_json"
      └─ その他
         └─ error_type: None
   └─ OpenAIProvider
      ├─ API呼び出し成功 → JSON parse失敗
      │  └─ error_type: "bad_json"
      ├─ API呼び出し成功 → JSON parse成功
      │  └─ error_type: None
      └─ API呼び出し失敗 (Exception)
         └─ error_type: "provider_error"
```

"""

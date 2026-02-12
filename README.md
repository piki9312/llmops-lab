# 🚀 LLMOps Lab

**回帰テスト×運用に特化した Dev 向け CI プロダクト（LLM/Agent 品質劣化の自動検知）**

[![Tests](https://img.shields.io/badge/tests-255%20passed-success)](tests/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-ready-blue)](Dockerfile)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

LLMOps Lab は、LLM/Agent の変更（prompt / tool / model / provider / code）による **品質劣化を CI 上で自動検知**し、どこが悪化したかを要約するプロダクトです。

中心は **AgentReg**（Agent Regression Gate）— CSV ケース管理・JSONL 永続化・ベースライン比較・CI ゲート判定・失敗原因分析・Flakiness 検知を備えた CI ネイティブな回帰テストフレームワークです。LLM Gateway（FastAPI）や可観測性（Streamlit）は補助コンポーネントとして同梱しています。

---

## ✨ 主要機能

### 🛡️ AgentReg — CI 回帰ゲート
- **回帰テスト実行** — CSV でケース管理、毎回同一入力で検証（`run-daily`）
- **JSONL 永続化** — 1 ケース = 1 行（`runs/agentreg/YYYYMMDD.jsonl`）
- **ベースライン比較** — main artifact or trailing-window; S1/S2 成功率デルタ
- **CI ゲート判定** — `agentops check` → 閾値違反で exit 1 → PR ブロック
- **YAML しきい値設定** — `.agentreg.yml` でデフォルト / PR ラベル・パスルール切替
- **ケース属性** — CSV に `owner`, `tags`, `min_pass_rate` カラム（per-case ゲート）
- **失敗差分の説明** — 新規回帰 / 失敗タイプ変化 / JSON schema 不一致 / レイテンシ急増 / トークン増加を自動検出
- **Flakiness 検知** — `--repeat N` で安定性を評価、🎲 フラグで PR コメントに表示
- **PR コメント** — ゲート結果を Markdown で PR に自動投稿
- **Markdown レポート** — 週次レポート生成（artifact / PR コメント化）

### 🎯 コア機能
- **FastAPI Gateway** - RESTful API で LLM プロバイダーを統一
- **マルチプロバイダー対応** - Mock（開発用）、OpenAI（本番用）
- **JSON Mode** - 構造化出力の自動生成
- **Retry & Timeout** - 非同期処理、エラー分類

### 📊 可観測性
- **リアルタイムダッシュボード** - Streamlit で 7 つのメトリクス、6 つのチャート
- **JSONL ロギング** - PII マスキング、UTC タイムスタンプ
- **コスト追跡** - OpenAI モデルの推定コスト計算
- **プロンプトバージョニング** - セマンティックバージョン管理

### ⚡ パフォーマンス最適化
- **In-Memory キャッシュ** - TTL ベース、Token Bucket 方式
- **レート制限** - QPS（クエリ/秒）+ TPM（トークン/分）制限
- **キャッシュメトリクス** - ヒット率追跡、エラー応答の非キャッシュ化

### 🛡️ 本番環境対応
- **環境変数設定** - 11 個の環境変数で柔軟な設定
- **Docker 化** - docker-compose で API + Dashboard を 1 コマンド起動
- **ヘルスチェック** - 自動的なコンテナ監視
- **CI/CD** - GitHub Actions（6 つのワークフロー、Python 3.10/3.11/3.12 対応）

---

## 🚀 クイックスタート

### ローカル開発

```bash
# 1. セットアップ
pip install -e ".[dev]"

# 2. 回帰テスト実行（3 回反復で Flakiness 検知）
python -m agentops run-daily cases/agent_regression.csv --log-dir runs/agentreg --repeat 3 -v

# 3. CI ゲート判定（ベースライン比較 + 閾値チェック）
python -m agentops check --log-dir runs/agentreg --baseline-days 7 \
  --config .agentreg.yml --cases-file cases/agent_regression.csv

# 4. 週次レポート生成
python -m agentops report --log-dir runs/agentreg --days 7 --baseline-days 7 \
  -o reports/weekly_regression_report.md -v

# 5. API 起動（Gateway: 任意）
python -m uvicorn src.llmops.gateway:app --host 127.0.0.1 --port 8000

# 6. ダッシュボード起動（別ターミナル / 任意）
streamlit run src/llmops/dashboard.py

# 7. テスト実行
make test
```

**アクセス:**
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Dashboard: http://localhost:8501

### Docker デプロイ

```bash
# クイックスタート
docker-compose up -d --build

# または
make docker-build
make docker-up
```

**アクセス:**
- API: http://localhost:8000
- Dashboard: http://localhost:8501

---

## 📖 API 使用例

### 基本的なテキスト生成

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Hello, how are you?"}
    ],
    "max_output_tokens": 256
  }'
```

### JSON 構造化出力

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Extract: Apple announced iPhone 15"}
    ],
    "schema": {
      "type": "object",
      "properties": {
        "company": {"type": "string"},
        "product": {"type": "string"}
      }
    }
  }'
```

### プロンプトバージョン指定

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Explain quantum computing"}],
    "prompt_version": "2.0"
  }'
```

---

## 🔧 設定

### 環境変数

`.env` ファイルで設定をカスタマイズ：

```bash
# Provider 設定
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...

# レート制限
RATE_LIMIT_QPS=100          # クエリ/秒
RATE_LIMIT_TPM=500000       # トークン/分

# キャッシュ
CACHE_ENABLED=true
CACHE_TTL_SECONDS=600
CACHE_MAX_ENTRIES=256

# その他
PROMPT_VERSION=1.0
LOG_DIR=runs/logs
```

サポートされる全環境変数は [docs/README_DEV.md](docs/README_DEV.md) を参照。

---

## 📊 ダッシュボード

Streamlit ダッシュボードでリアルタイム監視：

- **メトリクス**: 総リクエスト数、成功率、平均レイテンシ、トークン数、コスト、キャッシュヒット率
- **チャート**: レイテンシ推移、トークン使用量、コスト分析、キャッシュパフォーマンス、プロンプトバージョン分布、エラー内訳、レート制限状況
- **テーブル**: 最近 20 件のリクエスト詳細

---

## 🏗️ プロジェクト構成

```
llmops-lab/
├── src/agentops/            # AgentReg コア
│   ├── cli.py               # CLI エントリポイント (run-daily / check / report)
│   ├── runner.py            # テストケース実行エンジン
│   ├── check.py             # CI ゲート判定 (run_check / render)
│   ├── config.py            # YAML 設定ローダー (.agentreg.yml)
│   ├── load_cases.py        # CSV ケースローダー (owner/tags/min_pass_rate)
│   ├── diff_explain.py      # 失敗差分の説明エンジン
│   ├── flakiness.py         # Flakiness / 安定性検知
│   ├── models.py            # Pydantic v2 モデル (TestCase / TestResult / AgentRunRecord)
│   ├── aggregate.py         # 集計ロジック
│   ├── analyze.py           # 回帰分析
│   ├── render_md.py         # Markdown レポート生成
│   └── report_weekly.py     # 週次レポートオーケストレータ
├── src/llmops/              # LLM Gateway
│   ├── gateway.py           # FastAPI アプリケーション
│   ├── llm_client.py        # LLM プロバイダー抽象化
│   ├── cache.py             # In-Memory キャッシュ
│   ├── rate_limiter.py      # レート制限（Token Bucket）
│   └── dashboard.py         # Streamlit ダッシュボード
├── cases/                   # テストケース CSV (30 cases: 15 S1 + 15 S2)
├── .agentreg.yml            # AgentReg しきい値設定
├── .github/workflows/       # CI ワークフロー (7 files)
│   └── regression.yml       # AgentReg CI パイプライン
├── tests/                   # テストスイート（255 テスト）
├── docs/                    # ドキュメント
├── Dockerfile               # API 用（マルチステージビルド）
├── docker-compose.yml       # オーケストレーション
└── pyproject.toml           # プロジェクト定義
```

---

## 🧪 テスト

```bash
# 全テスト実行
make test

# 特定のテストスイート
pytest tests/test_gateway.py -v
pytest tests/test_rate_limiter.py -v
pytest tests/test_config.py -v

# カバレッジ
pytest --cov=src/llmops tests/
```

**テスト**: 255 テスト、100% 合格

---

## 📚 ドキュメント

- **[開発者ガイド](docs/README_DEV.md)** - セットアップ、開発フロー、Docker デプロイ
- **[CI の使い方（AgentReg）](docs/CI.md)** - PR/日次実行、artifacts の見方、S1ゲート
- **[AgentReg（CIプロダクト方針）](docs/AGENTREG_CI_PRODUCT.md)** - 回帰テスト×運用の設計方針
- **[エージェントルール](docs/AGENT_RULES.md)** - 自動化エージェント実行ルール
- **[API ドキュメント](http://localhost:8000/docs)** - OpenAPI（Swagger UI）

---

## 🔄 CI/CD

GitHub Actions で自動テスト・評価・デプロイ：

**ワークフロー:**
- **CI/CD Pipeline** - Lint → Test → Build → Security（毎 push/PR）
- **PR Checks** - 形式検証、変更分析、自動コメント
- **Nightly Tests** - 日次テスト実行（全 Python バージョン）
- **Weekly Regression Report** - 毎週月曜に回帰分析レポート生成
- **Dependency Updates** - 毎週日曜に依存パッケージをチェック
- **Release** - タグプッシュで自動リリース＆PyPI デプロイ

**詳細:** [GitHub Actions ドキュメント](docs/GITHUB_ACTIONS.md)

**ステータス:**
- テスト: Python 3.10, 3.11, 3.12 マトリックス
- キャッシュ: pip キャッシュで高速化
- レポート: codecov への自動アップロード
- Docker: main/dev ブランチで自動ビルド

---

## 🐳 Docker コマンド

```bash
# ビルド
make docker-build

# 起動（バックグラウンド）
make docker-up

# 停止
make docker-down

# ログ表示
make docker-logs

# 再起動
make docker-restart

# 完全クリーンアップ
docker-compose down -v
```

---

## 🎯 実装状況

### ✅ AgentReg CI プロダクト

**P0 — CI プロダクトとして成立**
- [x] `agentops check` コマンド（ベースライン比較 → exit code 判定）
- [x] ベースラインパターン（main artifact + `--baseline-dir` / trailing window）
- [x] PR コメント（`--output-file` → `github-script` で投稿）

**P1 — 運用レベル**
- [x] YAML しきい値設定（`.agentreg.yml`）
- [x] PR ラベル / 変更パスによるルール切替
- [x] ケース属性 CSV 拡張（`owner`, `tags`, `min_pass_rate`）
- [x] Per-case ゲート（`min_pass_rate` 違反で exit 1）

**P2 — 原因分析 & 安定性**
- [x] 失敗差分の説明（新規回帰 / 失敗タイプ変化 / JSON schema 不一致 / レイテンシ急増 / トークン増加）
- [x] Flakiness 検知（`--repeat N` で安定性評価、🎲 フラグ表示）

### ✅ LLM Gateway & 可観測性

- [x] FastAPI Gateway（POST /generate、GET /health、GET /prompts）
- [x] Mock & OpenAI プロバイダー
- [x] Retry / Timeout / エラー分類
- [x] JSONL ロギング（PII マスキング）
- [x] In-Memory キャッシュ（TTL + LRU）、レート制限（QPS + TPM）
- [x] Streamlit ダッシュボード、Docker 化
- [x] 包括的テスト（255 テスト）
- [x] GitHub Actions CI/CD（7 ワークフロー）

### 🔮 今後の拡張

- [ ] 複数プロバイダー（Anthropic Claude、Google Gemini、Ollama）
- [ ] 外部キャッシュ（Redis）/ Prometheus メトリクス
- [ ] Human Feedback ループ / A/B テスト

---

## 🧪 AgentReg — CLI リファレンス

### `run-daily` — 回帰テスト実行

```bash
python -m agentops run-daily cases/agent_regression.csv \
  --log-dir runs/agentreg \
  --run-id "$(date +%Y%m%d)-nightly" \
  --repeat 3 \
  -v
```

| フラグ | 説明 |
|--------|------|
| `--log-dir` | JSONL 保存先ディレクトリ |
| `--run-id` | 実行 ID（デフォルト: 自動生成） |
| `--repeat N` | 同一ケースを N 回反復実行（Flakiness 検知用） |
| `-v` | 詳細ログ出力 |

### `check` — CI ゲート判定

```bash
python -m agentops check \
  --log-dir runs/agentreg \
  --baseline-dir baseline/runs/agentreg \
  --config .agentreg.yml \
  --cases-file cases/agent_regression.csv \
  --labels hotfix \
  --output-file gate-result.md
```

| フラグ | 説明 |
|--------|------|
| `--baseline-dir` | ベースライン JSONL ディレクトリ（main artifact） |
| `--baseline-days N` | trailing window 比較（`--baseline-dir` なし時） |
| `--config PATH` | `.agentreg.yml` パス（しきい値設定） |
| `--cases-file PATH` | CSV パス（per-case `min_pass_rate` チェック用） |
| `--labels L1,L2` | PR ラベル（ルールマッチ用） |
| `--changed-files` | 変更ファイル（パスルールマッチ用） |
| `--output-file PATH` | Markdown 出力ファイル（PR コメント用） |
| `--s1-threshold` | S1 成功率しきい値（CLI 最優先） |
| `--overall-threshold` | 全体成功率しきい値 |

**ゲート出力例:**

```
## 🔴 AgentReg Gate: FAIL
| Metric       | Value  | Threshold | Status |
|-------------|--------|-----------|--------|
| S1 pass rate | 85.0%  | 100%      | ❌     |
| Overall      | 90.0%  | 80%       | ✅     |

### Failure Explanations
| Case  | Sev | Type     | Explanation                          |
|-------|-----|----------|--------------------------------------|
| TC004 | S1  | bad_json | 新規回帰; JSON schema不一致: 欠損キー: b |

### Stability Report (1 flaky 🎲)
| Case  | Runs | Pass Rate | Flaky | Latency CV |
|-------|------|-----------|-------|------------|
| TC007 | 3    | 67%       | 🎲    | 0.32       |
```

### `report` — 週次レポート

```bash
python -m agentops report --log-dir runs/agentreg --days 7 --baseline-days 7 \
  -o reports/weekly_regression_report.md -v
```

### ドキュメント
- [CI プロダクト方針（ロードマップ）](docs/AGENTREG_CI_PRODUCT.md)
- [CI の使い方](docs/CI.md)
- [オンボーディングガイド](docs/agentreg_onboarding_onepager.md)

---

## 🤝 貢献

貢献は大歓迎です！以下のガイドラインに従ってください：

1. Feature ブランチを作成（`feature/your-feature`）
2. テストを追加
3. `make test` と `make lint` を実行
4. PR を作成

詳細は [docs/README_DEV.md](docs/README_DEV.md) を参照。

---

## 📝 ライセンス

MIT License

---

## 👥 作者

LLMOps Lab Team

---

**バージョン**: 0.4.0 | **AgentReg**: P0 / P1 / P2 完了 ✅ | **テスト**: 255 passed 🚀

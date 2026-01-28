# 🚀 LLMOps Lab

**本番環境対応の LLM Gateway と可観測性プラットフォーム**

[![Tests](https://img.shields.io/badge/tests-99%20passed-success)](tests/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-ready-blue)](Dockerfile)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

LLMOps Lab は、大規模言語モデル（LLM）の運用に必要な機能を統合した、本番環境対応のゲートウェイプラットフォームです。FastAPI ベースの API、リアルタイム可視化、レート制限、キャッシング、コスト追跡など、エンタープライズグレードの機能を提供します。

---

## ✨ 主要機能

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
- **CI/CD** - GitHub Actions（Python 3.10/3.11 マトリックス）

---

## 🚀 クイックスタート

### ローカル開発

```bash
# 1. セットアップ
pip install -e ".[dev]"

# 2. API 起動
python -m uvicorn src.llmops.gateway:app --host 127.0.0.1 --port 8000

# 3. ダッシュボード起動（別ターミナル）
streamlit run src/llmops/dashboard.py

# 4. テスト実行
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
├── src/llmops/              # コア実装
│   ├── gateway.py           # FastAPI アプリケーション
│   ├── llm_client.py        # LLM プロバイダー抽象化
│   ├── pricing.py           # コスト計算
│   ├── prompt_manager.py    # プロンプトバージョニング
│   ├── cache.py             # In-Memory キャッシュ
│   ├── rate_limiter.py      # レート制限（Token Bucket）
│   ├── config.py            # 環境変数処理
│   └── dashboard.py         # Streamlit ダッシュボード
├── tests/                   # テストスイート（99 テスト）
├── configs/                 # 設定ファイル
├── prompts/                 # プロンプトテンプレート（v1.0, v2.0, v3.0）
├── evals/                   # 評価スクリプト
├── docs/                    # ドキュメント
├── Dockerfile               # API 用（マルチステージビルド）
├── Dockerfile.dashboard     # Dashboard 用
├── docker-compose.yml       # オーケストレーション
└── pyproject.toml          # プロジェクト定義
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

**テストカバレッジ**: 99 テスト、100% 合格

---

## 📚 ドキュメント

- **[開発者ガイド](docs/README_DEV.md)** - セットアップ、開発フロー、Docker デプロイ
- **[エージェントルール](docs/AGENT_RULES.md)** - 自動化エージェント実行ルール
- **[API ドキュメント](http://localhost:8000/docs)** - OpenAPI（Swagger UI）

---

## 🔄 CI/CD

GitHub Actions で自動テスト・評価：

- **トリガー**: push（main/dev/feature/fix）、PR（main/dev）
- **マトリックス**: Python 3.10, 3.11
- **実行内容**: pytest、評価スクリプト、pylint、ログ確認
- **アーティファクト**: 評価レポート（30 日間保存）

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

### ✅ 完成（Level 3.5）

- [x] FastAPI Gateway（POST /generate、GET /health、GET /prompts）
- [x] Mock & OpenAI プロバイダー
- [x] Retry/Timeout/エラー分類
- [x] JSONL ロギング（PII マスキング）
- [x] コスト計測
- [x] プロンプトバージョニング（3 テンプレート）
- [x] In-Memory キャッシュ（TTL + LRU）
- [x] レート制限（QPS + TPM）
- [x] 環境変数設定（11 個）
- [x] Docker 化（API + Dashboard）
- [x] Streamlit ダッシュボード
- [x] 包括的テスト（99 テスト）
- [x] GitHub Actions CI/CD
- [x] 完全なドキュメント

### 🔮 今後の拡張（Level 4.0）

- [ ] 複数プロバイダー（Anthropic Claude、Google Gemini、Ollama）
- [ ] 外部キャッシュ（Redis）
- [ ] Prometheus/Grafana メトリクス
- [ ] ログローテーション
- [ ] Human Feedback ループ
- [ ] A/B テスト機能

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

**バージョン**: 0.3.5 | **ステータス**: Level 3.5 完成 ✅ | **本番環境対応**: Ready 🚀

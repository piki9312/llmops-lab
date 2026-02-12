# 🚀 LLMOps Lab

**回帰テスト×運用に特化した Dev 向け CI プロダクト（LLM/Agent 品質劣化の自動検知）**

[![Tests](https://img.shields.io/badge/tests-124%20passed-success)](tests/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-ready-blue)](Dockerfile)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

LLMOps Lab は、LLM/Agent の変更（prompt / tool / model / provider / code）による **品質劣化を CI 上で検知**し、どこが悪化したかを自動で要約するための実験・実装リポジトリです。

中心は **Agent Regression（AgentReg）** で、JSONL 永続化・週次/期間比較・Top 回帰ケース抽出までを備えています。LLM Gateway（FastAPI）や可観測性（Streamlit）は補助コンポーネントとして同梱しています。

---

## ✨ 主要機能

### ✅ Agent Regression（CI 向け）
- **回帰テスト実行** - CSV でケース管理、毎回同一入力で検証
- **JSONL 永続化** - 1ケース=1行で保存（`runs/agentreg/YYYYMMDD.jsonl`）
- **期間比較（ベースライン）** - 成功率デルタ、失敗タイプ増減、Top 回帰ケース
- **Markdown レポート** - 週次レポート生成（CI で artifact / PR コメント化しやすい）

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

# 2. 回帰テスト（AgentReg）
python -m agentops run-daily cases/agent_regression.csv --log-dir runs/agentreg -v

# 3. ベースライン比較レポート（直近7日 vs その前7日）
python -m agentops report --log-dir runs/agentreg --days 7 --baseline-days 7 -o reports/weekly_regression_report.md -v

# 4. API 起動（Gateway: 任意）
python -m uvicorn src.llmops.gateway:app --host 127.0.0.1 --port 8000

# 5. ダッシュボード起動（別ターミナル / 任意）
streamlit run src/llmops/dashboard.py

# 6. テスト実行
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

**テスト**: 124 テスト、100% 合格

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
- [ ] Agent Regression の評価メトリクス拡張

---

## 🧪 Agent Regression (WIP)

**Agent Regression Testing Framework** - エージェント出力の品質と一貫性を保証する自動テストフレームワーク

### 概要
- **テストケース管理**: CSV形式でテストケースを定義・管理
- **自動実行**: CLI/プログラムからテスト実行
- **評価・レポート**: パスレート、スコア、実行時間などのメトリクス
- **週次レポート**: トレンド分析と改善提案

### クイックスタート

```bash
# テストケースを作成
# cases/agent_regression.csv を編集

# テスト実行
python -m agentops.cli cases/agent_regression.csv -v

# 週次レポート生成（当週vs前週比較）
python -m agentops report --days 14 --baseline-days 14 -o reports/regression_report.md --verbose

# レポート確認
ls reports/agentreg/
cat reports/regression_report.md
```

### 回帰分析レポート機能

**新機能**: Week-over-Week 比較による回帰検出

```bash
# 基本的な使用方法
python -m agentops report --days 7

# ベースライン期間を指定して実行
python -m agentops report --days 14 --baseline-days 14 -o reports/weekly_report.md

# 詳細ログ出力
python -m agentops report --days 7 --verbose
```

**レポートに含まれる情報:**
- 📈 Week-over-Week Summary - 全体/S1/S2 成功率の変化
- 📊 失敗タイプの変化 - failure_type ごとの増減数
- 🔴 トップ回帰ケース - 最悪化した 5 つのテストケース（S1 優先）
- 📋 Individual Runs - 各実行の詳細メトリクス

**レポート例:**
```
## Week-over-Week Summary
- 全体成功率: 62.50% (前週: 100.00%) → **-37.50%**
- S1成功率: 25.00% (前週: 100.00%) → **-75.00%**
- S2成功率: 100.00% (前週: 100.00%) → **+0.00%**

## トップ回帰ケース（前週比で最も悪化）
| ケース | 重要度 | カテゴリ | 前週 | 今週 | 変化 | 主な失敗 |
|--------|--------|---------|------|------|------|---------|
| TC004 | S1 | api | 100.0% | 25.0% | **-75.0%** | quality_fail |
```

### ドキュメント
- [オンボーディングガイド](docs/agentreg_onboarding_onepager.md)
- [週次レポートテンプレート](docs/agentreg_weekly_report_template.md)

**ステータス**: 🚧 開発中（基本機能実装済み）

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

# 開発者ガイド - LLMOps Lab

## 🚀 実行方法

### セットアップ
```bash
# 依存パッケージのインストール
pip install -e ".[dev]"
```

### API 起動（FastAPI）
```bash
python -m uvicorn src.llmops.gateway:app --host 127.0.0.1 --port 8000
# 開発時は --reload を付けてもOK
```

#### プロバイダ選択
- デフォルト: `mock`（テスト用、APIキー不要）
- 本番: `openai`（OpenAI API統合、APIキー必須）

**OpenAI使用時の設定**
```bash
# 環境変数でAPIキー設定
export OPENAI_API_KEY="sk-..."

# または configs/default.yaml を編集
provider: openai
model: gpt-4o-mini  # または gpt-4o, gpt-4-turbo など
```

### テスト実行
```bash
make test        # または pytest -v
```

### コード品質チェック
```bash
make lint        # pylint実行
make format      # black でコードフォーマット
```

### クリーンアップ
```bash
make clean       # __pycache__ と .pyc 削除
```

---

## 🔄 CI/CD

### GitHub Actions
- ワークフロー: `.github/workflows/ci.yml`
- トリガー: push（main/dev/chore/feature/fix）、PR（main/dev）
- マトリックス: Python 3.10, 3.11
- 実行内容:
  - テスト（pytest）
  - 評価（evals/run_eval.py）
  - コード品質チェック（pylint）
  - ログファイル確認
  - 評価レポートをArtifactとして保存（30日間）

### ローカルでCI相当を実行
```bash
# テスト
python -m pytest -v

# 評価
python -m evals.run_eval

# Lint
pylint src/ tests/ --fail-under=8.0
```

---

## 📈 評価（Evals）

### 実行
```bash
python -m evals.run_eval        # または make eval
```

### 出力
- レポート: evals/report.json
- 計測: JSON遵守率・エラー率・平均latency_ms

### ダミーケース
- 10件（半分は schema 指定）
- API は MockProvider を使用

---

## 📌 ブランチ運用

| ブランチ | 用途 | 例 |
|---------|------|-----|
| `main` | 本番環境対応 | リリース版 |
| `dev` | 開発ベース | 複数機能の統合 |
| `feature/*` | 新機能 | `feature/llm-prompt-optimization` |
| `fix/*` | バグ修正 | `fix/tokenizer-issue` |
| `eval/*` | 評価・実験 | `eval/model-comparison` |

**フロー**：
```
feature/* → dev (PR + review) → main (release)
```

---

## 🔄 変更ルール（AGENT_RULES に準拠）

### ✅ マージ可能な条件
1. **テストがある** - `tests/` に対応するテストを追加
2. **評価ログがある** - 新機能は `evals/` に評価結果を記録
3. **依存関係が明示** - pyproject.toml に明記
4. **最大3ファイル変更** - 1 PR = 3ファイルまで

### ❌ マージ不可の例
- テストなし
- 依存パッケージを黙ってインストール
- 4ファイル以上の変更

### 変更後に実行すべきコマンド

```bash
# 1. テスト確認（必須）
make test

# 2. コード品質チェック
make lint

# 3. フォーマット統一
make format

# 4. コミット前最終確認
git status
```

---

## 📂 プロジェクト構成

```
llmops-lab/
├── src/              # メインコード
│   └── llmops/
├── tests/            # テストコード
│   ├── unit/
│   └── test_*.py
├── evals/            # 評価・メトリクス
│   ├── metrics/
│   └── results/
├── configs/          # 設定ファイル
├── docs/             # ドキュメント
├── Makefile          # 開発タスク
└── pyproject.toml    # プロジェクト定義
```

---

## 🧪 テスト実行例

```bash
# 全テスト実行
pytest -v

# 特定ファイルのみ
pytest tests/unit/test_example.py -v

# カバレッジ確認（coverage インストール後）
pytest --cov=src tests/
```

---

## 📝 コミットメッセージ例

```
[feat] add LLM prompt optimizer
  - Add PrompOptimizer class in src/llmops/optimizer.py
  - Add unit tests in tests/unit/test_optimizer.py
  - Update eval/metrics/prompt_quality.json

[fix] fix tokenizer encoding issue
  - Handle UTF-8 edge cases
  - Add regression test
  - Closes #42

[eval] compare GPT-4 vs Claude performance
  - Benchmark on 100 samples
  - Results in evals/results/model_comparison_2026-01-25.json
```

---

## 🔍 ログの見方（Observability）

- ログファイル: `runs/logs/gateway.jsonl`（1行1JSON）
- 主なフィールド:
  - `timestamp`, `request_id`, `provider`, `model`
  - `latency_ms`, `token_usage`（prompt/completion/total）
  - `error_type`, `prompt_version`
  - `messages_masked`（content_hash, content_length）
- 注意: 個人情報（全文）は保存しない。マスク済みの長さ/ハッシュのみ。

例: tail で閲覧（Windows PowerShell）
```powershell
Get-Content runs/logs/gateway.jsonl -Tail 20
```

---

## ⚠️ 失敗モード＆トラブルシューティング

| 問題 | 原因 | 解決策 |
|------|------|--------|
| `pytest: command not found` | dev依存未インストール | `pip install -e ".[dev]"` |
| `ModuleNotFoundError: src.llmops` | src がパッケージでない | `src/llmops/__init__.py` を作成 |
| `make: command not found` | Windows GNU Make なし | `choco install make` or 手動実行 |
| テスト失敗（import Error） | PYTHONPATH 未設定 | `export PYTHONPATH=.:$PYTHONPATH` |

---

## 🔗 関連リソース
- [AGENT_RULES.md](./AGENT_RULES.md) - エージェント実行ルール
- [pytest 公式](https://docs.pytest.org/)
- [pylint 公式](https://www.pylint.org/)

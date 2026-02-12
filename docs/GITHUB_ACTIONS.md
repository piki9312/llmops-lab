# GitHub Actions CI/CD Pipeline

このドキュメントは、LLMOps Lab の GitHub Actions パイプラインについて説明します。

## 📋 ワークフロー一覧

### 1. **CI/CD Pipeline** (`ci.yml`)

メインの継続的インテグレーション/デプロイメント パイプライン。

**トリガー条件:**
- Push to `main`, `dev`, `feature/*`, `fix/*`, `chore/*`
- Pull Request to `main`, `dev`
- 日次スケジュール（UTC 2 AM）

**ジョブ:**

| ジョブ | 説明 | マトリックス |
|--------|------|------------|
| **Lint** | Black、Pylint、isort チェック | Python 3.11 |
| **Test** | ユニットテスト実行 | Python 3.10, 3.11, 3.12 |
| **Evaluation** | モデル評価実行 | Python 3.11 |
| **Build** | パッケージビルド | Python 3.11 |
| **Security** | Bandit、Safety チェック | Python 3.11 |
| **Docker Build** | Docker イメージビルド | main/dev ブランチのみ |
| **Status** | 全体ステータス確認 | 常に実行 |

**成果物:**
- Coverage レポート（codecov へアップロード）
- Evaluation レポート（30 日間保持）
- Docker ビルドキャッシュ

---

### 2. **Release** (`release.yml`)

リリースタグ (v*) でトリガーされるリリースパイプライン。

**トリガー条件:**
- Git タグ `v*` への Push（例：`v0.3.5`）

**ジョブ:**

| ジョブ | 説明 |
|--------|------|
| **Release** | GitHub Release 作成、PyPI へアップロード |
| **Docker Release** | Docker Hub へイメージをプッシュ |

**必要な Secrets:**
- `PYPI_API_TOKEN` - PyPI 認証トークン
- `DOCKER_USERNAME` - Docker Hub ユーザー名
- `DOCKER_PASSWORD` - Docker Hub パスワード

**使用例:**
```bash
# リリースの作成
git tag v0.3.5
git push origin v0.3.5
```

---

### 3. **Weekly Regression Report** (`regression-report.yml`)

週次の回帰分析レポートを自動生成。

**トリガー条件:**
- 毎週月曜日 UTC 9 AM
- Manual trigger with custom parameters

**パラメータ:**
- `days`: レポートに含める日数（デフォルト：7）
- `baseline_days`: ベースライン期間の日数（デフォルト：7）

**成果物:**
- `weekly_regression_report.md` - 回帰分析レポート（90 日間保持）

**使用例:**
```bash
# UI から "Run workflow" をクリック
# または GitHub CLI を使用
gh workflow run regression-report.yml \
  -f days=14 \
  -f baseline_days=14
```

---

## ✅ AgentReg を PR の品質ゲートにする（推奨）

このリポジトリの強みは「回帰テスト×運用（CI）」なので、PR に以下の 2 つを入れるのを推奨します。

1) **回帰テスト実行**（PRの成果物を作る）

```yaml
- name: Run AgentReg (PR)
  run: |
    python -m pip install --upgrade pip
    pip install -e ".[dev]"
    python -m agentops run-daily cases/agent_regression.csv --log-dir runs/agentreg -v
```

2) **ベースライン比較レポート**（main の成果物を baseline にして比較）

- ベースラインの置き場所（artifact / repo snapshot）を 1 つ決め、PR 側で取得して比較します。
- レポート生成は `python -m agentops report --days ... --baseline-days ...` を使用します。

設計方針: [docs/AGENTREG_CI_PRODUCT.md](AGENTREG_CI_PRODUCT.md)

---

### 4. **Nightly Tests** (`nightly.yml`)

24 時間ごとのテスト実行。

**トリガー条件:**
- 毎日 UTC 0 AM（深夜）
- Manual trigger

**特徴:**
- 全 Python バージョンでテスト実行（3.10, 3.11, 3.12）
- カバレッジレポート生成
- テスト結果を PR に自動コメント

**成果物:**
- JUnit XML テスト結果
- カバレッジレポート

---

### 5. **Dependency Updates** (`dependencies.yml`)

依存パッケージの定期チェック。

**トリガー条件:**
- 毎週日曜日 UTC 3 AM
- Manual trigger

**チェック項目:**
- 古いパッケージの検出
- セキュリティ脆弱性のスキャン（Safety）

**成果物:**
- `dependency_report.md` - 依存パッケージレポート
- `safety-report.json` - セキュリティレポート

---

### 6. **PR Checks** (`pr-checks.yml`)

プルリクエスト時の自動チェック。

**トリガー条件:**
- PR オープン、更新時
- `main`, `dev` ブランチへの PR

**ジョブ:**

| ジョブ | 説明 |
|--------|------|
| **Changed Files** | 変更ファイルを分析 |
| **Validate PR** | PR タイトルと形式チェック |
| **Lint PR Files** | 変更ファイルのリント |
| **Test PR Changes** | テスト実行 |
| **PR Summary** | 結果をコメント |

**Conventional Commits チェック:**
```
✅ feat(api): add new endpoint
✅ fix: resolve timeout issue
✅ docs: update README
❌ update something (形式に従わない)
```

---

## 🔧 セットアップ手順

### 1. リポジトリ設定

GitHub リポジトリの Settings → Actions → General で以下を確認：

- ✅ Actions permissions: "Allow all actions and reusable workflows"
- ✅ Workflow permissions: "Read and write permissions"

### 2. Secrets の設定

Settings → Secrets and variables → Actions に以下を追加：

**PyPI デプロイ用:**
```
PYPI_API_TOKEN = pypi-AgEIcHlwaS5vcmc...
```

**Docker レジストリ用:**
```
DOCKER_USERNAME = your_username
DOCKER_PASSWORD = your_token
```

### 3. Branch Protection ルール

Settings → Branches → Branch protection rules で以下を設定：

```
Branch name pattern: main
✅ Require status checks to pass before merging
  - ci / lint
  - ci / test
  - ci / security
✅ Require branches to be up to date before merging
✅ Dismiss stale pull request approvals
```

---

## 📊 ステータスバッジ

README に以下のバッジを追加できます：

```markdown
[![CI/CD](https://github.com/username/llmops-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/username/llmops-lab/actions)
[![Tests](https://img.shields.io/github/actions/workflow/status/username/llmops-lab/ci.yml?label=tests)](https://github.com/username/llmops-lab/actions)
[![codecov](https://codecov.io/gh/username/llmops-lab/branch/main/graph/badge.svg)](https://codecov.io/gh/username/llmops-lab)
```

---

## 🚀 ワークフロー実行例

### GitHub CLI を使用した手動実行

```bash
# 特定のワークフローを実行
gh workflow run ci.yml

# パラメータ付きで実行
gh workflow run regression-report.yml \
  -f days=14 \
  -f baseline_days=7

# 実行状況を監視
gh run watch

# 結果を表示
gh run list --workflow=ci.yml
```

### ウェブUI から実行

1. GitHub リポジトリ → Actions
2. 左側のワークフローを選択
3. "Run workflow" ボタンをクリック
4. パラメータを入力（オプション）
5. "Run workflow" を実行

---

## 📈 パフォーマンス最適化

### キャッシュの活用

すべてのワークフローで pip キャッシュを有効化：

```yaml
- uses: actions/setup-python@v5
  with:
    python-version: '3.11'
    cache: 'pip'
```

### マトリックスの効率化

テスト実行を複数バージョンで並列化：

```yaml
strategy:
  matrix:
    python-version: ["3.10", "3.11", "3.12"]
```

### Artifact の管理

不要なファイルを保持しない：

```yaml
retention-days: 30  # デフォルト 90 日
```

---

## 🆘 トラブルシューティング

### ワークフローが実行されない

**確認項目:**
1. ✅ Actions が有効か？（Settings → Actions）
2. ✅ トリガー条件が正しいか？（ブランチ、タグなど）
3. ✅ Workflow ファイルの YAML 形式は正しいか？

**デバッグ:**
```bash
# ログを確認
gh run view <run_id> --log

# 最新のワークフロー実行を表示
gh run list --workflow=ci.yml --limit 5
```

### テストが失敗する

1. ローカルで同じテストを実行
   ```bash
   pytest tests/ -v
   ```

2. ワークフローログをダウンロード
   - Actions → 該当の実行 → 右上の "..." → "Download logs"

3. Python バージョンを確認
   ```bash
   python --version
   ```

### Docker ビルドが失敗する

1. ローカルでビルド
   ```bash
   docker build -t llmops-lab .
   ```

2. `Dockerfile` の構文を確認

3. ビルドキャッシュをクリア
   ```bash
   gh actions-cache delete <cache-id> --confirm
   ```

---

## 📚 参考リソース

- [GitHub Actions Documentation](https://docs.github.com/actions)
- [Workflow Syntax Reference](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
- [Actions Marketplace](https://github.com/marketplace?type=actions)
- [Conventional Commits](https://www.conventionalcommits.org/)

---

**最終更新:** 2026-02-08
**Version:** 1.0.0

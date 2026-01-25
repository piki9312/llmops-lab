# LLMOps Lab - 初期化済みプロジェクト

このリポジトリは **LLMOps（大規模言語モデル運用）学習**用の作業場です。

## 🎯 目的

- LLMOps の開発フロー学習
- テスト・評価の自動化
- CI/CD パイプライン構築
- 依存関係管理のベストプラクティス

## 📦 プロジェクト構成

```
llmops-lab/
├── src/llmops/           # コア実装
├── tests/unit/           # ユニットテスト
├── evals/metrics/        # 評価メトリクス
├── configs/              # 設定ファイル
├── docs/
│   ├── AGENT_RULES.md   # エージェント実行ルール
│   └── README_DEV.md    # 開発者ガイド
├── Makefile              # 開発タスク自動化
└── pyproject.toml        # プロジェクト定義
```

## 🚀 クイックスタート

```bash
# 1. セットアップ
pip install -e ".[dev]"

# 2. テスト実行
make test

# 3. コード品質チェック
make lint

# 4. 開発ドキュメント
cat docs/README_DEV.md
```

## 📖 ドキュメント

- [開発者ガイド](docs/README_DEV.md) - セットアップ、ブランチ運用、変更ルール
- [エージェントルール](docs/AGENT_RULES.md) - 自動化エージェント実行ルール

## ✅ 実装済み

- ✓ Pythonプロジェクト構成（pyproject.toml）
- ✓ 開発タスク自動化（Makefile）
- ✓ ダミーテスト＆ユーティリティ
- ✓ 開発者ガイド（README_DEV.md）

## 🔄 次のステップ

1. `pip install -e ".[dev]"` で依存パッケージをインストール
2. `make test` でテスト実行
3. [README_DEV.md](docs/README_DEV.md) で開発フロー確認
4. 必要な機能を `feature/*` ブランチで実装

---

**バージョン**: 0.1.0 | **ステータス**: 初期化完了 ✅

# CI の使い方（AgentReg: 回帰テスト×運用）

このリポジトリは **LLM/Agent の変更で品質が落ちたかを CI で自動検知**するための回帰テスト基盤（AgentReg）を提供します。

---

## いつ回るか

GitHub Actions の [AgentReg Regression](../.github/workflows/regression.yml) が以下で実行されます。

- **pull_request**: main 向け PR ごと
- **push**: main への push
- **schedule**: 毎日 09:00 JST（= 00:00 UTC 目安）
- **workflow_dispatch**: 手動実行

---

## 何を実行しているか（コマンド）

### 1) 回帰実行（JSONL 永続化）

```bash
python -m agentops run-daily cases/agent_regression.csv --log-dir runs/agentreg -v
```

- 出力（永続化先）: `runs/agentreg/YYYYMMDD.jsonl`
- 1行=1ケースの実行結果

### 2) レポート生成（Markdown）

```bash
python -m agentops report --log-dir runs/agentreg --days 1 --baseline-days 1 -o reports/ci_regression_report.md -v
```

- `--days`: 「今週（=現在期間）」として集計する日数
- `--baseline-days`: 「ベースライン（=比較対象期間）」として集計する日数
  - ベースライン期間は現在期間の **直前** に設定されます

- 出力先: `reports/ci_regression_report.md`

---

## Artifacts（成果物）の見方

ワークフロー実行の画面で **Artifacts** に以下がアップロードされます。

- `runs/**`（JSONL）
- `reports/**`（Markdown レポート）

### JSONL（runs/agentreg/*.jsonl）

各行に以下の情報が入っています（抜粋）:

- `run_id`: 実行を関連付けるID（CIでは UUID を採番）
- `case_id`: テストケースID
- `severity`: `S1` / `S2`
- `passed`: pass/fail
- `failure_type`: `bad_json` / `quality_fail` / `timeout` など
- `latency_ms`, `cost_usd`

### レポート（reports/*.md）

- 全体成功率、S1/S2成功率
- 前期間比較（データがあれば）
- 失敗タイプ増減
- Top 回帰ケース

---

## 失敗時（S1）の扱い

最優先のゲート条件は **S1 の失敗が1つでもあれば CI を Fail（赤）**にすることです。

- ワークフローでは `scripts/ci_gate_s1.py` が JSONL をパースして
  - `S1 failed > 0` → `exit 1`
  - `S1 failed == 0` → `exit 0`

### 参照する JSONL と対象 run の選び方

- `runs/agentreg/` 配下の **最新の JSONL**（通常は `YYYYMMDD.jsonl`）を選びます
- その JSONL の中で **最新の `run_id`**（timestamp / 最後の出現順）を対象に集計します
- CI では確実性のため `--run-id` を明示して同一 run を評価します

> 注: `run-daily` は「失敗が1つでもあると終了コード1」ですが、CIではいったん継続し、最終的に **S1のみ**でゲートしています。

---

## ローカルで同じことをやる

```bash
# 回帰実行（JSONLに追記）
python -m agentops run-daily cases/agent_regression.csv --log-dir runs/agentreg -v

# レポート生成
python -m agentops report --log-dir runs/agentreg --days 1 --baseline-days 1 -o reports/ci_regression_report.md -v
```

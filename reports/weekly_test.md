# Agent Regression Weekly Report

**Week:** 2026-01-26 to 2026-02-01

## Summary（上の人向け）

- 総合判定: 🔥重大
- S1成功率: 0.00%（先週比 N/A）
- S2成功率: 100.00%（先週比 N/A）
- 一番重要な回帰: N/A（先週データなし）
- 来週のアクション:
  - 品質低下: プロンプト/評価ロジック改善
  - 回帰ケースの追加と閾値の再確認
  - 回帰ケースの追加と閾値の再確認

## 主要メトリクス（運用担当向け）

- 総実行数: 2
- 成功率（全体）: 50.00%
- 成功率（S1）: 0.00%
- 成功率（S2）: 100.00%
- レイテンシ p50/p95: 0.00ms / 0.00ms
- コスト/タスク: $0.000000
- 失敗分類内訳:
  - quality_fail: 10件 (100.0%)

## 失敗トップ10（どこが壊れてるか）
- TC004 / quality_fail / 2件 / 原因候補: prompt/エージェントロジック
- TC005 / quality_fail / 2件 / 原因候補: prompt/エージェントロジック
- TC006 / quality_fail / 2件 / 原因候補: prompt/エージェントロジック
- TC007 / quality_fail / 2件 / 原因候補: prompt/エージェントロジック
- TC008 / quality_fail / 2件 / 原因候補: prompt/エージェントロジック

## Individual Runs

### Run 1b87b25a
- Timestamp: 2026-02-01 19:25:34
- Cases: 10
- Passed: 5
- Failed: 5
- Pass Rate: 50.00%

### Run ecd1d9fa
- Timestamp: 2026-02-01 19:29:52
- Cases: 10
- Passed: 5
- Failed: 5
- Pass Rate: 50.00%

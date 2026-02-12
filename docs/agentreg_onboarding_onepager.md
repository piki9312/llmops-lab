# Agent Regression Testing（AgentReg）- Onboarding Guide

## Overview

Agent Regression（AgentReg / AgentOps）は、AI エージェントの変更で **品質が落ちたかを CI で自動検知**するための回帰テスト基盤です。

## What is Agent Regression?

Agent regression testing validates that changes to your AI agent don't break existing functionality. It automatically runs test cases against your agent and compares outputs to expected results.

## Quick Start

### 1. Create Test Cases

Add test cases to `cases/agent_regression.csv`:

```csv
case_id,name,input_prompt,expected_output,category
TC001,Greeting,Hello!,A friendly response,basic
```

### 2. Run Tests

```bash
# 1回実行して JSONL に追記
python -m agentops run-daily cases/agent_regression.csv --log-dir runs/agentreg -v

# ベースライン比較レポート（直近7日 vs その前7日）
python -m agentops report --log-dir runs/agentreg --days 7 --baseline-days 7 -o reports/weekly_regression_report.md -v
```

### 3. Review Results

Check the console output for pass/fail status and review detailed reports in `reports/agentreg/`.

## Architecture

```
┌─────────────┐
│ Test Cases  │ (CSV files in cases/)
└──────┬──────┘
       │
       v
┌─────────────┐
│   Loader    │ (load_cases.py)
└──────┬──────┘
       │
       v
┌─────────────┐
│   Runner    │ (runner.py)
└──────┬──────┘
       │
       v
┌─────────────┐
│  Evaluator  │ (evaluator.py)
└──────┬──────┘
       │
       v
┌─────────────┐
│   Reports   │ (report_weekly.py)
└─────────────┘
```

## Key Components

### Models (`models.py`)
Defines data structures:
- `TestCase`: Input test case
- `TestResult`: Output result
- `RegressionReport`: Aggregated report

### Loader (`load_cases.py`)
Loads test cases from CSV files.

### Runner (`runner.py`)
Executes test cases against your agent.

### Evaluator (`evaluator.py`)
Calculates metrics and scores.

### Weekly Reporter (`report_weekly.py`)
Generates weekly summary reports.

### CLI (`cli.py`)
Command-line interface for running tests.

## Best Practices

1. **Write Clear Test Cases**: Each test case should have a single, clear objective
2. **Organize by Category**: Group related test cases for easier analysis
3. **Regular Testing**: Run regression tests on every major change
4. **Review Failed Cases**: Investigate and document all failures
5. **Track Trends**: Monitor pass rates over time

## Directory Structure

```
cases/                    # Test case definitions
  agent_regression.csv
runs/agentreg/           # Test run outputs
reports/agentreg/        # Generated reports
src/agentops/            # Source code
```

## Configuration

[TODO: Add configuration options when implemented]

## Integration with CI/CD

最小構成は「main でベースラインを更新」→「PR で比較してゲート」です。

### main（nightly / merge後）
- `run-daily` を実行して JSONL を生成
- JSONL または週次レポートを artifact として保存

### PR
- `run-daily` を実行して当該PRの結果を生成
- main の最新 artifact を取得してベースラインにする
- `report` を実行して差分を可視化（必要なら PR コメント）

参考: [docs/GITHUB_ACTIONS.md](GITHUB_ACTIONS.md) と [docs/AGENTREG_CI_PRODUCT.md](AGENTREG_CI_PRODUCT.md)

## Troubleshooting

### Common Issues

**Problem:** Test cases not loading  
**Solution:** Verify CSV format matches schema

**Problem:** All tests failing  
**Solution:** Check agent function is properly configured

## Getting Help

- Check documentation in `docs/`
- Review example test cases in `cases/`
- See architecture docs for deep dive

## Next Steps

1. Create your first test case
2. Run a test
3. Review the report
4. Set up weekly reporting
5. Integrate with CI/CD

---
*Last updated: 2026-01-31*

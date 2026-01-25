"""LLM Gateway - Minimal Evaluation Runner

目的（MVP）:
- 単一エンドポイントで LLM 呼び出しを行い、運用に必要な評価指標を収集する。
- 外部 LLM がなくても動作（MockProvider）。

計測項目:
- JSON遵守率（schema指定時に json が dict で返る割合）
- エラー率（error_type が null でない割合）
- 平均 latency_ms

"""

from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi.testclient import TestClient

from src.llmops.gateway import app


def build_cases() -> List[Dict[str, Any]]:
    """評価用ダミーケースを10個作成する。

    入力: なし
    出力: リクエストペイロードのリスト（10件）
    副作用: なし
    失敗モード: なし（固定データ生成）
    """
    cases: List[Dict[str, Any]] = []
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "user", "content": "Generate JSON"},
        {"role": "user", "content": "Count tokens"},
        {"role": "user", "content": "Latency test"},
        {"role": "user", "content": "Another sample"},
    ]

    # 10件: 半分は schema 指定あり
    for i in range(10):
        payload: Dict[str, Any] = {
            "messages": [messages[i % len(messages)]],
            "max_output_tokens": 256,
        }
        if i % 2 == 0:
            payload["schema"] = {"properties": {"name": "string", "age": "number"}}
        cases.append(payload)
    return cases


def run_eval(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """ケースを実行し、評価メトリクスを収集する。

    入力: cases（POST /generate 用のペイロード配列）
    出力: 指標 dict（json遵守率、エラー率、平均latency_ms）
    副作用: FastAPI TestClient を利用してアプリを呼び出し、evals/report.json を書き出す
    失敗モード:
      - API 呼び出し失敗 → 該当ケースは error として計上
      - JSON 書き込み失敗 → 例外発生（呼び出し元で扱う）
    """
    client = TestClient(app)

    latencies: List[float] = []
    errors = 0
    schema_cases = 0
    json_ok = 0

    for payload in cases:
        has_schema = "schema" in payload
        if has_schema:
            schema_cases += 1
        resp = client.post("/generate", json=payload)
        if resp.status_code != 200:
            errors += 1
            continue
        data = resp.json()
        latencies.append(float(data.get("latency_ms", 0)))
        if data.get("error_type") is not None:
            errors += 1
        if has_schema:
            # JSON遵守: json が dict で返る
            if isinstance(data.get("json"), dict):
                json_ok += 1

    json_adherence_rate = (json_ok / schema_cases) if schema_cases > 0 else 0.0
    error_rate = (errors / len(cases)) if cases else 0.0
    avg_latency_ms = statistics.mean(latencies) if latencies else 0.0

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sample_size": len(cases),
        "schema_cases": schema_cases,
        "json_ok": json_ok,
        "json_adherence_rate": json_adherence_rate,
        "error_count": errors,
        "error_rate": error_rate,
        "avg_latency_ms": avg_latency_ms,
    }

    # 保存
    out_path = Path("evals/report.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))

    return report


def main() -> None:
    """評価を実行して結果を出力する。

    入力: なし
    出力: コンソール出力（要約）と evals/report.json の保存
    副作用: ファイル書き込み（evals/report.json）
    失敗モード: 書き込み不能時に例外
    """
    cases = build_cases()
    report = run_eval(cases)
    print("✅ Eval 完了")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

# AgentReg（回帰テスト×運用）: Dev向け CI プロダクト方針

## ねらい（やること / やらないこと）

**やること**
- LLM/Agent の変更（prompt / tool / router / model / provider / code）で **品質が落ちたかを CI で自動検知**する
- 「失敗したか」だけでなく、**どこが悪化したか（S1優先 / 失敗タイプ / Top回帰ケース）**を自動で要約する
- PR に **機械可読な指標**（成功率、デルタ、p95、コスト/タスク）を残し、合否ゲートにする

**やらないこと（当面）**
- 本番トラフィック監視・アラート（APM/監視SaaSの置き換え）
- マルチテナントSaaS（請求、RBAC、顧客管理）

---

## ターゲットユーザー
- AI/Agent を開発・運用する Dev（Platform/Backend/ML/Applied AI）
- 「変更のたびに壊れる」「性能劣化に気づけない」「原因追跡がつらい」チーム

---

## プロダクトの中核ループ（CIで回す）

1) **回帰スイート実行**
- CSV（ケース）を固定して毎回同じ入力を流す
- 結果を JSONL（1ケース=1行）に永続化（`runs/agentreg/YYYYMMDD.jsonl`）

2) **ベースライン比較**
- 直近の基準期間（例: 直前7日 / mainの最新成功）と比較
- 指標のデルタを計算し、Top回帰ケースを抽出

3) **判定（ゲート）**
- 例: S1 成功率、全体成功率、Worst回帰デルタ、失敗タイプ増加など
- 失敗時は PR を落とす（exit code != 0）

4) **説明（PRコメント/レポート）**
- 何が悪化したかを Markdown で出力
- 次アクション候補（原因カテゴリ）を提示

---

## 現状の実装対応（このリポジトリ）

- 実行と永続化: `python -m agentops run-daily <cases.csv>` → JSONL append
- 集計/分析/レポート: `python -m agentops report --days 7 --baseline-days 7`
- 週次レポート: [src/agentops/report_weekly.py](../src/agentops/report_weekly.py)（オーケストレータ）
  - 集計: [src/agentops/aggregate.py](../src/agentops/aggregate.py)
  - 原因分析: [src/agentops/analyze.py](../src/agentops/analyze.py)
  - Markdown生成: [src/agentops/render_md.py](../src/agentops/render_md.py)

---

## 設計原則（CIプロダクト向け）

- **Deterministic-ish**: できる限り再現性（温度、seed、prompt固定、tools固定）
- **S1最優先**: クリティカルケースは別ゲート（S1とS2で閾値を分ける）
- **出力は二系統**
  - 機械可読: JSON（メトリクス/閾値/判定）
  - 人間可読: Markdown（Top回帰・原因・次アクション）
- **ストレージは差し替え可能**: 今はJSONL、将来はS3/DBへ

---

## 推奨CI構成（最小）

- PR:
  - 回帰テスト実行（mockまたはsecretsがあるなら実LLM）
  - ベースライン（mainの最新）を取得
  - 比較してゲート判定
  - PRにサマリコメント

- main:
  - nightly（またはmerge後）に回帰を実行し baseline を更新（artifact/JSONL）

---

## 次の実装優先度（ロードマップ）

P0（CIプロダクトとして成立）
- `agentops check`（比較→exit code）を追加
- ベースライン取得パターンを1つ決めてドキュメント化（artifact or repo snapshot）
- 失敗時のPRコメント（要点だけ）

P1（使われる）
- しきい値設定（YAML）と、PRラベル/ディレクトリでルール切替
- ケースに ownership（team）/タグ/最小許容率を持たせる

P2（強い）
- 失敗差分の説明（json schema不一致、tool呼び出しの変化、token増など）
- 反復実行（n回）での安定性評価（揺らぎを検知）

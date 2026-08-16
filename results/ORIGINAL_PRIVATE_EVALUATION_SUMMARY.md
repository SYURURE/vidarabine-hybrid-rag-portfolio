# Original private-corpus evaluation summary

以下は、非公開の第三者資料由来コーパスを使用した元実習の保存済み集計値です。本文・質問文・回答ログは公開していません。この公開リポジトリで再実行した値ではなく、独立した第三者監査結果でもありません。

## Stage 6: vector retrieval

- 実行記録日: 2026-08-03
- 埋め込みモデル: `embeddinggemma:300m-qat-q8_0`
- 質問数: 9
- 合格: 9 / 9
- Positive Hit@1: 0.8333
- Positive Recall@5: 1.0000
- Blocked accuracy: 1.0000

## Stage 7: hybrid retrieval

- 実行記録日: 2026-08-03
- 質問数: 28
- 合格: 28 / 28
- Positive Hit@1: 0.8696
- Positive Recall@5: 1.0000
- Blocked accuracy: 1.0000

## Stage 8: end-to-end

- 実行記録日: 2026-08-03
- 回答モデル: `qwen3:1.7b`
- 質問数: 12
- 合格: 12 / 12

## 解釈上の注意

- 評価セットは小さく、同じプロジェクト内で作成したものです。
- 実際の臨床利用、最新情報、未知質問への性能を示しません。
- 非公開コーパスを含まないため、公開版から元の数値を再計算できません。
- 公開版の合成評価はソフトウェア経路の検査であり、医薬品情報の品質検査ではありません。

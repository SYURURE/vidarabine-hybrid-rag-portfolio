# Private corpus drop-in guide

## 目的

公開版の合成データを使うコードと、本物のビダラビン検索データを使うコードを分けず、同じコマンドで使えるようにします。実データはGitHubへ送らず、ローカルだけに置きます。

## 置き場所

次の名前で配置します。

```text
data/private/vidarabine_documents.jsonl
```

アプリは起動時にこのファイルを探します。

1. privateファイルがあれば、privateファイルを使用
2. privateファイルがなければ、`data/sample/synthetic_documents.jsonl`を使用

## 以前の実習ファイルを使う

次のどちらかを、そのまま入力にできます。

- `vidarabine_keyword_documents.jsonl`
- `vidarabine_chunks.jsonl`

配置時にファイル名だけ `vidarabine_documents.jsonl` にします。元の項目名は実行時にメモリ上で変換され、元ファイル自体は編集されません。

安全にコピーするには、リポジトリ直下で次を実行します。

```powershell
.\scripts\install_private_corpus.ps1 `
  -SourceFile "D:\private-rag-data\vidarabine_keyword_documents.jsonl"
```

## 切り替え確認

```powershell
python .\src\vidarabine_rag.py inspect
```

実データが選ばれた場合の例です。

```json
{
  "corpus_path": ".../data/private/vidarabine_documents.jsonl",
  "document_count": 45,
  "synthetic_document_count": 0,
  "input_schemas": {
    "legacy_keyword_or_chunk_export": 45
  },
  "status": "ready"
}
```

`inspect` は文書数と形式だけを返し、本文を表示しません。

## 検索

privateファイルがあれば、通常コマンドが自動的にそれを使います。

```powershell
python .\src\vidarabine_rag.py search "ビダラビンの質問"
python .\src\vidarabine_rag.py answer "ビダラビンの質問"
```

Ollama回答を使う場合です。

```powershell
python .\src\vidarabine_rag.py answer "ビダラビンの質問" --use-ollama
```

## 合成データへ戻す

`data/private/vidarabine_documents.jsonl`をリポジトリ外の保管場所へ移動すると、次回起動時から合成データへ戻ります。公開版のコードや設定を編集する必要はありません。

## GitHubへ送られないことの確認

`.gitignore`には次が登録されています。

```gitignore
data/private/
```

GitHub DesktopのChanges一覧に `data/private/vidarabine_documents.jsonl` が表示されないことを確認してください。ブラウザから手作業で実データを選択してアップロードしないでください。

公開ZIPを作り直す場合は、通常の圧縮操作ではなく次を使用してください。manifestに載っている公開ファイルだけを集めるため、`data/private`はZIPに入りません。

```powershell
.\scripts\build_public_zip.ps1
```

## 対応形式

| 入力形式 | 対応 |
|---|---|
| 公開サンプル形式 (`id`, `text`) | 対応 |
| 旧キーワード形式 (`document_id`, `display_text`, `search_text`) | 対応 |
| 旧チャンク形式 (`chunk_id`, `display_text`, `embedding_text`) | 対応 |
| PDF / Word / Excel | 直接は非対応。JSONLへの変換が必要 |
| 画像・スキャン | 直接は非対応。OCRと構造化が必要 |

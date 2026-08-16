# GitHubアップロード手順

## ブラウザから新規登録する場合

1. GitHubで新しいリポジトリを作ります。リポジトリ名の例は `vidarabine-hybrid-rag-portfolio` です。
2. 最初は `Private` で作成しても構いません。
3. 空のリポジトリ画面にある **uploading an existing file** を押します。
4. このZIPを展開し、最上位フォルダの**中身**をすべて選んでドラッグします。ZIPファイルそのものや、外側のフォルダだけを登録しないでください。
5. `.github` は隠しフォルダなので、ブラウザで選びにくい場合はGitHub Desktopを使うか、先に通常ファイルを登録してから `.github/workflows/verify-package.yml` をGitHub画面で作成します。
6. commit message に `Add public vidarabine RAG portfolio` と入力し、commitします。
7. **Actions** タブで `Verify public portfolio` の2つのjobが緑になることを確認します。

## GitHub Desktopを使う場合

1. ZIPを展開します。
2. GitHub Desktopで `File` → `Add local repository` を選びます。
3. 展開した `vidarabine-hybrid-rag-portfolio` を指定します。
4. Summaryに `Add public vidarabine RAG portfolio` と入力します。
5. `Commit to main`、続いて `Publish repository` または `Push origin` を押します。

## Publicへ切り替える前の確認

- READMEが正常に表示される
- `DATA_AVAILABILITY.md` が開く
- 実際の医薬品本文、チャンク、埋め込み、ログを追加していない
- APIキー、パスワード、個人情報、個人PCの絶対パスがない
- 最新commitのActionsが緑
- `LICENSE.md` の公開条件が希望どおり

Publicリポジトリは誰でも閲覧・cloneできます。他人が直接mainへ変更を書き込むことはできませんが、forkやPull Requestの提案は技術的に可能です。採用・mergeは所有者が決めます。

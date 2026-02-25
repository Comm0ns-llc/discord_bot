# Comm0ns C++ TUI (btop-like)

`設計書.md` の仕様をベースに、`btop_oss` 風のレイアウトで作った C++/ncurses ダッシュボードです。  
現在は Supabase の実データ（`users/messages/reactions/channels` など）を読み込んで表示します（モック表示は無効化済み）。

詳細なTUI運用ガイドは [TUI_GUIDE.md](./TUI_GUIDE.md) を参照してください。

## 構成

- `src/main.cpp`
  - 5画面 TUI（Overview / Members / Channels / Governance / Issues）
  - Stage1 ルール分類（URL/運営ch/短文/長文）
  - CP計算の基本式（カテゴリCP・チャンネル重み・TS倍率）
  - VP計算式（`floor(log2(CP+1))+1`, 上限6）と有効VP表示
  - Supabase REST API からのDBロード（`curl` + `jq`）
  - 投票/Issueテーブルが未作成の場合は `PENDING` 表示

## ビルド

```bash
cd comm0ns_cpp_tui
cmake -S . -B build
cmake --build build
```

## 実行

```bash
./build/comm0ns_tui
```

## DB接続

- `.env` の `SUPABASE_URL` と `SUPABASE_KEY` を参照します
- 実行環境に `curl` と `jq` が必要です
- 未設定/接続失敗時は `DB ERROR` 表示になります
- `r` キーで手動再読込できます

## キー操作

- `1`..`5`: ページ切替
- 上部タブクリック: ページ切替
- Members行クリック: 選択移動
- `j` / `k`: Members画面で選択移動
- `s`: Members画面でソートキー切替
- `r`: DB手動リフレッシュ
- `q`: 終了

## 設計書との対応

- メッセージ分類: `INFO / INSIGHT / VIBE / OPS / MISC`
- CP体系: カテゴリ別基本CP + チャンネル係数 + TS補正
- ストリークボーナス: `3/7/30日` ティア
- 議決権: `VP` と `有効VP`
- 投票: 通常決議/重要決議の成立条件表示
- 開発評価: Issue/スプリントとCP付与目安を表示

## 補足

この実装は Discord Bot 本体とは独立した可視化TUIです。  
フル機能化には以下のテーブル追加が必要です（未作成時はPENDING表示）:

- `members`（TS/Trust Score）
- `votes`（および関連集計テーブル）
- `issues`

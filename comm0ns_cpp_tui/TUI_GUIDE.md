# Comm0ns C++ TUI Guide

このドキュメントは `comm0ns_cpp_tui` の操作・内部仕様・運用時トラブル対応に特化したガイドです。

## 1. 概要

`comm0ns_cpp_tui` は、Discord Bot のスコア系データを Supabase から直接読み出して可視化する ncurses ベースのダッシュボードです。

| 項目 | 内容 |
|---|---|
| 画面数 | 5ページ（Overview / Members / Channels / Governance / Issues） |
| データソース | Supabase REST API |
| モック | 無効化済み（コードは参考として残置） |

## 2. 前提条件

| 項目 | 必須 | 備考 |
|---|---|---|
| `cmake` / C++17 | Yes | ビルドに使用 |
| `ncurses` | Yes | TUI描画 |
| `curl` | Yes | Supabase REST取得 |
| `jq` | Yes | JSON整形 |
| `SUPABASE_URL` / `SUPABASE_KEY` | Yes | `.env` で管理 |

## 3. ビルドと起動

### 3.1 ビルド

```bash
cd /Users/tsukuru/Dev/myprojects/comm0ns/comm0ns_discord_bot/comm0ns_cpp_tui
cmake -S . -B build
cmake --build build -j4
```

### 3.2 起動

`.env` は自動読み込みしないため、先に環境変数として export してください。

```bash
cd /Users/tsukuru/Dev/myprojects/comm0ns/comm0ns_discord_bot
set -a; source .env; set +a
export LANG=ja_JP.UTF-8
export LC_ALL=ja_JP.UTF-8
./comm0ns_cpp_tui/build/comm0ns_tui
```

## 4. キー操作

| キー | 動作 | 対象 |
|---|---|---|
| `1`..`5` | ページ切替 | 全体 |
| 上部タブクリック | ページ切替 | 全体 |
| Members行クリック | 選択行の移動 | Members |
| `j` / `k` | 選択行の移動 | Members |
| `s` | ソートキー切替 | Members |
| `r` | DB手動再読込 | 全体 |
| `q` | 終了 | 全体 |

## 5. 画面構成

| ページ | 主な表示内容 |
|---|---|
| Overview | Activity Engine / Community Stats / Live Feed / Category + Rewards |
| Members | 左: メンバー一覧、右: 選択メンバー詳細 |
| Channels | 左: チャンネル活動量、右: 分類サンプルと運用状態 |
| Governance | 左: 投票一覧と成立判定、右: VP分布 |
| Issues | Issue状態集計・一覧・Sprint表示 |

## 6. 画面内に登場する指標（用語）解説

TUI各画面に表示される略語および指標は、Comm0nsの人物評価システム仕様に基づいています。

### 総合指標
- **`CP` (貢献ポイント / Contribution Points)**: コミュニティでの活動量や質に基づく累計スコア。
- **`TS` (信頼スコア / Trust Score)**: メンバーのコミュニティに対する信頼度。初期値・上限は100で、ペナルティ等でのみ減点されます。
- **`VP` (議決権 / Voting Power)**: 投票力。累積CPと現在のTSを加味して対数スケール等で算出され、方針決定時に用いる票の重みです。
- **`STK` (STAKE)**: ステーキング量（トークンや貢献の預入れ想定）。
- **`CP%`**: コミュニティ全体の総CPに対する、該当メンバーが保有するCPのシェア率。

### 行動カテゴリ（メッセージ種別）
メンバーの発言は内容に基づき分類され、それぞれ集計・可視化されます。
- **`INFO` (情報シェア)**: URLやニュース、資料の共有など、コミュニティにとって参照価値のある発言。
- **`INSI` / `INSIGHT` (知見・意見)**: 分析や経験に基づく考察、オリジナルな思考・提案を伴う発言。
- **`VIBE` (コミュニティ活性化)**: 挨拶、盛り上げ、歓迎など、場の空気を良くするコミュニケーション。
- **`OPS` (運営・調整)**: タスク管理、スケジュール調整、告知などの実践的な運営サポート活動。

### 6.1 Members ページ補足

| 項目 | 内容 |
|---|---|
| 左ペイン列 | `CP / TS / VP / STK / INFO / INSI / VIBE / OPS / CP%` |
| 列揃え | UTF-8表示幅ベースで整列 |
| 右ペイン | カテゴリ構成、VP計算式 |

### 6.2 Channels / Governance / Issues の PENDING 表示

| テーブル状態 | 表示 |
|---|---|
| `members` 未整備 | `members.ts: PENDING` |
| `votes` 未整備 | 投票欄に `PENDING` 表示 |
| `issues` 未整備 | Issues欄に `PENDING` 表示 |

## 7. データ取得仕様（Supabase）

| 種別 | 名前 | 必須 |
|---|---|---|
| Table | `users` | Yes |
| Table | `members` | No |
| Table | `channels` | Yes |
| Table | `messages` | Yes |
| Table | `reactions` | Yes |
| View | `analytics_daily_pulse` | Yes |
| View | `analytics_channel_leader_user` | Yes |
| View | `analytics_channel_ranking` | Yes |
| Table | `votes` | No |
| Table | `issues` | No |

## 8. 右上ステータスの意味

| ステータス | 意味 |
|---|---|
| `DB LIVE` | DB読込成功 |
| `DB STALE` | 既存データは保持しているが最新リフレッシュ失敗 |
| `DB ERROR` | 初回読込失敗（接続情報不足 / 到達不可など） |

## 9. トラブルシュート

### 9.1 `DB ERROR` のまま

切り分け順序:

1. `.env` の値確認
2. DNS解決確認
3. REST疎通確認

```bash
set -a; source .env; set +a
host=$(echo "$SUPABASE_URL" | sed -E 's#https?://([^/]+).*#\1#')
dig +short "$host"

curl -sS --fail --get "$SUPABASE_URL/rest/v1/users" \
  -H "apikey: $SUPABASE_KEY" \
  -H "Authorization: Bearer $SUPABASE_KEY" \
  --data-urlencode "select=user_id" \
  --data-urlencode "limit=1"
```

### 9.2 日本語が文字化けする

```bash
export LANG=ja_JP.UTF-8
export LC_ALL=ja_JP.UTF-8
```

### 9.3 `./build/comm0ns_tui` が見つからない

```bash
cd /Users/tsukuru/Dev/myprojects/comm0ns/comm0ns_discord_bot/comm0ns_cpp_tui
cmake --build build -j4
./build/comm0ns_tui
```

## 10. 拡張ポイント

| テーマ | 実施内容 |
|---|---|
| 投票機能の本運用化 | `votes` と関連集計テーブルを追加 |
| Issue機能の本運用化 | `issues` テーブルを追加 |
| TS精度向上 | `members` テーブルへ `ts`（または同義カラム）整備 |

# Discord Quality Scoring Bot

Discordコミュニティの質の高い発言を評価し、ランキング化するBotです。

## 特徴

- **発言スコア**: 発言1つにつき3pt
- **リアクションスコア**: 発言に対してリアクション1つにつき1pt
- **リアルタイム更新**: メッセージ送信・リアクション追加時に即時スコア反映

## スコアリングシステム

| 指標 | 説明 | ポイント |
|------|------|----------|
| Message | 発言1つにつき | 3pt |
| Reaction | 発言に対してリアクション1つにつき | 1pt |

## セットアップ

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 2. 環境変数の設定

`.env.example` を `.env` にコピーして、各値を設定してください。

```bash
cp .env.example .env
```

必要な値:
- `DISCORD_BOT_TOKEN`: Discord Botのトークン
- `DISCORD_APPLICATION_ID`: Discord Application ID（スラッシュコマンド用・推奨）

#### とりあえず動かす（DBなし / memoryモード）

`.env` に最低限これだけ入っていれば起動できます。

- `DISCORD_BOT_TOKEN`
- `STORAGE_BACKEND=memory`（デフォルトはmemory）

#### Supabaseに保存する（supabaseモード）

永続化してランキングを保持したい場合は、以下も設定してください。

- `STORAGE_BACKEND=supabase`
- `SUPABASE_URL`
- `SUPABASE_KEY`

### 3. データベースのセットアップ

Supabaseの SQL Editor で `migrations/001_initial_schema.sql` を実行してください。

### 4. Botの起動

```bash
python main.py
```

## スラッシュコマンド

| コマンド | 説明 |
|----------|------|
| `/rank` | 自分の順位とスコア内訳を表示 |
| `/leaderboard` | 上位10名のランキングを表示 |
| `/leaderboard weekly:True` | 週間ランキングを表示 |

## プロジェクト構成

```
discord_bot/
├── main.py                 # エントリーポイント
├── requirements.txt        # 依存関係
├── .env                    # 環境変数（要作成）
├── .env.example            # 環境変数テンプレート
├── migrations/
│   └── 001_initial_schema.sql  # DBスキーマ
└── src/
    ├── __init__.py
    ├── bot.py              # メインBotロジック
    ├── config.py           # 設定・定数
    ├── database.py         # Supabase連携
    ├── nlp_analyzer.py     # OpenAI NLP分析
    └── scoring.py          # スコア計算
```

## Discord Bot設定

Discord Developer Portalで以下の権限を設定してください:

### Bot Permissions
- Read Messages/View Channels
- Send Messages
- Use Slash Commands
- Read Message History

※ Active Scoreのみの場合、Privileged Gateway Intents は不要です。

## ライセンス

MIT License

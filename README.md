# Discord Quality Scoring Bot

Discordコミュニティの質の高い発言を評価し、ランキング化するBotです。

## 特徴

- **NLP分析**: OpenAI APIを使用してメッセージの品質を評価
- **複合スコアリング**: 発言数、品質、会話誘発、リアクションの4指標
- **リアルタイム更新**: メッセージ送信・リアクション追加時に即時スコア反映
- **コスト最適化**: 短いメッセージはAPI呼び出しをスキップ

## スコアリングシステム

| 指標 | 説明 | ポイント |
|------|------|----------|
| Active Score | 発言1つにつき | 1pt |
| NLP Context | 基本点 × 品質係数 | 0.1x ~ 1.5x |
| Conversation | リプライ1件につき | 5pt |
| Impact | 通常リアクション | 2pt |
| Impact | 特別リアクション (🔥🚀👍) | 5pt |

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
- `SUPABASE_URL`: SupabaseプロジェクトのURL
- `SUPABASE_KEY`: Supabaseのサービスロールキー
- `OPENAI_API_KEY`: OpenAI APIキー

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
- Add Reactions
- Read Message History

### Privileged Gateway Intents
- MESSAGE CONTENT INTENT
- SERVER MEMBERS INTENT

## ライセンス

MIT License

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

## 過去ログのインポート

Bot導入前の会話データをインポートし、ランキングに反映させることができます。
**[DiscordChatExporter](https://github.com/Tyrrrz/DiscordChatExporter)** と、付属のスクリプトを使用します。

### 1. DiscordChatExporter の準備（Mac）

Bot用のトークンを使用するのが安全です。

#### ダウンロード
1.  [Releasesページ](https://github.com/Tyrrrz/DiscordChatExporter/releases/latest) から `DiscordChatExporter.Cli.osx-arm64.zip` をダウンロード（M1/M2/M3 Macの場合）。
2.  解凍してフォルダを開く。

#### セキュリティ許可（初回のみ）
MacのGatekeeperにより停止されるため、ターミナルで許可します。
（ディレクトリは解凍先に合わせてください）

```bash
# フォルダ内の全ファイルの検疫を解除
xattr -r -d com.apple.quarantine .

# 実行権限を付与
chmod +x DiscordChatExporter.Cli
```

### 2. データのエクスポート

サーバーIDを指定して、全チャンネルを一括エクスポートします。

```bash
./DiscordChatExporter.Cli exportguild \
  -t "Bot <DISCORD_BOT_TOKEN>" \
  -g <SERVER_ID> \
  -f Json \
  -o "export_%C.json"
```

- `-t`: Botトークン（`Bot ` という接頭辞が必要です）
- `-g`: サーバーID（Discord上でサーバーアイコンを右クリック → IDをコピー）
- `-o`: 出力ファイル名パターン（`%C` はチャンネル名に置換されます）

### 3. インポートの実行

出力されたJSONファイルを、このプロジェクトのルートディレクトリに移動します。

```bash
# 例: ダウンロードフォルダから移動
mv ~/Downloads/DiscordChatExporter*/export_*.json ./
```

インポートスクリプトを実行します。

```bash
# ライブラリのセットアップ（初回のみ）
pip install supabase python-dotenv

# 全てのJSONファイルを読み込む
python tools/import_history.py *.json
```

処理が完了すると、過去のメッセージ数に応じて各ユーザーに「3pt/msg」が加算され、会話内容もDBに保存されます。

## プロジェクト管理・ガバナンス

このコードベースは **Organization** によって管理されています。

### 変更手順
Comm0ns運営メンバーまたはコントリビューターがコードを変更する場合：

1.  **ブランチ作成**: 直接 `main` にコミットせず、必ず新しいブランチを作成してください（例: `feature/cool-update`）。
2.  **Pull Request (PR)**: 変更が完了したらPRを作成してください。
3.  **レビュー & マージ**:
    - 通常は運営メンバーによるレビューを経てマージします。
    - 緊急時や合意形成済みの場合は、チャット（Discord等）で `tsukuru` または `fumi` に声をかけて即時マージを依頼してください。

### 将来の展望 (Vision)
現在はDiscordの分析が中心ですが、将来的には「Comm0ns」全体の活動データを可視化する **統合アナリティクスプラットフォーム** を目指しています。
Google Analyticsのように、データを：
- **軸を変えて比較**: 時系列、ユーザー属性、活動タイプなどで多角的に分析
- **ビジュアライズ**: グラフやヒートマップで視覚的に分かりやすく
- **カスタム可能**: ユーザーが見たいデータを自由に定義できる

「ただのデータ」を「面白いインサイト」に変え、コミュニティの熱量を可視化することが目標です。

### デザイン方針
**「かっこよく、燃えるUIを」**
- データを見るだけでなく、見ていてテンションが上がるような "Cool" なデザインを心がけてください。
- 無機質な管理画面ではなく、近未来的なダッシュボードやゲームのステータス画面のような没入感を目指します。

## ライセンス


MIT License

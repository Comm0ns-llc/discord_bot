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

## システム設計・アーキテクチャ

詳細なシステム設計、仕様、DBスキーマなどについては **[SYSTEM_DESIGN.md](./SYSTEM_DESIGN.md)** を参照してください。

> [!TIP]
> **AIとの協業について**
> このシステムについてAIと議論したり、機能追加の相談をする際は、必ず `SYSTEM_DESIGN.md` をコンテキストとして読み込ませてください。
> 設計思想や内部ロジックの理解度が格段に上がり、より正確な提案が可能になります。

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

## CLIダッシュボード（C++ TUI & Python CLI）

`system設計書2.md` の v2 指標（CP/TS/VP、カテゴリ分類、月間ランキング）に合わせたダッシュボードです。

> [!NOTE]
> 現在は TUI（`comm0ns_cpp_tui` およびラッパーコマンドの `c0top`）をメイン運用としています。
> 旧 `web` 実装は一旦撤去済みですが、将来的にアップデート版のWebダッシュボードを再実装する予定です。

### `c0top` コマンドの使い方（推奨）

コミュニティメンバーが自身のPCからダッシュボードを確認するためのコマンドです。事前に `.env` 等の設定は不要です。

1. **初回セットアップ**
   リポジトリをcloneして、C++ TUIをビルド・Pythonの依存関係をインストールします。
   ```bash
   git clone https://github.com/Comm0ns-llc/discord_bot.git
   cd discord_bot/comm0ns_cpp_tui
   cmake --build build -j4
   cd ..
   pip install -r requirements.txt
   ```

2. **コマンドの実行**
   ```bash
   tools/c0top
   ```
   初回起動時は自動的にブラウザが立ち上がり、DiscordでのOAuth認証（連携承認）が求められます。認証完了後、ターミナルに戻るとTUI画面が起動します（次回以降は認証スキップ可能）。

---

### Python CLI版ダッシュボード（開発・検証用）

TUIではなくログや特定のセクション出力を行いたい場合はPython版を利用できます。

### TUIのDiscordログイン（初回のみ）

`--tui` 起動時は Discord OAuth ログインを行います。

1. 未ログイン時はブラウザが自動で開き、Discord認証画面に遷移
2. 認証後、ブラウザに一瞬「認証成功。タブを閉じます...」と表示
3. TUIへ戻ってDBデータをロード
4. 次回以降は保存済みセッションを再利用（ブラウザは開かない）

必要な設定:
- Supabase Auth で `Discord` プロバイダを有効化
- Supabase Auth の Redirect URL に `http://127.0.0.1:53682/auth/callback` を追加
- `.env` に `SUPABASE_URL` と `SUPABASE_AUTH_KEY`（未設定なら `SUPABASE_KEY` を代用）

補助オプション:
- `--force-login`: 保存済みセッションを無視して再ログイン
- `--auth-timeout`: OAuth待機タイムアウト秒数
- `--skip-auth`: 認証をスキップ（ローカル検証用途）

TUIキー操作:
- `1-9` : ページ切替（Overview / MyStats / Leaderboard / Categories / Channels / Behavior / Graph / Governance / Operations）
- `Tab` / `←` / `→` : ページ移動
- `r` : 手動リフレッシュ
- `a` : 自動更新 ON/OFF
- `+` / `-` : 表示件数（limit）変更
- `[` / `]` : トレンド表示日数変更
- `u` : MyStatsの対象を自動TOPユーザーに戻す
- `q` : 終了

主なオプション:
- `--section` : `overview` / `mystats` / `leaderboard` / `categories` / `channels` / `behavior` / `graph` / `governance` / `operations` / `all`
- `--limit` : ランキング系の表示件数（デフォルト `10`）
- `--days` : overview の直近トレンド日数（デフォルト `14`）
- `--lookback-days` : DBスキャン対象の日数（デフォルト `90`）
- `--max-messages` : スキャンするメッセージ上限（デフォルト `50000`）
- `--max-reactions` : スキャンするリアクション上限（デフォルト `50000`）
- `--max-users` : モデル化するユーザー上限（デフォルト `5000`）
- `--timeout` : Supabaseリクエストのタイムアウト秒（デフォルト `20`）
- `--refresh` : TUI自動更新間隔（秒、デフォルト `15`）
- `--user` : MyStats対象ユーザー（`user_id` または `username`）
- `--tui` : インタラクティブTUIモードで起動

例:

```bash
# すべてのセクションを表示
python tools/dashboard_cli.py --section all --limit 20

# 特定ユーザーのMyStatsを表示
python tools/dashboard_cli.py --section mystats --user Tsukuru86

# TUIを10秒間隔で更新
python tools/dashboard_cli.py --tui --refresh 10

# 重い環境向け（短い期間だけ見る）
python tools/dashboard_cli.py --tui --lookback-days 30 --max-messages 15000 --max-reactions 15000
```

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

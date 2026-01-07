"""
Discord Bot Main Module
メインのBotクラスとイベントハンドラー
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from .config import config, validate_config, EmbedColors
from .database import db, DatabaseError
from .nlp_analyzer import nlp_analyzer
from .scoring import scoring_engine, MessageScoreInput

if TYPE_CHECKING:
    from discord import Message, RawReactionActionEvent

# ロギング設定
logging.basicConfig(
    level=logging.DEBUG if config.debug_mode else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class QualityBot(commands.Bot):
    """
    Discord Quality Scoring Bot
    
    メッセージの品質を評価し、ランキング化するBot
    """
    
    def __init__(self) -> None:
        """Botを初期化"""
        intents = discord.Intents.default()
        intents.message_content = True  # メッセージ内容を取得するために必要
        intents.reactions = True        # リアクションイベントを取得
        intents.members = True          # メンバー情報を取得
        
        super().__init__(
            command_prefix="!",  # スラッシュコマンドを主に使用
            intents=intents,
            application_id=config.discord.application_id or None
        )
        
        # 非同期タスクのキュー
        self._nlp_task_queue: asyncio.Queue[tuple[int, str, int]] = asyncio.Queue()
        self._nlp_worker_task: asyncio.Task | None = None
    
    async def setup_hook(self) -> None:
        """Bot起動時の初期化処理"""
        logger.info("Setting up bot...")
        
        # スラッシュコマンドを同期
        await self.tree.sync()
        logger.info("Slash commands synced")
        
        # NLP分析ワーカーを開始
        self._nlp_worker_task = asyncio.create_task(self._nlp_worker())
        logger.info("NLP worker started")
    
    async def on_ready(self) -> None:
        """Bot準備完了時のイベント"""
        if self.user:
            logger.info(f"Logged in as {self.user.name} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guild(s)")
        
        # ステータスを設定
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="コミュニティの品質 📊"
            )
        )
    
    async def _nlp_worker(self) -> None:
        """
        NLP分析をバックグラウンドで処理するワーカー
        
        メインスレッドをブロックしないように、
        NLP分析を別タスクで実行
        """
        logger.info("NLP worker started")
        
        while True:
            try:
                # キューからタスクを取得
                message_id, content, user_id = await self._nlp_task_queue.get()
                
                try:
                    # NLP分析を実行
                    multiplier = await nlp_analyzer.analyze(content)
                    logger.debug(f"NLP analysis completed: message={message_id}, multiplier={multiplier}")
                    
                    # データベースを更新
                    message = await db.update_message_nlp_score(message_id, multiplier)
                    
                    if message:
                        # スコア差分を計算してユーザースコアを更新
                        old_score = float(config.scoring.BASE_SCORE_PER_MESSAGE)  # 初期スコア
                        new_score = float(message["total_score"])
                        score_delta = new_score - old_score
                        
                        if score_delta != 0:
                            await db.update_user_score(user_id, score_delta)
                            logger.debug(f"User score updated: user={user_id}, delta={score_delta}")
                    
                except DatabaseError as e:
                    logger.error(f"Database error in NLP worker: {e}")
                except Exception as e:
                    logger.error(f"Error in NLP worker: {e}")
                finally:
                    self._nlp_task_queue.task_done()
                    
            except asyncio.CancelledError:
                logger.info("NLP worker cancelled")
                break
            except Exception as e:
                logger.error(f"Unexpected error in NLP worker: {e}")
                await asyncio.sleep(1)  # エラー時は少し待つ
    
    async def close(self) -> None:
        """Bot終了時のクリーンアップ"""
        logger.info("Shutting down bot...")
        
        # NLPワーカーを停止
        if self._nlp_worker_task:
            self._nlp_worker_task.cancel()
            try:
                await self._nlp_worker_task
            except asyncio.CancelledError:
                pass
        
        await super().close()


# Botインスタンスを作成
bot = QualityBot()


# ============================================
# Event Handlers
# ============================================

@bot.event
async def on_message(message: Message) -> None:
    """
    メッセージ受信時のイベントハンドラー
    
    1. Botのメッセージは無視
    2. ユーザー情報をupsert
    3. メッセージを保存（初期スコアで）
    4. NLP分析をキューに追加（バックグラウンド処理）
    5. リプライの場合は親メッセージのリプライカウントを更新
    """
    # Botのメッセージは無視
    if message.author.bot:
        return
    
    # DMは無視（サーバーのみ対象）
    if not message.guild:
        return
    
    try:
        # ユーザー情報をupsert
        await db.upsert_user(
            user_id=message.author.id,
            username=str(message.author)
        )
        
        # メッセージを保存（初期スコア）
        initial_multiplier = 1.0
        base_score = config.scoring.BASE_SCORE_PER_MESSAGE
        
        await db.insert_message(
            message_id=message.id,
            user_id=message.author.id,
            channel_id=message.channel.id,
            guild_id=message.guild.id,
            content=message.content,
            nlp_score_multiplier=initial_multiplier,
            base_score=base_score
        )
        
        # 初期スコアをユーザーに加算
        initial_score = base_score * initial_multiplier
        await db.update_user_score(message.author.id, initial_score)
        
        # NLP分析をキューに追加（バックグラウンドで処理）
        if message.content:  # 空のメッセージ（画像のみなど）は分析しない
            await bot._nlp_task_queue.put((
                message.id,
                message.content,
                message.author.id
            ))
        
        # リプライの場合、親メッセージのリプライカウントを更新
        if message.reference and message.reference.message_id:
            parent_message = await db.get_message(message.reference.message_id)
            if parent_message:
                updated_message = await db.increment_reply_count(message.reference.message_id)
                
                if updated_message:
                    # 親メッセージの投稿者のスコアを更新
                    reply_score = config.scoring.REPLY_SCORE_MULTIPLIER
                    await db.update_user_score(parent_message["user_id"], reply_score)
                    logger.debug(f"Reply count updated for message {message.reference.message_id}")
        
        logger.debug(f"Message processed: {message.id} from {message.author}")
        
    except DatabaseError as e:
        logger.error(f"Database error processing message: {e}")
    except Exception as e:
        logger.error(f"Error processing message: {e}")
    
    # コマンドの処理を継続
    await bot.process_commands(message)


@bot.event
async def on_raw_reaction_add(payload: RawReactionActionEvent) -> None:
    """
    リアクション追加時のイベントハンドラー
    
    1. Botのリアクションは無視
    2. 自分自身へのリアクションは無視
    3. リアクションを保存
    4. メッセージのリアクションスコアを更新
    5. メッセージ投稿者のスコアを更新
    """
    # Botのリアクションは無視
    if payload.member and payload.member.bot:
        return
    
    try:
        # メッセージを取得
        message = await db.get_message(payload.message_id)
        if not message:
            # DBにないメッセージ（Bot起動前のメッセージなど）は無視
            return
        
        # 自分自身へのリアクションは無視
        if message["user_id"] == payload.user_id:
            return
        
        # 絵文字の名前を取得
        emoji_name = str(payload.emoji.name) if payload.emoji.name else str(payload.emoji)
        
        # 既に同じリアクションが存在するかチェック
        exists = await db.check_reaction_exists(
            payload.message_id,
            payload.user_id,
            emoji_name
        )
        
        if exists:
            logger.debug(f"Reaction already exists: {emoji_name} on {payload.message_id}")
            return
        
        # リアクションの重みを計算
        weight = scoring_engine.calculate_reaction_weight(emoji_name)
        
        # リアクションを保存
        await db.insert_reaction(
            message_id=payload.message_id,
            user_id=payload.user_id,
            reaction_type=emoji_name,
            weight=weight
        )
        
        # メッセージのリアクションスコアを更新
        await db.update_message_reaction_score(payload.message_id, weight)
        
        # メッセージ投稿者のスコアを更新
        await db.update_user_score(message["user_id"], weight)
        
        logger.debug(f"Reaction processed: {emoji_name} on {payload.message_id}, weight={weight}")
        
    except DatabaseError as e:
        logger.error(f"Database error processing reaction: {e}")
    except Exception as e:
        logger.error(f"Error processing reaction: {e}")


# ============================================
# Slash Commands
# ============================================

@bot.tree.command(name="rank", description="自分のランキングとスコア内訳を表示")
async def rank_command(interaction: discord.Interaction) -> None:
    """
    /rank コマンド
    
    自分の順位とスコア内訳を表示
    """
    await interaction.response.defer(thinking=True)
    
    try:
        user_id = interaction.user.id
        
        # ユーザー情報を取得
        user = await db.get_user(user_id)
        if not user:
            embed = discord.Embed(
                title="❌ データが見つかりません",
                description="まだメッセージを送信していないようです。\nメッセージを送信するとスコアが記録されます！",
                color=EmbedColors.WARNING
            )
            await interaction.followup.send(embed=embed)
            return
        
        # 順位を取得
        rank_info = await db.get_user_rank(user_id)
        rank = rank_info[0] if rank_info else None
        total_users = rank_info[1] if rank_info else None
        
        # メッセージ統計を取得
        stats = await db.get_user_messages_stats(user_id)
        
        # スコア内訳を計算
        breakdown = scoring_engine.calculate_user_total_score(stats)
        
        # Embedを作成
        embed = discord.Embed(
            title=f"📊 {interaction.user.display_name} のスコア",
            color=EmbedColors.GOLD if rank and rank <= 3 else EmbedColors.INFO
        )
        
        # 順位
        if rank and total_users:
            medal = scoring_engine._get_rank_medal(rank)
            embed.add_field(
                name="🏆 順位",
                value=f"{medal} **{rank}位** / {total_users}人中",
                inline=False
            )
        
        # スコア内訳
        embed.add_field(
            name="📝 基本点 (発言数)",
            value=f"{breakdown.base_score:.1f}pt",
            inline=True
        )
        embed.add_field(
            name="🧠 NLP調整後",
            value=f"{breakdown.nlp_adjusted_score:.1f}pt",
            inline=True
        )
        embed.add_field(
            name="💬 会話誘発",
            value=f"{breakdown.conversation_score:.1f}pt",
            inline=True
        )
        embed.add_field(
            name="⭐ リアクション",
            value=f"{breakdown.impact_score:.1f}pt",
            inline=True
        )
        embed.add_field(
            name="📈 合計スコア",
            value=f"**{breakdown.total_score:.1f}pt**",
            inline=True
        )
        embed.add_field(
            name="📅 週間スコア",
            value=f"{float(user['weekly_score']):.1f}pt",
            inline=True
        )
        
        # 統計情報
        embed.add_field(
            name="📊 統計",
            value=f"総メッセージ数: {stats['total_messages']}",
            inline=False
        )
        
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text="💡 質の高い発言でスコアアップ！")
        
        await interaction.followup.send(embed=embed)
        
    except DatabaseError as e:
        logger.error(f"Database error in rank command: {e}")
        embed = discord.Embed(
            title="❌ エラー",
            description="データの取得中にエラーが発生しました。",
            color=EmbedColors.ERROR
        )
        await interaction.followup.send(embed=embed)
    except Exception as e:
        logger.error(f"Error in rank command: {e}")
        embed = discord.Embed(
            title="❌ エラー",
            description="予期しないエラーが発生しました。",
            color=EmbedColors.ERROR
        )
        await interaction.followup.send(embed=embed)


@bot.tree.command(name="leaderboard", description="上位10名のランキングを表示")
@app_commands.describe(weekly="週間ランキングを表示する場合はTrue")
async def leaderboard_command(
    interaction: discord.Interaction,
    weekly: bool = False
) -> None:
    """
    /leaderboard コマンド
    
    上位10名のランキングを表示
    """
    await interaction.response.defer(thinking=True)
    
    try:
        # リーダーボードを取得
        leaderboard = await db.get_leaderboard(limit=10, weekly=weekly)
        
        if not leaderboard:
            embed = discord.Embed(
                title="📊 リーダーボード",
                description="まだランキングデータがありません。\nメッセージを送信してスコアを獲得しましょう！",
                color=EmbedColors.WARNING
            )
            await interaction.followup.send(embed=embed)
            return
        
        # タイトル
        title = "🏆 週間ランキング TOP10" if weekly else "🏆 累計ランキング TOP10"
        
        # Embedを作成
        embed = discord.Embed(
            title=title,
            color=EmbedColors.GOLD
        )
        
        # ランキングエントリを構築
        entries: list[str] = []
        for entry in leaderboard:
            score = entry["weekly_score"] if weekly else entry["current_score"]
            line = scoring_engine.format_leaderboard_entry(
                rank=entry["rank"],
                username=entry["username"],
                score=score,
                weekly=weekly
            )
            entries.append(line)
        
        embed.description = "\n".join(entries)
        
        # 自分の順位を追加
        rank_info = await db.get_user_rank(interaction.user.id)
        if rank_info:
            rank, total = rank_info
            if rank > 10:
                embed.add_field(
                    name="📍 あなたの順位",
                    value=f"**{rank}位** / {total}人中",
                    inline=False
                )
        
        embed.set_footer(text="💡 /rank で自分の詳細スコアを確認できます")
        
        await interaction.followup.send(embed=embed)
        
    except DatabaseError as e:
        logger.error(f"Database error in leaderboard command: {e}")
        embed = discord.Embed(
            title="❌ エラー",
            description="データの取得中にエラーが発生しました。",
            color=EmbedColors.ERROR
        )
        await interaction.followup.send(embed=embed)
    except Exception as e:
        logger.error(f"Error in leaderboard command: {e}")
        embed = discord.Embed(
            title="❌ エラー",
            description="予期しないエラーが発生しました。",
            color=EmbedColors.ERROR
        )
        await interaction.followup.send(embed=embed)


# ============================================
# Main Entry Point
# ============================================

def main() -> None:
    """Botを起動"""
    # 設定を検証
    errors = validate_config()
    if errors:
        for error in errors:
            logger.error(f"Configuration error: {error}")
        raise SystemExit("Configuration validation failed")
    
    logger.info("Starting Discord Quality Bot...")
    bot.run(config.discord.bot_token)


if __name__ == "__main__":
    main()

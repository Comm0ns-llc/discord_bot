"""
Database Module - Supabase Integration
Supabaseとの接続およびデータ操作を行う非同期モジュール
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, TypedDict

from supabase import Client, create_client

from .config import config

logger = logging.getLogger(__name__)


# Type definitions for database records
class UserRecord(TypedDict):
    """ユーザーレコードの型定義"""
    user_id: int
    username: str
    current_score: float
    weekly_score: float
    created_at: str
    updated_at: str


class MessageRecord(TypedDict):
    """メッセージレコードの型定義"""
    message_id: int
    user_id: int
    channel_id: int
    guild_id: int
    content: str | None
    nlp_score_multiplier: float
    base_score: float
    reply_count: int
    reaction_score: float
    total_score: float
    timestamp: str
    created_at: str


class ReactionRecord(TypedDict):
    """リアクションレコードの型定義"""
    id: str
    message_id: int
    user_id: int
    reaction_type: str
    weight: float
    created_at: str


class LeaderboardEntry(TypedDict):
    """リーダーボードエントリの型定義"""
    user_id: int
    username: str
    current_score: float
    weekly_score: float
    rank: int


class Database:
    """
    Supabaseデータベース操作クラス
    
    非同期操作をサポートし、エラーハンドリングを適切に行う
    """
    
    def __init__(self) -> None:
        """データベースクライアントを初期化"""
        self._client: Client | None = None
        self._lock = asyncio.Lock()
    
    @property
    def client(self) -> Client:
        """Supabaseクライアントを取得（遅延初期化）"""
        if self._client is None:
            self._client = create_client(
                config.supabase.url,
                config.supabase.key
            )
        return self._client
    
    async def _execute_async(self, func: Any) -> Any:
        """
        同期関数を非同期で実行
        
        Supabase Python SDKは同期的なため、
        asyncio.to_threadを使用して非同期化
        """
        return await asyncio.to_thread(func)
    
    # ============================================
    # User Operations
    # ============================================
    
    async def upsert_user(
        self,
        user_id: int,
        username: str
    ) -> UserRecord | None:
        """
        ユーザーを作成または更新
        
        Args:
            user_id: Discord User ID
            username: Discord Username
            
        Returns:
            UserRecord | None: 作成/更新されたユーザーレコード
        """
        try:
            def _upsert() -> Any:
                return self.client.table("users").upsert({
                    "user_id": user_id,
                    "username": username
                }, on_conflict="user_id").execute()
            
            result = await self._execute_async(_upsert)
            
            if result.data:
                return result.data[0]
            return None
            
        except Exception as e:
            logger.error(f"Failed to upsert user {user_id}: {e}")
            raise DatabaseError(f"Failed to upsert user: {e}") from e
    
    async def get_user(self, user_id: int) -> UserRecord | None:
        """
        ユーザー情報を取得
        
        Args:
            user_id: Discord User ID
            
        Returns:
            UserRecord | None: ユーザーレコード
        """
        try:
            def _get() -> Any:
                return self.client.table("users").select("*").eq(
                    "user_id", user_id
                ).execute()
            
            result = await self._execute_async(_get)
            
            if result.data:
                return result.data[0]
            return None
            
        except Exception as e:
            logger.error(f"Failed to get user {user_id}: {e}")
            raise DatabaseError(f"Failed to get user: {e}") from e
    
    async def update_user_score(
        self,
        user_id: int,
        score_delta: float
    ) -> UserRecord | None:
        """
        ユーザースコアを更新（差分加算）
        
        Args:
            user_id: Discord User ID
            score_delta: 加算するスコア
            
        Returns:
            UserRecord | None: 更新後のユーザーレコード
        """
        try:
            # 現在のスコアを取得
            user = await self.get_user(user_id)
            if not user:
                logger.warning(f"User {user_id} not found for score update")
                return None
            
            new_current_score = float(user["current_score"]) + score_delta
            new_weekly_score = float(user["weekly_score"]) + score_delta
            
            def _update() -> Any:
                return self.client.table("users").update({
                    "current_score": new_current_score,
                    "weekly_score": new_weekly_score
                }).eq("user_id", user_id).execute()
            
            result = await self._execute_async(_update)
            
            if result.data:
                return result.data[0]
            return None
            
        except Exception as e:
            logger.error(f"Failed to update user score {user_id}: {e}")
            raise DatabaseError(f"Failed to update user score: {e}") from e
    
    async def get_user_rank(self, user_id: int) -> tuple[int, int] | None:
        """
        ユーザーの順位を取得
        
        Args:
            user_id: Discord User ID
            
        Returns:
            tuple[int, int] | None: (順位, 総ユーザー数) のタプル
        """
        try:
            def _get_all() -> Any:
                return self.client.table("users").select(
                    "user_id, current_score"
                ).order("current_score", desc=True).execute()
            
            result = await self._execute_async(_get_all)
            
            if not result.data:
                return None
            
            total_users = len(result.data)
            rank = 1
            
            for record in result.data:
                if record["user_id"] == user_id:
                    return (rank, total_users)
                rank += 1
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get user rank {user_id}: {e}")
            raise DatabaseError(f"Failed to get user rank: {e}") from e
    
    async def get_leaderboard(
        self,
        limit: int = 10,
        weekly: bool = False
    ) -> list[LeaderboardEntry]:
        """
        リーダーボードを取得
        
        Args:
            limit: 取得する件数
            weekly: 週間ランキングを取得するか
            
        Returns:
            list[LeaderboardEntry]: リーダーボードエントリのリスト
        """
        try:
            score_column = "weekly_score" if weekly else "current_score"
            
            def _get_leaderboard() -> Any:
                return self.client.table("users").select(
                    "user_id, username, current_score, weekly_score"
                ).order(score_column, desc=True).limit(limit).execute()
            
            result = await self._execute_async(_get_leaderboard)
            
            if not result.data:
                return []
            
            leaderboard: list[LeaderboardEntry] = []
            for idx, record in enumerate(result.data, start=1):
                leaderboard.append({
                    "user_id": record["user_id"],
                    "username": record["username"],
                    "current_score": float(record["current_score"]),
                    "weekly_score": float(record["weekly_score"]),
                    "rank": idx
                })
            
            return leaderboard
            
        except Exception as e:
            logger.error(f"Failed to get leaderboard: {e}")
            raise DatabaseError(f"Failed to get leaderboard: {e}") from e
    
    # ============================================
    # Message Operations
    # ============================================
    
    async def insert_message(
        self,
        message_id: int,
        user_id: int,
        channel_id: int,
        guild_id: int,
        content: str | None,
        nlp_score_multiplier: float = 1.0,
        base_score: float = 1.0
    ) -> MessageRecord | None:
        """
        メッセージを保存
        
        Args:
            message_id: Discord Message ID
            user_id: Discord User ID
            channel_id: Discord Channel ID
            guild_id: Discord Guild ID
            content: メッセージ内容
            nlp_score_multiplier: NLP分析による係数
            base_score: 基本スコア
            
        Returns:
            MessageRecord | None: 作成されたメッセージレコード
        """
        try:
            total_score = base_score * nlp_score_multiplier
            
            def _insert() -> Any:
                return self.client.table("messages").insert({
                    "message_id": message_id,
                    "user_id": user_id,
                    "channel_id": channel_id,
                    "guild_id": guild_id,
                    "content": content,
                    "nlp_score_multiplier": nlp_score_multiplier,
                    "base_score": base_score,
                    "total_score": total_score
                }).execute()
            
            result = await self._execute_async(_insert)
            
            if result.data:
                return result.data[0]
            return None
            
        except Exception as e:
            logger.error(f"Failed to insert message {message_id}: {e}")
            raise DatabaseError(f"Failed to insert message: {e}") from e
    
    async def get_message(self, message_id: int) -> MessageRecord | None:
        """
        メッセージを取得
        
        Args:
            message_id: Discord Message ID
            
        Returns:
            MessageRecord | None: メッセージレコード
        """
        try:
            def _get() -> Any:
                return self.client.table("messages").select("*").eq(
                    "message_id", message_id
                ).execute()
            
            result = await self._execute_async(_get)
            
            if result.data:
                return result.data[0]
            return None
            
        except Exception as e:
            logger.error(f"Failed to get message {message_id}: {e}")
            raise DatabaseError(f"Failed to get message: {e}") from e
    
    async def update_message_nlp_score(
        self,
        message_id: int,
        nlp_score_multiplier: float
    ) -> MessageRecord | None:
        """
        メッセージのNLPスコアを更新
        
        Args:
            message_id: Discord Message ID
            nlp_score_multiplier: NLP分析による係数
            
        Returns:
            MessageRecord | None: 更新されたメッセージレコード
        """
        try:
            message = await self.get_message(message_id)
            if not message:
                return None
            
            base_score = float(message["base_score"])
            reaction_score = float(message["reaction_score"])
            reply_count = int(message["reply_count"])
            
            # 合計スコアを再計算
            from .config import config as app_config
            total_score = (
                base_score * nlp_score_multiplier +
                reply_count * app_config.scoring.REPLY_SCORE_MULTIPLIER +
                reaction_score
            )
            
            def _update() -> Any:
                return self.client.table("messages").update({
                    "nlp_score_multiplier": nlp_score_multiplier,
                    "total_score": total_score
                }).eq("message_id", message_id).execute()
            
            result = await self._execute_async(_update)
            
            if result.data:
                return result.data[0]
            return None
            
        except Exception as e:
            logger.error(f"Failed to update message NLP score {message_id}: {e}")
            raise DatabaseError(f"Failed to update message NLP score: {e}") from e
    
    async def update_message_reaction_score(
        self,
        message_id: int,
        reaction_score_delta: float
    ) -> MessageRecord | None:
        """
        メッセージのリアクションスコアを更新
        
        Args:
            message_id: Discord Message ID
            reaction_score_delta: 加算するリアクションスコア
            
        Returns:
            MessageRecord | None: 更新されたメッセージレコード
        """
        try:
            message = await self.get_message(message_id)
            if not message:
                return None
            
            new_reaction_score = float(message["reaction_score"]) + reaction_score_delta
            base_score = float(message["base_score"])
            nlp_multiplier = float(message["nlp_score_multiplier"])
            reply_count = int(message["reply_count"])
            
            # 合計スコアを再計算
            from .config import config as app_config
            total_score = (
                base_score * nlp_multiplier +
                reply_count * app_config.scoring.REPLY_SCORE_MULTIPLIER +
                new_reaction_score
            )
            
            def _update() -> Any:
                return self.client.table("messages").update({
                    "reaction_score": new_reaction_score,
                    "total_score": total_score
                }).eq("message_id", message_id).execute()
            
            result = await self._execute_async(_update)
            
            if result.data:
                return result.data[0]
            return None
            
        except Exception as e:
            logger.error(f"Failed to update message reaction score {message_id}: {e}")
            raise DatabaseError(f"Failed to update message reaction score: {e}") from e
    
    async def increment_reply_count(
        self,
        message_id: int
    ) -> MessageRecord | None:
        """
        メッセージのリプライカウントをインクリメント
        
        Args:
            message_id: Discord Message ID
            
        Returns:
            MessageRecord | None: 更新されたメッセージレコード
        """
        try:
            message = await self.get_message(message_id)
            if not message:
                return None
            
            new_reply_count = int(message["reply_count"]) + 1
            base_score = float(message["base_score"])
            nlp_multiplier = float(message["nlp_score_multiplier"])
            reaction_score = float(message["reaction_score"])
            
            # 合計スコアを再計算
            from .config import config as app_config
            total_score = (
                base_score * nlp_multiplier +
                new_reply_count * app_config.scoring.REPLY_SCORE_MULTIPLIER +
                reaction_score
            )
            
            def _update() -> Any:
                return self.client.table("messages").update({
                    "reply_count": new_reply_count,
                    "total_score": total_score
                }).eq("message_id", message_id).execute()
            
            result = await self._execute_async(_update)
            
            if result.data:
                return result.data[0]
            return None
            
        except Exception as e:
            logger.error(f"Failed to increment reply count {message_id}: {e}")
            raise DatabaseError(f"Failed to increment reply count: {e}") from e
    
    async def get_user_messages_stats(
        self,
        user_id: int
    ) -> dict[str, Any]:
        """
        ユーザーのメッセージ統計を取得
        
        Args:
            user_id: Discord User ID
            
        Returns:
            dict: 統計情報
        """
        try:
            def _get_stats() -> Any:
                return self.client.table("messages").select(
                    "base_score, nlp_score_multiplier, reply_count, reaction_score, total_score"
                ).eq("user_id", user_id).execute()
            
            result = await self._execute_async(_get_stats)
            
            if not result.data:
                return {
                    "total_messages": 0,
                    "total_base_score": 0.0,
                    "total_nlp_adjusted_score": 0.0,
                    "total_reply_score": 0.0,
                    "total_reaction_score": 0.0,
                    "total_score": 0.0
                }
            
            from .config import config as app_config
            
            total_messages = len(result.data)
            total_base_score = sum(float(m["base_score"]) for m in result.data)
            total_nlp_adjusted_score = sum(
                float(m["base_score"]) * float(m["nlp_score_multiplier"])
                for m in result.data
            )
            total_reply_score = sum(
                int(m["reply_count"]) * app_config.scoring.REPLY_SCORE_MULTIPLIER
                for m in result.data
            )
            total_reaction_score = sum(float(m["reaction_score"]) for m in result.data)
            total_score = sum(float(m["total_score"]) for m in result.data)
            
            return {
                "total_messages": total_messages,
                "total_base_score": total_base_score,
                "total_nlp_adjusted_score": total_nlp_adjusted_score,
                "total_reply_score": total_reply_score,
                "total_reaction_score": total_reaction_score,
                "total_score": total_score
            }
            
        except Exception as e:
            logger.error(f"Failed to get user messages stats {user_id}: {e}")
            raise DatabaseError(f"Failed to get user messages stats: {e}") from e
    
    # ============================================
    # Reaction Operations
    # ============================================
    
    async def insert_reaction(
        self,
        message_id: int,
        user_id: int,
        reaction_type: str,
        weight: float
    ) -> ReactionRecord | None:
        """
        リアクションを保存
        
        Args:
            message_id: Discord Message ID
            user_id: リアクションしたユーザーのID
            reaction_type: 絵文字の名前またはUnicode
            weight: リアクションの重み
            
        Returns:
            ReactionRecord | None: 作成されたリアクションレコード
        """
        try:
            def _insert() -> Any:
                return self.client.table("reactions").upsert({
                    "message_id": message_id,
                    "user_id": user_id,
                    "reaction_type": reaction_type,
                    "weight": weight
                }, on_conflict="message_id,user_id,reaction_type").execute()
            
            result = await self._execute_async(_insert)
            
            if result.data:
                return result.data[0]
            return None
            
        except Exception as e:
            logger.error(f"Failed to insert reaction for message {message_id}: {e}")
            raise DatabaseError(f"Failed to insert reaction: {e}") from e
    
    async def check_reaction_exists(
        self,
        message_id: int,
        user_id: int,
        reaction_type: str
    ) -> bool:
        """
        リアクションが既に存在するかチェック
        
        Args:
            message_id: Discord Message ID
            user_id: リアクションしたユーザーのID
            reaction_type: 絵文字の名前またはUnicode
            
        Returns:
            bool: 存在する場合True
        """
        try:
            def _check() -> Any:
                return self.client.table("reactions").select("id").eq(
                    "message_id", message_id
                ).eq("user_id", user_id).eq("reaction_type", reaction_type).execute()
            
            result = await self._execute_async(_check)
            return bool(result.data)
            
        except Exception as e:
            logger.error(f"Failed to check reaction exists: {e}")
            return False


class DatabaseError(Exception):
    """データベース操作エラー"""
    pass


# Global database instance
db = Database()

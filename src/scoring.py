"""
Scoring Module
メッセージとユーザーのスコア計算ロジック
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import NamedTuple

from .config import config, SPECIAL_REACTION_EMOJIS

logger = logging.getLogger(__name__)


class ScoreBreakdown(NamedTuple):
    """スコア内訳を表す名前付きタプル"""
    base_score: float           # 基本点 (発言数 × 1)
    nlp_adjusted_score: float   # NLP調整後スコア (基本点 × multiplier)
    conversation_score: float   # 会話誘発スコア (リプライ数 × 5)
    impact_score: float         # リアクションスコア
    total_score: float          # 合計スコア


@dataclass
class MessageScoreInput:
    """メッセージスコア計算の入力データ"""
    base_score: float = 1.0
    nlp_multiplier: float = 1.0
    reply_count: int = 0
    reaction_score: float = 0.0


class ScoringEngine:
    """
    スコア計算エンジン
    
    4つの指標を組み合わせてスコアを算出:
    1. Active Score (基本点): 発言1つにつき1ポイント
    2. NLP Context Score: 基本点 × NLP multiplier
    3. Conversation Induction: リプライ数 × 5
    4. Impact Score: リアクションスコア
    """
    
    def __init__(self) -> None:
        """スコアリング設定を初期化"""
        self.weights = config.scoring
    
    def calculate_message_score(self, input_data: MessageScoreInput) -> ScoreBreakdown:
        """
        単一メッセージのスコアを計算
        
        Args:
            input_data: メッセージスコア計算の入力データ
            
        Returns:
            ScoreBreakdown: スコア内訳
        """
        # 1. Active Score (基本点)
        base_score = input_data.base_score
        
        # 2. NLP Context Score
        nlp_adjusted_score = base_score * input_data.nlp_multiplier
        
        # 3. Conversation Induction Score
        conversation_score = input_data.reply_count * self.weights.REPLY_SCORE_MULTIPLIER
        
        # 4. Impact Score (リアクション)
        impact_score = input_data.reaction_score
        
        # 合計スコア
        total_score = nlp_adjusted_score + conversation_score + impact_score
        
        return ScoreBreakdown(
            base_score=base_score,
            nlp_adjusted_score=nlp_adjusted_score,
            conversation_score=conversation_score,
            impact_score=impact_score,
            total_score=total_score
        )
    
    def calculate_reaction_weight(self, emoji: str) -> float:
        """
        リアクションの重みを計算
        
        特定の絵文字（🔥, 🚀, 👍）は高い重みを持つ
        
        Args:
            emoji: 絵文字の名前またはUnicode文字
            
        Returns:
            float: リアクションの重み
        """
        # 特別な絵文字かチェック
        if emoji in SPECIAL_REACTION_EMOJIS:
            return self.weights.REACTION_SPECIAL_WEIGHT
        
        # 通常のリアクション
        return self.weights.REACTION_BASE_WEIGHT
    
    def calculate_user_total_score(
        self,
        messages_stats: dict[str, float | int]
    ) -> ScoreBreakdown:
        """
        ユーザーの累計スコアを計算
        
        Args:
            messages_stats: メッセージ統計データ
                - total_messages: 総メッセージ数
                - total_base_score: 基本スコアの合計
                - total_nlp_adjusted_score: NLP調整後スコアの合計
                - total_reply_score: リプライスコアの合計
                - total_reaction_score: リアクションスコアの合計
                
        Returns:
            ScoreBreakdown: スコア内訳
        """
        base_score = float(messages_stats.get("total_base_score", 0))
        nlp_adjusted_score = float(messages_stats.get("total_nlp_adjusted_score", 0))
        conversation_score = float(messages_stats.get("total_reply_score", 0))
        impact_score = float(messages_stats.get("total_reaction_score", 0))
        
        total_score = nlp_adjusted_score + conversation_score + impact_score
        
        return ScoreBreakdown(
            base_score=base_score,
            nlp_adjusted_score=nlp_adjusted_score,
            conversation_score=conversation_score,
            impact_score=impact_score,
            total_score=total_score
        )
    
    def format_score_breakdown(
        self,
        breakdown: ScoreBreakdown,
        username: str,
        rank: int | None = None,
        total_users: int | None = None
    ) -> str:
        """
        スコア内訳を見やすい形式でフォーマット
        
        Args:
            breakdown: スコア内訳
            username: ユーザー名
            rank: 順位（オプション）
            total_users: 総ユーザー数（オプション）
            
        Returns:
            str: フォーマットされた文字列
        """
        lines = [f"📊 **{username}** のスコア詳細"]
        
        if rank is not None and total_users is not None:
            lines.append(f"🏆 順位: **{rank}位** / {total_users}人中")
        
        lines.extend([
            "",
            "**スコア内訳:**",
            f"├ 📝 基本点 (発言数): {breakdown.base_score:.1f}",
            f"├ 🧠 NLP調整後: {breakdown.nlp_adjusted_score:.1f}",
            f"├ 💬 会話誘発: {breakdown.conversation_score:.1f}",
            f"├ ⭐ リアクション: {breakdown.impact_score:.1f}",
            f"└ **合計: {breakdown.total_score:.1f}**"
        ])
        
        return "\n".join(lines)
    
    def format_leaderboard_entry(
        self,
        rank: int,
        username: str,
        score: float,
        weekly: bool = False
    ) -> str:
        """
        リーダーボードエントリをフォーマット
        
        Args:
            rank: 順位
            username: ユーザー名
            score: スコア
            weekly: 週間ランキングかどうか
            
        Returns:
            str: フォーマットされた文字列
        """
        # 順位に応じたメダル
        medal = self._get_rank_medal(rank)
        
        # 週間/累計の表示
        period = "週間" if weekly else "累計"
        
        return f"{medal} **{rank}.** {username} - {score:.1f}pt ({period})"
    
    def _get_rank_medal(self, rank: int) -> str:
        """
        順位に応じたメダル絵文字を取得
        
        Args:
            rank: 順位
            
        Returns:
            str: メダル絵文字
        """
        medals = {
            1: "🥇",
            2: "🥈",
            3: "🥉"
        }
        return medals.get(rank, "🏅")


# Global scoring engine instance
scoring_engine = ScoringEngine()


def calculate_score(
    base_score: float = 1.0,
    nlp_multiplier: float = 1.0,
    reply_count: int = 0,
    reaction_score: float = 0.0
) -> float:
    """
    スコアを計算するユーティリティ関数
    
    Args:
        base_score: 基本スコア（デフォルト: 1.0）
        nlp_multiplier: NLP係数（デフォルト: 1.0）
        reply_count: リプライ数（デフォルト: 0）
        reaction_score: リアクションスコア（デフォルト: 0.0）
        
    Returns:
        float: 合計スコア
    """
    input_data = MessageScoreInput(
        base_score=base_score,
        nlp_multiplier=nlp_multiplier,
        reply_count=reply_count,
        reaction_score=reaction_score
    )
    
    breakdown = scoring_engine.calculate_message_score(input_data)
    return breakdown.total_score

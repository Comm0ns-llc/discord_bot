"""
Discord Bot Configuration Module
スコアリングの重み付けや各種定数を一元管理
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Final

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass(frozen=True)
class DiscordConfig:
    """Discord関連の設定"""
    bot_token: str = field(default_factory=lambda: os.getenv("DISCORD_BOT_TOKEN", ""))
    application_id: str = field(default_factory=lambda: os.getenv("DISCORD_APPLICATION_ID", ""))


@dataclass(frozen=True)
class SupabaseConfig:
    """Supabase関連の設定"""
    url: str = field(default_factory=lambda: os.getenv("SUPABASE_URL", ""))
    key: str = field(default_factory=lambda: os.getenv("SUPABASE_KEY", ""))


@dataclass(frozen=True)
class OpenAIConfig:
    """OpenAI関連の設定"""
    api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))


@dataclass(frozen=True)
class ScoringWeights:
    """スコアリングの重み付け定数"""
    
    # Active Score (基本点)
    BASE_SCORE_PER_MESSAGE: float = 1.0
    
    # NLP Context Score Multipliers
    NLP_MULTIPLIER_SPAM: float = 0.1       # スパム/短文
    NLP_MULTIPLIER_NORMAL: float = 1.0     # 通常会話
    NLP_MULTIPLIER_HIGH_QUALITY: float = 1.5  # 高品質な発言
    NLP_MULTIPLIER_SHORT_TEXT: float = 0.5    # 30文字以下（API未使用時）
    
    # NLP Analysis Threshold
    NLP_MIN_CHAR_LENGTH: int = field(
        default_factory=lambda: int(os.getenv("NLP_MIN_CHAR_LENGTH", "30"))
    )
    
    # Conversation Induction Score
    REPLY_SCORE_MULTIPLIER: float = 5.0    # リプライ1件につき
    
    # Impact Score (リアクション)
    REACTION_BASE_WEIGHT: float = 2.0      # 通常リアクション
    REACTION_SPECIAL_WEIGHT: float = 5.0   # 特定の絵文字


# 特別なリアクション絵文字（高い重み付け）
SPECIAL_REACTION_EMOJIS: Final[frozenset[str]] = frozenset({
    "🔥",  # fire
    "🚀",  # rocket
    "👍",  # thumbs up
    "fire",
    "rocket",
    "thumbsup",
    "+1",
})


@dataclass(frozen=True)
class BotConfig:
    """Bot全体の設定"""
    discord: DiscordConfig = field(default_factory=DiscordConfig)
    supabase: SupabaseConfig = field(default_factory=SupabaseConfig)
    openai: OpenAIConfig = field(default_factory=OpenAIConfig)
    scoring: ScoringWeights = field(default_factory=ScoringWeights)
    debug_mode: bool = field(
        default_factory=lambda: os.getenv("DEBUG_MODE", "false").lower() == "true"
    )


# Global config instance
config = BotConfig()


def validate_config() -> list[str]:
    """
    設定値の検証を行い、エラーメッセージのリストを返す
    
    Returns:
        list[str]: エラーメッセージのリスト（空の場合は検証成功）
    """
    errors: list[str] = []
    
    if not config.discord.bot_token:
        errors.append("DISCORD_BOT_TOKEN is not set")
    
    if not config.supabase.url:
        errors.append("SUPABASE_URL is not set")
    
    if not config.supabase.key:
        errors.append("SUPABASE_KEY is not set")
    
    return errors


# NLP分析用のシステムプロンプト
NLP_SYSTEM_PROMPT: Final[str] = """あなたはDiscordコミュニティのメッセージ品質を評価するアナリストです。
与えられたメッセージを分析し、以下の基準で品質係数(multiplier)を決定してください。

評価基準:
- 0.1: スパム、意味のない短文（例: "あ", "w", "草", 絵文字のみ）
- 0.5: 短い返答、軽い挨拶（例: "おはよう", "了解", "OK"）
- 1.0: 通常の会話、一般的な質問や返答
- 1.2: 有益な情報を含む発言、建設的な意見
- 1.5: 技術的な貢献、詳細な説明、ポジティブな励まし、問題解決に貢献する発言

必ず数値のみ（0.1, 0.5, 1.0, 1.2, 1.5のいずれか）を返してください。"""


# Embed colors
class EmbedColors:
    """Discord Embedのカラー定数"""
    SUCCESS: int = 0x00FF00  # 緑
    ERROR: int = 0xFF0000    # 赤
    INFO: int = 0x0099FF     # 青
    WARNING: int = 0xFFFF00  # 黄
    GOLD: int = 0xFFD700     # 金（ランキング用）
    SILVER: int = 0xC0C0C0   # 銀
    BRONZE: int = 0xCD7F32   # 銅

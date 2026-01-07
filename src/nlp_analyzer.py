"""
NLP Analyzer Module - OpenAI Integration
OpenAI APIを使用してメッセージの品質を分析し、multiplierを返す
"""
from __future__ import annotations

import asyncio
import logging
from typing import Final

from openai import AsyncOpenAI, APIError, RateLimitError, APIConnectionError

from .config import config, NLP_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# 有効なmultiplier値
VALID_MULTIPLIERS: Final[frozenset[float]] = frozenset({0.1, 0.5, 1.0, 1.2, 1.5})

# デフォルト値
DEFAULT_MULTIPLIER: Final[float] = 1.0
SHORT_TEXT_MULTIPLIER: Final[float] = 0.5
ERROR_MULTIPLIER: Final[float] = 1.0  # エラー時はペナルティを与えない


class NLPAnalyzer:
    """
    OpenAI APIを使用したメッセージ品質分析クラス
    
    コスト削減のため、短いメッセージはAPIを呼び出さずに
    一律のmultiplierを返す
    """
    
    def __init__(self) -> None:
        """OpenAIクライアントを初期化"""
        self._client: AsyncOpenAI | None = None
        self._semaphore = asyncio.Semaphore(10)  # 同時リクエスト数を制限
    
    @property
    def client(self) -> AsyncOpenAI:
        """OpenAIクライアントを取得（遅延初期化）"""
        if self._client is None:
            self._client = AsyncOpenAI(api_key=config.openai.api_key)
        return self._client
    
    def _is_short_text(self, text: str) -> bool:
        """
        テキストが短すぎるかどうかを判定
        
        Args:
            text: 分析対象のテキスト
            
        Returns:
            bool: 設定された最小文字数以下の場合True
        """
        # 空白を除いた実質的な文字数でカウント
        cleaned_text = text.strip()
        return len(cleaned_text) <= config.scoring.NLP_MIN_CHAR_LENGTH
    
    def _is_spam_pattern(self, text: str) -> bool:
        """
        明らかなスパムパターンをローカルで検出
        
        Args:
            text: 分析対象のテキスト
            
        Returns:
            bool: スパムパターンの場合True
        """
        cleaned = text.strip().lower()
        
        # 空のテキスト
        if not cleaned:
            return True
        
        # 1-2文字のみ
        if len(cleaned) <= 2:
            return True
        
        # よくあるスパムパターン
        spam_patterns = {
            "w", "ww", "www", "wwww", "wwwww",
            "草", "草草", "草草草",
            "あ", "ああ", "あああ",
            "え", "ええ", "えええ",
            "お", "おお", "おおお",
            "う", "うう", "うーん",
            "笑", "笑笑",
        }
        
        if cleaned in spam_patterns:
            return True
        
        # 同じ文字の繰り返しのみ（例: "wwwwwwww"）
        if len(set(cleaned)) == 1 and len(cleaned) > 2:
            return True
        
        # 絵文字のみかどうかをチェック（簡易版）
        # Unicode絵文字の範囲をチェック
        non_emoji_chars = [c for c in cleaned if not self._is_emoji(c)]
        if not non_emoji_chars:
            return True
        
        return False
    
    def _is_emoji(self, char: str) -> bool:
        """
        文字が絵文字かどうかを判定（簡易版）
        
        Args:
            char: 判定する文字
            
        Returns:
            bool: 絵文字の場合True
        """
        code_point = ord(char)
        emoji_ranges = [
            (0x1F600, 0x1F64F),  # Emoticons
            (0x1F300, 0x1F5FF),  # Misc Symbols and Pictographs
            (0x1F680, 0x1F6FF),  # Transport and Map
            (0x1F1E0, 0x1F1FF),  # Flags
            (0x2600, 0x26FF),    # Misc symbols
            (0x2700, 0x27BF),    # Dingbats
            (0xFE00, 0xFE0F),    # Variation Selectors
            (0x1F900, 0x1F9FF),  # Supplemental Symbols and Pictographs
            (0x1FA00, 0x1FA6F),  # Chess Symbols
            (0x1FA70, 0x1FAFF),  # Symbols and Pictographs Extended-A
        ]
        
        for start, end in emoji_ranges:
            if start <= code_point <= end:
                return True
        return False
    
    def _parse_multiplier(self, response: str) -> float:
        """
        APIレスポンスからmultiplierを抽出
        
        Args:
            response: APIからのレスポンステキスト
            
        Returns:
            float: 有効なmultiplier値
        """
        try:
            # 数値部分を抽出
            cleaned = response.strip()
            
            # 数値として解析を試みる
            value = float(cleaned)
            
            # 有効な値かチェック
            if value in VALID_MULTIPLIERS:
                return value
            
            # 最も近い有効な値を返す
            return min(VALID_MULTIPLIERS, key=lambda x: abs(x - value))
            
        except ValueError:
            logger.warning(f"Failed to parse multiplier from response: {response}")
            return DEFAULT_MULTIPLIER
    
    async def analyze(self, text: str) -> float:
        """
        テキストを分析してmultiplierを返す
        
        コスト削減のため:
        1. 30文字以下の発言は一律0.5
        2. 明らかなスパムパターンは一律0.1
        3. それ以外はOpenAI APIで分析
        
        Args:
            text: 分析対象のテキスト
            
        Returns:
            float: multiplier値 (0.1 ~ 1.5)
        """
        # 空のテキスト
        if not text or not text.strip():
            return config.scoring.NLP_MULTIPLIER_SPAM
        
        # 明らかなスパムパターン
        if self._is_spam_pattern(text):
            logger.debug(f"Spam pattern detected: {text[:20]}...")
            return config.scoring.NLP_MULTIPLIER_SPAM
        
        # 短いテキスト（APIコスト削減）
        if self._is_short_text(text):
            logger.debug(f"Short text, skipping API: {text[:20]}...")
            return SHORT_TEXT_MULTIPLIER
        
        # OpenAI APIで分析
        return await self._analyze_with_api(text)
    
    async def _analyze_with_api(self, text: str) -> float:
        """
        OpenAI APIを使用してテキストを分析
        
        Args:
            text: 分析対象のテキスト
            
        Returns:
            float: multiplier値
        """
        async with self._semaphore:  # 同時リクエスト数を制限
            try:
                response = await self.client.chat.completions.create(
                    model=config.openai.model,
                    messages=[
                        {"role": "system", "content": NLP_SYSTEM_PROMPT},
                        {"role": "user", "content": text}
                    ],
                    max_tokens=10,  # 数値のみなので少なくてOK
                    temperature=0.3,  # 一貫性を重視
                )
                
                if response.choices and response.choices[0].message.content:
                    result = self._parse_multiplier(response.choices[0].message.content)
                    logger.debug(f"NLP analysis result: {result} for text: {text[:30]}...")
                    return result
                
                logger.warning("Empty response from OpenAI API")
                return DEFAULT_MULTIPLIER
                
            except RateLimitError as e:
                logger.warning(f"OpenAI rate limit exceeded: {e}")
                # レート制限時は少し待ってリトライせず、デフォルト値を返す
                return ERROR_MULTIPLIER
                
            except APIConnectionError as e:
                logger.error(f"OpenAI connection error: {e}")
                return ERROR_MULTIPLIER
                
            except APIError as e:
                logger.error(f"OpenAI API error: {e}")
                return ERROR_MULTIPLIER
                
            except Exception as e:
                logger.error(f"Unexpected error during NLP analysis: {e}")
                return ERROR_MULTIPLIER
    
    async def analyze_batch(self, texts: list[str]) -> list[float]:
        """
        複数のテキストを並列で分析
        
        Args:
            texts: 分析対象のテキストリスト
            
        Returns:
            list[float]: multiplier値のリスト
        """
        tasks = [self.analyze(text) for text in texts]
        return await asyncio.gather(*tasks)


class NLPAnalyzerError(Exception):
    """NLP分析エラー"""
    pass


# Global analyzer instance
nlp_analyzer = NLPAnalyzer()

"""
Discord Quality Scoring Bot
"""
from .bot import bot, main
from .config import config
from .database import db
from .nlp_analyzer import nlp_analyzer
from .scoring import scoring_engine, calculate_score

__version__ = "1.0.0"
__all__ = [
    "bot",
    "main",
    "config",
    "db",
    "nlp_analyzer",
    "scoring_engine",
    "calculate_score",
]

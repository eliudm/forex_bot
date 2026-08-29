# =============================================================================
# agents/sentiment_agent.py — "A third bot analyzes news and sentiment"
# =============================================================================
# HONEST STATUS: no news/sentiment data source is wired in. This ships as a
# working interface with a null provider that reports zero confidence —
# not a fabricated sentiment score. The coordinator weights agents by their
# own confidence, so a confidence=0.0 signal never dilutes the real (AI
# model) signal; it's a true no-op until you plug in a real provider.
#
# TO WIRE IN A REAL PROVIDER:
#   Implement a class with the same analyze(symbol) -> AgentSignal interface
#   (e.g. hitting a news API and running keyword/NLP scoring), set
#   SENTIMENT_PROVIDER in .env to a dotted path to it, and it'll be used
#   automatically — see _load_provider() below.
# =============================================================================

import os
import importlib
import logging

from agents.base import AgentSignal, neutral_signal

logger = logging.getLogger(__name__)


class NullSentimentProvider:
    """Default provider: always reports 'no data', never fabricates a score."""

    def analyze(self, symbol: str) -> AgentSignal:
        return neutral_signal("sentiment", f"{symbol}: no sentiment provider configured")


def _load_provider():
    path = os.environ.get("SENTIMENT_PROVIDER", "").strip()
    if not path:
        return NullSentimentProvider()
    try:
        module_name, class_name = path.rsplit(".", 1)
        cls = getattr(importlib.import_module(module_name), class_name)
        logger.info(f"Loaded sentiment provider: {path}")
        return cls()
    except Exception as e:
        logger.warning(f"Could not load SENTIMENT_PROVIDER={path} ({e}); using NullSentimentProvider.")
        return NullSentimentProvider()


class SentimentAgent:
    def __init__(self):
        self.provider = _load_provider()

    def analyze(self, symbol: str) -> AgentSignal:
        try:
            return self.provider.analyze(symbol)
        except Exception as e:
            logger.warning(f"Sentiment provider failed for {symbol}: {e}")
            return neutral_signal("sentiment", f"{symbol}: sentiment provider error, ignored")

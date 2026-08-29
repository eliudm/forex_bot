# =============================================================================
# agents/onchain_agent.py — "Tracks whales and on-chain activity"
# =============================================================================
# HONEST STATUS: same situation as sentiment_agent.py — no on-chain/whale
# data source is wired in, so this ships as a working interface with a null
# provider (confidence=0.0, true no-op) rather than invented whale numbers.
# Only relevant to crypto symbols; forex/synthetic/commodity symbols never
# call this at all (see agents/coordinator.py).
#
# TO WIRE IN A REAL PROVIDER: same pattern as sentiment_agent.py — implement
# analyze(symbol) -> AgentSignal, set ONCHAIN_PROVIDER in .env to its dotted
# path (e.g. hitting Etherscan/Whale Alert and scoring large-transfer flow).
# =============================================================================

import os
import importlib
import logging

from agents.base import AgentSignal, neutral_signal

logger = logging.getLogger(__name__)

CRYPTO_MARKERS = ("BTC", "ETH")


def is_crypto(symbol: str) -> bool:
    return any(marker in symbol.upper() for marker in CRYPTO_MARKERS)


class NullOnChainProvider:
    def analyze(self, symbol: str) -> AgentSignal:
        return neutral_signal("onchain", f"{symbol}: no on-chain data provider configured")


def _load_provider():
    path = os.environ.get("ONCHAIN_PROVIDER", "").strip()
    if not path:
        return NullOnChainProvider()
    try:
        module_name, class_name = path.rsplit(".", 1)
        cls = getattr(importlib.import_module(module_name), class_name)
        logger.info(f"Loaded on-chain provider: {path}")
        return cls()
    except Exception as e:
        logger.warning(f"Could not load ONCHAIN_PROVIDER={path} ({e}); using NullOnChainProvider.")
        return NullOnChainProvider()


class OnChainAgent:
    def __init__(self):
        self.provider = _load_provider()

    def analyze(self, symbol: str) -> AgentSignal:
        if not is_crypto(symbol):
            return neutral_signal("onchain", f"{symbol}: not a crypto symbol, on-chain data not applicable")
        try:
            return self.provider.analyze(symbol)
        except Exception as e:
            logger.warning(f"On-chain provider failed for {symbol}: {e}")
            return neutral_signal("onchain", f"{symbol}: on-chain provider error, ignored")

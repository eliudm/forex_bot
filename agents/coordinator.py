# =============================================================================
# agents/coordinator.py — "The HEAD BOSS coordinates everything"
# =============================================================================
# Combines the scanner, setup (AI model), sentiment, and on-chain agents
# into one trade decision. Risk management is deliberately NOT reimplemented
# here — config/settings.py + ai_engine/risk_manager.py + ai_engine/
# loss_detector.py already do that job, are already wired into main.py's
# trade-execution path, and are already covered by tests. This coordinator
# only decides direction/confidence; main.py still runs the existing risk
# checks before anything is actually traded.
#
# HOW SENTIMENT/ON-CHAIN COMBINE WITH THE MODEL:
#   Each agent's influence is proportional to its own confidence. The
#   sentiment/on-chain agents default to confidence=0.0 (no data source
#   configured — see agents/sentiment_agent.py, agents/onchain_agent.py),
#   which makes their contribution exactly zero: the coordinator's output
#   is then identical to the setup agent's (the AI model's) own signal.
#   Wire in a real provider and it starts actually shifting confidence —
#   nudging it up when an agent agrees with the model's direction, down
#   (potentially below the trade threshold, flipping the action to WAIT)
#   when it disagrees.
# =============================================================================

import logging

from agents.scanner_agent import MarketScannerAgent
from agents.setup_agent import SetupAgent
from agents.sentiment_agent import SentimentAgent
from agents.onchain_agent import OnChainAgent

logger = logging.getLogger(__name__)

SENTIMENT_WEIGHT = 0.15
ONCHAIN_WEIGHT = 0.15


class TradeCoordinator:
    def __init__(self):
        self.scanner = MarketScannerAgent()
        self.setup = SetupAgent()
        self.sentiment = SentimentAgent()
        self.onchain = OnChainAgent()

    def decide(self, symbol: str, df, ai_engine, min_confidence: float) -> dict:
        """
        Returns {"signal": <the same shape ai_engine.predict() already
        returns, i.e. action/confidence/sl/tp/strategy/regime/...>,
        "agents": {name: AgentSignal, ...}} so main.py can execute exactly
        as before, plus optionally log/alert on the breakdown.
        """
        scan = self.scanner.scan(symbol, df)
        if not scan.meta.get("interesting", True):
            return {
                "signal": {"action": "WAIT", "confidence": 0.0, "reason": scan.reason, "regime": "QUIET"},
                "agents": {"scanner": scan},
            }

        setup = self.setup.analyze(ai_engine, df, min_confidence)
        signal = dict(setup.meta)  # copy — safe to mutate without touching the AI engine's own return value

        if signal.get("action") == "WAIT":
            return {"signal": signal, "agents": {"scanner": scan, "setup": setup}}

        direction = 1 if signal["action"] == "BUY" else -1
        sentiment = self.sentiment.analyze(symbol)
        onchain = self.onchain.analyze(symbol)

        adjustment = (
            direction * sentiment.score * sentiment.confidence * SENTIMENT_WEIGHT +
            direction * onchain.score * onchain.confidence * ONCHAIN_WEIGHT
        )
        final_confidence = max(0.0, min(1.0, signal["confidence"] + adjustment))
        signal["confidence"] = round(final_confidence, 4)
        signal["agent_adjustment"] = round(adjustment, 4)

        if final_confidence < min_confidence:
            original_action = signal["action"]
            signal["action"] = "WAIT"
            signal["reason"] = (
                f"Setup agent wanted {original_action} but combined confidence "
                f"{final_confidence:.0%} fell below the {min_confidence:.0%} threshold "
                f"after sentiment/on-chain adjustment"
            )

        return {
            "signal": signal,
            "agents": {"scanner": scan, "setup": setup, "sentiment": sentiment, "onchain": onchain},
        }


def format_breakdown(agents: dict) -> str:
    """One-line human-readable summary of what each agent contributed, for logs/Telegram."""
    parts = []
    for name, sig in agents.items():
        if sig.confidence > 0:
            parts.append(f"{name}={sig.score:+.2f}@{sig.confidence:.0%}")
        else:
            parts.append(f"{name}=no-data")
    return " | ".join(parts)

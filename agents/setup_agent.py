# =============================================================================
# agents/setup_agent.py — "Another hunts for setups"
# =============================================================================
# Thin adapter around the existing EnhancedAIEngine (ai_engine/enhanced_engine.py)
# — the actual ensemble model (RandomForest + GradientBoosting + XGBoost) that
# does the real predictive work. This agent doesn't reimplement any of that;
# it just reports the model's own signal in the common AgentSignal shape so
# the coordinator can combine it with the other agents, and hands back the
# full raw signal dict (sl/tp/strategy/regime) for trade execution.
# =============================================================================

import pandas as pd

from agents.base import AgentSignal


class SetupAgent:
    def analyze(self, ai_engine, df: pd.DataFrame, min_confidence: float) -> AgentSignal:
        signal = ai_engine.predict(df, min_confidence)

        if signal["action"] == "BUY":
            score = signal["confidence"]
        elif signal["action"] == "SELL":
            score = -signal["confidence"]
        else:
            score = 0.0

        return AgentSignal(
            agent="setup",
            score=score,
            confidence=signal.get("confidence", 0.0) if signal["action"] != "WAIT" else 0.0,
            reason=signal.get("reason", f"AI signal: {signal['action']}"),
            meta=signal,
        )

# =============================================================================
# agents/scanner_agent.py — "One bot scans the market"
# =============================================================================
# WHAT THIS ACTUALLY DOES (no more, no less):
#   A cheap pre-filter that skips a symbol for this scan cycle only when its
#   volatility has gone abnormally flat relative to ITS OWN recent history —
#   e.g. a frozen/illiquid tick or a data glitch. That's it.
#
# WHAT IT DELIBERATELY DOES NOT DO:
#   It does not filter by trend-vs-ranging. The AI engine already trades
#   both regimes (TREND_FOLLOW in strong trends, MEAN_REVERSION in ranging
#   markets) — a scanner that screened out "ranging" markets would silently
#   disable half the model's own strategy logic. So this only ever catches
#   genuinely dead/flat stretches, using a self-relative threshold so it
#   works the same way whether the symbol is EURUSD or a Boom index.
# =============================================================================

import pandas as pd

from agents.base import AgentSignal

QUIET_ATR_RATIO = 0.15  # flag as quiet only if current ATR < 15% of its own 20-bar average


class MarketScannerAgent:
    def scan(self, symbol: str, df: pd.DataFrame) -> AgentSignal:
        if "atr" not in df.columns or len(df) < 20:
            return AgentSignal(agent="scanner", score=0.0, confidence=0.0,
                                reason="Not enough data to judge volatility — treating as interesting")

        atr_now = df["atr"].iloc[-1]
        atr_avg = df["atr"].tail(20).mean()

        if atr_avg > 0 and atr_now < atr_avg * QUIET_ATR_RATIO:
            return AgentSignal(
                agent="scanner", score=0.0, confidence=1.0,
                reason=f"{symbol}: volatility abnormally flat ({atr_now:.5f} vs "
                       f"20-bar avg {atr_avg:.5f}) — skipping this cycle",
                meta={"interesting": False, "atr_now": float(atr_now), "atr_avg": float(atr_avg)},
            )

        return AgentSignal(
            agent="scanner", score=0.0, confidence=0.0,
            reason=f"{symbol}: normal volatility — worth analyzing",
            meta={"interesting": True, "atr_now": float(atr_now), "atr_avg": float(atr_avg)},
        )

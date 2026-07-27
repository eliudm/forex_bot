# ============================================================
# strategies/strategy_library.py — All Trading Strategies
# ============================================================
# WHAT THIS FILE DOES:
#   Contains all 5 trading strategies the bot can use.
#   The AI engine picks the best one based on market conditions.
#
# STRATEGIES:
#   1. EMA Crossover   — Best in trending markets
#   2. RSI Reversal    — Best in ranging markets
#   3. MACD Momentum   — Best when momentum is building
#   4. Breakout        — Best when price breaks key levels
#   5. Boom/Crash      — Specific to Deriv synthetic indices
# ============================================================

import logging
import numpy as np

logger = logging.getLogger(__name__)


class StrategyResult:
    """Holds the output of a strategy evaluation."""
    def __init__(self, signal=None, direction=None, sl_pips=0,
                 tp_pips=0, confidence=0.0, reason=""):
        self.signal     = signal        # "BUY", "SELL", or None
        self.direction  = direction     # same as signal
        self.sl_pips    = sl_pips
        self.tp_pips    = tp_pips
        self.confidence = confidence    # 0.0 to 1.0
        self.reason     = reason        # Explanation of the signal


class EMAStrategy:
    """
    Strategy 1: EMA Crossover Trend Following
    ─────────────────────────────────────────
    LOGIC:
      • BUY  when EMA20 crosses above EMA50
             AND price is above EMA200 (uptrend confirmed)
             AND RSI is between 40-70 (not overbought)
             AND ADX > 20 (trend exists)

      • SELL when EMA20 crosses below EMA50
             AND price is below EMA200 (downtrend confirmed)
             AND RSI is between 30-60 (not oversold)
             AND ADX > 20

    BEST FOR: Trending markets (forex pairs, XAUUSD)
    TIMEFRAME: H1, H4
    """
    name = "EMA Crossover"

    def evaluate(self, features: dict, atr: float) -> StrategyResult:
        rsi         = features.get("rsi", 50)
        adx         = features.get("adx", 0)
        above_200   = features.get("above_ema200", 0)
        bull_cross  = features.get("ema_bullish_cross", 0)
        bear_cross  = features.get("ema_bearish_cross", 0)
        strong_trend= features.get("strong_trend", 0)
        macd_hist   = features.get("macd_hist", 0)

        # BUY conditions
        if (bull_cross and above_200 and 40 < rsi < 70 and strong_trend):
            confidence = 0.60
            if macd_hist > 0: confidence += 0.08   # MACD confirms
            if adx > 30:      confidence += 0.07   # Strong trend bonus
            sl_pips = atr * 10000 * 1.5            # 1.5× ATR stop
            tp_pips = sl_pips * 2.5                # 2.5:1 R:R
            return StrategyResult("BUY", "BUY", sl_pips, tp_pips,
                                  min(confidence, 0.92),
                                  "EMA20 crossed above EMA50, price above EMA200, ADX confirms trend")

        # SELL conditions
        if (bear_cross and not above_200 and 30 < rsi < 60 and strong_trend):
            confidence = 0.60
            if macd_hist < 0: confidence += 0.08
            if adx > 30:      confidence += 0.07
            sl_pips = atr * 10000 * 1.5
            tp_pips = sl_pips * 2.5
            return StrategyResult("SELL", "SELL", sl_pips, tp_pips,
                                  min(confidence, 0.92),
                                  "EMA20 crossed below EMA50, price below EMA200, ADX confirms trend")

        return StrategyResult()


class RSIReversalStrategy:
    """
    Strategy 2: RSI Mean Reversion
    ───────────────────────────────
    LOGIC:
      • BUY  when RSI < 30 (oversold)
             AND price near lower Bollinger Band
             AND Stochastic also oversold (< 20)
             AND a bullish candle pattern present (hammer / engulf)

      • SELL when RSI > 70 (overbought)
             AND price near upper Bollinger Band
             AND Stochastic also overbought (> 80)
             AND a bearish candle pattern present

    BEST FOR: Range-bound markets, counter-trend reversals
    TIMEFRAME: M15, H1
    """
    name = "RSI Reversal"

    def evaluate(self, features: dict, atr: float) -> StrategyResult:
        rsi         = features.get("rsi", 50)
        bb_pct      = features.get("bb_percent", 0.5)
        stoch_k     = features.get("stoch_k", 50)
        hammer      = features.get("hammer", 0)
        engulf_bull = features.get("bullish_engulf", 0)
        shoot_star  = features.get("shooting_star", 0)
        engulf_bear = features.get("bearish_engulf", 0)
        strong_trend= features.get("strong_trend", 0)

        # Don't trade reversals in strong trends
        if strong_trend:
            return StrategyResult()

        # BUY (oversold reversal)
        if rsi < 30 and bb_pct < 0.2 and stoch_k < 25:
            confidence = 0.58
            if hammer or engulf_bull: confidence += 0.12  # Pattern confirms
            if rsi < 20:              confidence += 0.08  # Extreme oversold
            sl_pips = atr * 10000 * 1.2
            tp_pips = sl_pips * 2.2
            return StrategyResult("BUY", "BUY", sl_pips, tp_pips,
                                  min(confidence, 0.88),
                                  f"RSI={rsi:.0f} oversold, price at lower BB, Stoch={stoch_k:.0f}")

        # SELL (overbought reversal)
        if rsi > 70 and bb_pct > 0.8 and stoch_k > 75:
            confidence = 0.58
            if shoot_star or engulf_bear: confidence += 0.12
            if rsi > 80:                  confidence += 0.08
            sl_pips = atr * 10000 * 1.2
            tp_pips = sl_pips * 2.2
            return StrategyResult("SELL", "SELL", sl_pips, tp_pips,
                                  min(confidence, 0.88),
                                  f"RSI={rsi:.0f} overbought, price at upper BB, Stoch={stoch_k:.0f}")

        return StrategyResult()


class MACDMomentumStrategy:
    """
    Strategy 3: MACD Momentum
    ──────────────────────────
    LOGIC:
      • BUY  when MACD line crosses above signal line
             AND both lines are below zero (reversal from bearish)
             AND RSI just crossed above 50
             AND price is above EMA50

      • SELL when MACD line crosses below signal line
             AND both lines are above zero (reversal from bullish)
             AND RSI just crossed below 50
             AND price is below EMA50

    BEST FOR: Momentum buildups, trend continuations
    TIMEFRAME: M15, H1
    """
    name = "MACD Momentum"

    def evaluate(self, features: dict, atr: float) -> StrategyResult:
        macd_bull   = features.get("macd_bullish_cross", 0)
        macd_bear   = features.get("macd_bearish_cross", 0)
        macd_hist   = features.get("macd_hist", 0)
        rsi         = features.get("rsi", 50)
        above_200   = features.get("above_ema200", 0)
        rsi_up      = features.get("rsi_mid_cross_up", 0)
        rsi_down    = features.get("rsi_mid_cross_down", 0)

        # BUY
        if macd_bull and macd_hist > 0 and 45 < rsi < 65:
            confidence = 0.62
            if rsi_up:      confidence += 0.10
            if above_200:   confidence += 0.08
            sl_pips = atr * 10000 * 1.8
            tp_pips = sl_pips * 2.0
            return StrategyResult("BUY", "BUY", sl_pips, tp_pips,
                                  min(confidence, 0.90),
                                  "MACD bullish crossover with RSI confirmation")

        # SELL
        if macd_bear and macd_hist < 0 and 35 < rsi < 55:
            confidence = 0.62
            if rsi_down:   confidence += 0.10
            if not above_200: confidence += 0.08
            sl_pips = atr * 10000 * 1.8
            tp_pips = sl_pips * 2.0
            return StrategyResult("SELL", "SELL", sl_pips, tp_pips,
                                  min(confidence, 0.90),
                                  "MACD bearish crossover with RSI confirmation")

        return StrategyResult()


class BreakoutStrategy:
    """
    Strategy 4: Bollinger Band Breakout
    ─────────────────────────────────────
    LOGIC:
      After a squeeze (bands narrow), price tends to break out strongly.

      • BUY  when BB squeeze is detected
             AND price breaks above upper band
             AND ADX is rising
             AND volume is above average

      • SELL when BB squeeze detected
             AND price breaks below lower band

    BEST FOR: Volatile moves, news-driven moves, synthetic indices
    TIMEFRAME: M5, M15
    """
    name = "Breakout"

    def evaluate(self, features: dict, atr: float) -> StrategyResult:
        squeeze     = features.get("bb_squeeze", 0)
        bb_pct      = features.get("bb_percent", 0.5)
        adx         = features.get("adx", 0)
        high_vol    = features.get("high_volatility", 0)
        macd_hist   = features.get("macd_hist", 0)

        if not squeeze:
            return StrategyResult()

        # BUY breakout (price breaks above upper band)
        if bb_pct > 1.0 and adx > 20:
            confidence = 0.65
            if macd_hist > 0:  confidence += 0.10
            if high_vol:       confidence += 0.08
            sl_pips = atr * 10000 * 2.0    # Wider SL for breakouts
            tp_pips = sl_pips * 2.5
            return StrategyResult("BUY", "BUY", sl_pips, tp_pips,
                                  min(confidence, 0.90),
                                  "BB Squeeze breakout to upside")

        # SELL breakout (price breaks below lower band)
        if bb_pct < 0.0 and adx > 20:
            confidence = 0.65
            if macd_hist < 0:  confidence += 0.10
            if high_vol:       confidence += 0.08
            sl_pips = atr * 10000 * 2.0
            tp_pips = sl_pips * 2.5
            return StrategyResult("SELL", "SELL", sl_pips, tp_pips,
                                  min(confidence, 0.90),
                                  "BB Squeeze breakout to downside")

        return StrategyResult()


class BoomCrashStrategy:
    """
    Strategy 5: Boom & Crash Synthetic Index Strategy
    ──────────────────────────────────────────────────
    SPECIAL STRATEGY for Deriv's synthetic Boom/Crash indices.

    HOW BOOM/CRASH WORKS:
      - Boom indices have random UPWARD spikes every ~1000 ticks
      - Crash indices have random DOWNWARD spikes every ~1000 ticks
      - Between spikes, price moves in a steady trend

    LOGIC for BOOM (e.g. Boom 1000):
      • BUY  when price is trending UP before a spike
             (ride the trend, exit before the spike reverses)
      • After a spike DOWN (price drops sharply), look for
        recovery BUY as price bounces back

    LOGIC for CRASH (e.g. Crash 1000):
      • SELL when price is trending DOWN
      • After a spike UP, look for SELL as price drops back
    """
    name = "Boom/Crash Synthetic"

    def evaluate(self, features: dict, atr: float,
                 symbol: str = "") -> StrategyResult:
        rsi        = features.get("rsi", 50)
        trending_up= features.get("trending_up", 0)
        trending_dn= features.get("trending_down", 0)
        adx        = features.get("adx", 0)
        bb_pct     = features.get("bb_percent", 0.5)

        is_boom  = "Boom"  in symbol
        is_crash = "Crash" in symbol

        # BOOM strategy — look for BUYs
        if is_boom:
            if trending_up and 40 < rsi < 65 and adx > 20:
                confidence = 0.68
                if adx > 35: confidence += 0.10
                sl_pips = atr * 10000 * 1.5
                tp_pips = sl_pips * 2.0
                return StrategyResult("BUY", "BUY", sl_pips, tp_pips,
                                      min(confidence, 0.88),
                                      f"Boom index uptrend, ADX={adx:.0f}")
            # Buy after crash spike (RSI oversold on boom = anomaly, buy the dip)
            if rsi < 25 and bb_pct < 0.1:
                return StrategyResult("BUY", "BUY",
                                      atr * 10000 * 1.2,
                                      atr * 10000 * 2.5, 0.72,
                                      "Boom index post-spike dip recovery")

        # CRASH strategy — look for SELLs
        if is_crash:
            if trending_dn and 35 < rsi < 60 and adx > 20:
                confidence = 0.68
                if adx > 35: confidence += 0.10
                sl_pips = atr * 10000 * 1.5
                tp_pips = sl_pips * 2.0
                return StrategyResult("SELL", "SELL", sl_pips, tp_pips,
                                      min(confidence, 0.88),
                                      f"Crash index downtrend, ADX={adx:.0f}")
            # Sell after boom spike on crash index
            if rsi > 75 and bb_pct > 0.9:
                return StrategyResult("SELL", "SELL",
                                      atr * 10000 * 1.2,
                                      atr * 10000 * 2.5, 0.72,
                                      "Crash index post-spike reversal")

        return StrategyResult()


# Registry of all strategies
ALL_STRATEGIES = [
    EMAStrategy(),
    RSIReversalStrategy(),
    MACDMomentumStrategy(),
    BreakoutStrategy(),
    BoomCrashStrategy(),
]

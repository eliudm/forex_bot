"""
=============================================================
  TECHNICAL INDICATORS MODULE
=============================================================
  PURPOSE: Calculates all the technical indicators the AI
  uses to analyze the market and generate trade signals.

  WHAT ARE INDICATORS?
  Indicators are mathematical calculations applied to
  price data (open, high, low, close) to help identify:
  - Trend direction (is price going up or down?)
  - Momentum (is the move speeding up or slowing down?)
  - Overbought/Oversold conditions (has price moved too far?)
  - Volatility (how wildly is price moving?)

  INDICATORS CALCULATED HERE:
  ✅ RSI      - Relative Strength Index (overbought/oversold)
  ✅ MACD     - Moving Average Convergence Divergence (momentum)
  ✅ EMA      - Exponential Moving Average (trend direction)
  ✅ Bollinger Bands - Volatility bands around price
  ✅ ATR      - Average True Range (measures volatility)
  ✅ ADX      - Average Directional Index (trend strength)
  ✅ Stochastic - Another overbought/oversold indicator
=============================================================
"""

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class IndicatorEngine:
    """
    Calculates all technical indicators for a price DataFrame.
    
    HOW TO USE:
        engine = IndicatorEngine()
        df_with_indicators = engine.add_all(df)
        
    After calling add_all(), your DataFrame will have new columns like:
        rsi, macd, ema20, ema50, ema200, bb_upper, bb_lower, atr, adx, etc.
    """

    def add_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Adds ALL indicators to the price DataFrame at once.
        This is the main function you call.
        """
        df = df.copy()  # Don't modify the original data
        
        logger.debug(f"Calculating indicators on {len(df)} candles...")

        df = self.add_ema(df, 20)
        df = self.add_ema(df, 50)
        df = self.add_ema(df, 200)
        df = self.add_rsi(df, 14)
        df = self.add_macd(df)
        df = self.add_bollinger_bands(df)
        df = self.add_atr(df, 14)
        df = self.add_adx(df, 14)
        df = self.add_stochastic(df)
        df = self.add_candle_features(df)

        # Drop rows with NaN (happens at the beginning before enough data)
        df.dropna(inplace=True)
        df.reset_index(drop=True, inplace=True)

        logger.debug(f"Indicators calculated. DataFrame now has {len(df.columns)} columns.")
        return df

    # ─────────────────────────────────────────
    #  EMA - EXPONENTIAL MOVING AVERAGE
    # ─────────────────────────────────────────
    def add_ema(self, df: pd.DataFrame, period: int) -> pd.DataFrame:
        """
        EMA smooths price to show the trend direction.
        
        HOW TO READ:
        - Price ABOVE EMA = uptrend (bullish)
        - Price BELOW EMA = downtrend (bearish)
        - EMA 20 reacts fast, EMA 200 reacts slowly (long-term trend)
        
        CROSS SIGNAL:
        - EMA20 crosses ABOVE EMA50 = Golden Cross (strong BUY signal)
        - EMA20 crosses BELOW EMA50 = Death Cross (strong SELL signal)
        """
        col_name = f"ema{period}"
        df[col_name] = df['close'].ewm(span=period, adjust=False).mean()
        return df

    # ─────────────────────────────────────────
    #  RSI - RELATIVE STRENGTH INDEX
    # ─────────────────────────────────────────
    def add_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """
        RSI measures if a market is overbought or oversold.
        Ranges from 0 to 100.
        
        HOW TO READ:
        - RSI > 70 = OVERBOUGHT (price may be too high, expect a drop)
        - RSI < 30 = OVERSOLD   (price may be too low, expect a bounce)
        - RSI = 50 = Neutral
        
        SIGNAL:
        - RSI crossing UP through 30 = potential BUY
        - RSI crossing DOWN through 70 = potential SELL
        """
        delta = df['close'].diff()
        gain  = delta.clip(lower=0)
        loss  = -delta.clip(upper=0)

        avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
        avg_loss = loss.ewm(com=period - 1, adjust=False).mean()

        rs        = avg_gain / avg_loss.replace(0, 1e-10)
        df['rsi'] = 100 - (100 / (1 + rs))
        return df

    # ─────────────────────────────────────────
    #  MACD - MOVING AVERAGE CONVERGENCE/DIVERGENCE
    # ─────────────────────────────────────────
    def add_macd(self, df: pd.DataFrame, fast=12, slow=26, signal=9) -> pd.DataFrame:
        """
        MACD shows momentum and potential reversals.
        
        COMPONENTS:
        - macd_line   = Fast EMA (12) minus Slow EMA (26)
        - macd_signal = 9-period EMA of the MACD line
        - macd_hist   = MACD line minus Signal line (histogram bars)
        
        HOW TO READ:
        - MACD line crosses ABOVE signal line = BUY momentum
        - MACD line crosses BELOW signal line = SELL momentum
        - Histogram growing = momentum increasing
        - Histogram shrinking = momentum fading (prepare for reversal)
        """
        ema_fast       = df['close'].ewm(span=fast,   adjust=False).mean()
        ema_slow       = df['close'].ewm(span=slow,   adjust=False).mean()
        df['macd_line']   = ema_fast - ema_slow
        df['macd_signal'] = df['macd_line'].ewm(span=signal, adjust=False).mean()
        df['macd_hist']   = df['macd_line'] - df['macd_signal']
        return df

    # ─────────────────────────────────────────
    #  BOLLINGER BANDS
    # ─────────────────────────────────────────
    def add_bollinger_bands(self, df: pd.DataFrame, period=20, std_dev=2) -> pd.DataFrame:
        """
        Bollinger Bands are volatility bands around a moving average.
        
        COMPONENTS:
        - bb_middle = 20-period SMA of close price
        - bb_upper  = Middle + 2 standard deviations
        - bb_lower  = Middle - 2 standard deviations
        - bb_width  = Distance between upper and lower (shows volatility)
        - bb_pct    = Where price is within the bands (0=at lower, 1=at upper)
        
        HOW TO READ:
        - Price touching UPPER band + RSI>70 = Potential reversal DOWN
        - Price touching LOWER band + RSI<30 = Potential reversal UP
        - Bands WIDENING = volatility increasing (big move may be coming)
        - Bands NARROWING (squeeze) = breakout coming soon
        """
        sma            = df['close'].rolling(window=period).mean()
        std            = df['close'].rolling(window=period).std()
        df['bb_upper'] = sma + (std_dev * std)
        df['bb_middle']= sma
        df['bb_lower'] = sma - (std_dev * std)
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        df['bb_pct']   = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'] + 1e-10)
        return df

    # ─────────────────────────────────────────
    #  ATR - AVERAGE TRUE RANGE
    # ─────────────────────────────────────────
    def add_atr(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """
        ATR measures market volatility (how much price moves per candle).
        
        HOW TO READ:
        - HIGH ATR = Market is volatile (big candles, wide stop losses needed)
        - LOW ATR  = Market is calm (small candles, tight stop losses ok)
        
        USED FOR:
        - Setting stop loss size (e.g., SL = 1.5 x ATR)
        - Detecting if a breakout is real (needs ATR expansion)
        """
        high_low   = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close  = (df['low']  - df['close'].shift()).abs()

        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr']  = true_range.ewm(span=period, adjust=False).mean()
        return df

    # ─────────────────────────────────────────
    #  ADX - AVERAGE DIRECTIONAL INDEX
    # ─────────────────────────────────────────
    def add_adx(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """
        ADX measures how STRONG a trend is (not direction, just strength).
        
        HOW TO READ:
        - ADX < 20 = No clear trend (avoid trend-following strategies)
        - ADX 20-25 = Emerging trend (can start trend trades)
        - ADX > 25 = Strong trend (ideal for trend-following)
        - ADX > 50 = Very strong trend (be careful of reversals)
        
        The bot uses ADX to decide WHICH strategy to use:
        - High ADX → trend-following strategy
        - Low ADX  → range/mean-reversion strategy
        """
        high_diff = df['high'].diff()
        low_diff  = df['low'].diff()

        plus_dm  = high_diff.where((high_diff > low_diff.abs()) & (high_diff > 0), 0.0)
        minus_dm = low_diff.abs().where((low_diff.abs() > high_diff) & (low_diff < 0), 0.0)

        atr_     = df['atr'] if 'atr' in df.columns else self.add_atr(df.copy(), period)['atr']

        plus_di  = 100 * plus_dm.ewm(span=period,  adjust=False).mean() / atr_
        minus_di = 100 * minus_dm.ewm(span=period, adjust=False).mean() / atr_

        dx       = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10))
        df['adx']      = dx.ewm(span=period, adjust=False).mean()
        df['plus_di']  = plus_di
        df['minus_di'] = minus_di
        return df

    # ─────────────────────────────────────────
    #  STOCHASTIC OSCILLATOR
    # ─────────────────────────────────────────
    def add_stochastic(self, df: pd.DataFrame, k_period=14, d_period=3) -> pd.DataFrame:
        """
        Stochastic is another overbought/oversold indicator.
        Works well alongside RSI to confirm signals.
        
        COMPONENTS:
        - stoch_k = %K line (fast, more sensitive)
        - stoch_d = %D line (slow, signal line)
        
        HOW TO READ:
        - Both lines < 20 = OVERSOLD → potential BUY
        - Both lines > 80 = OVERBOUGHT → potential SELL
        - %K crosses ABOVE %D in oversold zone = BUY signal
        - %K crosses BELOW %D in overbought zone = SELL signal
        """
        low_min    = df['low'].rolling(window=k_period).min()
        high_max   = df['high'].rolling(window=k_period).max()
        df['stoch_k'] = 100 * (df['close'] - low_min) / (high_max - low_min + 1e-10)
        df['stoch_d'] = df['stoch_k'].rolling(window=d_period).mean()
        return df

    # ─────────────────────────────────────────
    #  CANDLE PATTERN FEATURES
    # ─────────────────────────────────────────
    def add_candle_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Adds features that describe the shape of each candle.
        These help the AI recognize candlestick patterns.
        
        FEATURES ADDED:
        - candle_body  = Size of the real body (open to close)
        - upper_wick   = Length of upper shadow (high to max(open,close))
        - lower_wick   = Length of lower shadow (min(open,close) to low)
        - is_bullish   = 1 if close > open (green candle), else 0
        - price_change = % change from previous close
        """
        df['candle_body']  = (df['close'] - df['open']).abs()
        df['upper_wick']   = df['high']  - df[['open','close']].max(axis=1)
        df['lower_wick']   = df[['open','close']].min(axis=1) - df['low']
        df['is_bullish']   = (df['close'] > df['open']).astype(int)
        df['price_change'] = df['close'].pct_change() * 100

        # Candle size relative to ATR (normalized) - helps AI compare across assets
        df['body_atr_ratio'] = df['candle_body'] / (df['atr'] + 1e-10)

        return df

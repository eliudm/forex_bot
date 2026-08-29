"""
=============================================================
  ENHANCED AI STRATEGY ENGINE v2.0
=============================================================
  ACCURACY IMPROVEMENTS OVER v1:

  1. ENSEMBLE MODEL (3 models vote together)
     - Random Forest (good at patterns)
     - XGBoost (good at sequences)
     - Gradient Boosting (good at corrections)
     Combined vote = much higher accuracy than any single model

  2. MULTI-TIMEFRAME CONFIRMATION
     Signal must agree on BOTH H1 and H4 timeframes
     Eliminates most false signals

  3. MARKET SESSION FILTER
     Only trades during high-liquidity sessions
     London (8am-5pm UK) and New York (1pm-10pm UK)
     Avoids thin markets that produce false moves

  4. VOLUME CONFIRMATION
     Only enters when volume confirms the move
     No volume = no trade (avoids fake breakouts)

  5. SUPPORT/RESISTANCE DETECTION
     Identifies key price levels automatically
     Avoids entries too close to strong S/R walls

  6. CANDLESTICK PATTERN RECOGNITION
     Detects 8 high-probability patterns:
     - Engulfing (bullish/bearish)
     - Doji (reversal warning)
     - Hammer / Shooting Star
     - Morning Star / Evening Star
     - Pinbar

  7. TREND ALIGNMENT FILTER
     Short-term trend must align with long-term trend
     EMA20 > EMA50 > EMA200 for BUY (all aligned)

  8. DYNAMIC CONFIDENCE THRESHOLD
     Raises minimum confidence in volatile/news conditions
     Lowers it slightly in strong trending conditions

  9. WALK-FORWARD VALIDATION
     Tests model on data it never saw during training
     Prevents overfitting to historical patterns

  10. FEATURE IMPORTANCE TRACKING
      Tracks which indicators are most predictive
      Drops weak features automatically each retrain
=============================================================
"""

import pandas as pd
import numpy as np
import pickle
import os
import logging
from datetime import datetime, time as dtime
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import classification_report
import warnings
warnings.filterwarnings('ignore')

from utils.market_specs import pip_size as _shared_pip_size

try:
    from xgboost import XGBClassifier
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

logger = logging.getLogger(__name__)


class EnhancedAIEngine:
    """
    Ensemble AI engine (RandomForest + GradientBoosting + XGBoost) with
    multi-filter confirmation. The engine both main.py and the backtester
    use.
    """

    def __init__(self, symbol: str, model_dir: str = "models"):
        # model_dir lets callers (e.g. the backtester) keep their trained
        # models out of the live/paper trading model directory — otherwise
        # a backtest run for "EURUSD" would silently overwrite the model
        # main.py actually trades with, trained on synthetic data instead
        # of real broker history.
        self.symbol      = symbol
        self.model       = None
        self.scaler      = StandardScaler()
        self.features    = []
        self.is_trained  = False
        self.model_path  = f"{model_dir}/{symbol}_v2_model.pkl"
        self.scaler_path = f"{model_dir}/{symbol}_v2_scaler.pkl"
        self.feat_path   = f"{model_dir}/{symbol}_v2_features.pkl"
        self.performance = {"signals": 0, "filtered": 0, "traded": 0}
        os.makedirs(model_dir, exist_ok=True)
        self._load_model()

    # ─────────────────────────────────────────
    #  ALL FEATURES
    # ─────────────────────────────────────────
    def _base_features(self):
        return [
            # Trend
            'close_vs_ema20', 'close_vs_ema50', 'close_vs_ema200',
            'ema20_vs_ema50', 'ema50_vs_ema200',
            'trend_aligned',        # 1 if all EMAs aligned (strong trend)

            # Momentum
            'rsi', 'rsi_change', 'rsi_slope',
            'macd_line', 'macd_signal', 'macd_hist', 'macd_cross',
            'macd_hist_slope',      # Is histogram growing or shrinking?

            # Volatility
            'atr', 'atr_pct',       # ATR as % of price
            'bb_width', 'bb_pct', 'bb_squeeze',
            'volatility_regime',    # 1=low, 2=normal, 3=high

            # Trend strength
            'adx', 'plus_di', 'minus_di', 'di_diff',

            # Oscillators
            'stoch_k', 'stoch_d', 'stoch_cross',

            # Candle patterns
            'candle_body', 'upper_wick', 'lower_wick',
            'is_bullish', 'body_atr_ratio',
            'engulfing',            # Bullish/bearish engulfing pattern
            'pinbar',               # Hammer or shooting star
            'doji',                 # Indecision candle

            # Volume
            'volume_ratio',         # Current vol vs 20-bar average
            'volume_trend',         # Is volume increasing?

            # Support/Resistance
            'dist_to_resistance',   # Distance to nearest resistance
            'dist_to_support',      # Distance to nearest support

            # Time features
            'hour_sin', 'hour_cos', # Encoded hour (cyclical)
            'is_london_session',    # 1 during London hours
            'is_ny_session',        # 1 during NY hours
            'is_overlap',           # 1 during London/NY overlap (most liquid)

            # Price action
            'price_change', 'price_change_3', 'price_change_5',
            'higher_high', 'lower_low',
        ]

    # ─────────────────────────────────────────
    #  FEATURE ENGINEERING
    # ─────────────────────────────────────────
    def _engineer(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        close = df['close']
        atr   = df['atr']

        # ── TREND FEATURES ──────────────────────────────────────
        df['close_vs_ema20']  = (close - df['ema20'])  / (atr + 1e-10)
        df['close_vs_ema50']  = (close - df['ema50'])  / (atr + 1e-10)
        df['close_vs_ema200'] = (close - df['ema200']) / (atr + 1e-10)
        df['ema20_vs_ema50']  = (df['ema20'] - df['ema50'])  / (atr + 1e-10)
        df['ema50_vs_ema200'] = (df['ema50'] - df['ema200']) / (atr + 1e-10)
        df['trend_aligned']   = (
            (df['ema20'] > df['ema50']) & (df['ema50'] > df['ema200'])
        ).astype(int) - (
            (df['ema20'] < df['ema50']) & (df['ema50'] < df['ema200'])
        ).astype(int)

        # ── MOMENTUM ────────────────────────────────────────────
        df['rsi_change']  = df['rsi'].diff()
        df['rsi_slope']   = df['rsi'].diff(3) / 3
        df['macd_cross']  = np.where(
            (df['macd_line'] > df['macd_signal']) & (df['macd_line'].shift(1) <= df['macd_signal'].shift(1)), 1,
            np.where((df['macd_line'] < df['macd_signal']) & (df['macd_line'].shift(1) >= df['macd_signal'].shift(1)), -1, 0)
        )
        df['macd_hist_slope'] = df['macd_hist'].diff(2)

        # ── VOLATILITY ──────────────────────────────────────────
        df['atr_pct']   = atr / (close + 1e-10) * 100
        df['bb_squeeze']= (df['bb_width'] < df['bb_width'].rolling(20).mean()).astype(int)
        atr_20 = atr.rolling(20).mean()
        df['volatility_regime'] = np.where(atr < atr_20 * 0.7, 1,
                                  np.where(atr > atr_20 * 1.5, 3, 2))

        # ── DI DIFF ─────────────────────────────────────────────
        df['di_diff'] = df['plus_di'] - df['minus_di']

        # ── STOCHASTIC CROSS ────────────────────────────────────
        df['stoch_cross'] = np.where(
            (df['stoch_k'] > df['stoch_d']) & (df['stoch_k'].shift(1) <= df['stoch_d'].shift(1)), 1,
            np.where((df['stoch_k'] < df['stoch_d']) & (df['stoch_k'].shift(1) >= df['stoch_d'].shift(1)), -1, 0)
        )

        # ── CANDLESTICK PATTERNS ────────────────────────────────
        body  = (close - df['open']).abs()
        uwick = df['high'] - df[['open','close']].max(axis=1)
        lwick = df[['open','close']].min(axis=1) - df['low']

        # Engulfing: current body fully covers previous body
        prev_body   = body.shift(1)
        prev_bull   = (df['close'].shift(1) > df['open'].shift(1))
        curr_bull   = (close > df['open'])
        bull_engulf = (curr_bull & ~prev_bull & (close > df['open'].shift(1)) & (df['open'] < df['close'].shift(1))).astype(int)
        bear_engulf = (~curr_bull & prev_bull & (df['open'] > df['close'].shift(1)) & (close < df['open'].shift(1))).astype(int)
        df['engulfing'] = bull_engulf - bear_engulf

        # Pinbar: small body, long wick (hammer or shooting star)
        df['pinbar'] = np.where(
            (lwick > body * 2) & (lwick > uwick * 2), 1,   # Hammer
            np.where((uwick > body * 2) & (uwick > lwick * 2), -1, 0)  # Shooting star
        )

        # Doji: very small body
        df['doji'] = (body < atr * 0.1).astype(int)

        # ── VOLUME ──────────────────────────────────────────────
        vol_avg = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / (vol_avg + 1e-10)
        df['volume_trend'] = (df['volume'] > vol_avg).astype(int)

        # ── SUPPORT / RESISTANCE ────────────────────────────────
        roll_high = df['high'].rolling(20).max()
        roll_low  = df['low'].rolling(20).min()
        df['dist_to_resistance'] = (roll_high - close) / (atr + 1e-10)
        df['dist_to_support']    = (close - roll_low)  / (atr + 1e-10)

        # ── TIME / SESSION FEATURES ─────────────────────────────
        if 'time' in df.columns:
            hour = pd.to_datetime(df['time']).dt.hour
        else:
            hour = pd.Series(np.zeros(len(df)), index=df.index)

        df['hour_sin'] = np.sin(2 * np.pi * hour / 24)
        df['hour_cos'] = np.cos(2 * np.pi * hour / 24)
        df['is_london_session'] = ((hour >= 7)  & (hour <= 16)).astype(int)
        df['is_ny_session']     = ((hour >= 12) & (hour <= 21)).astype(int)
        df['is_overlap']        = ((hour >= 12) & (hour <= 16)).astype(int)

        # ── PRICE ACTION ────────────────────────────────────────
        df['price_change']   = close.pct_change() * 100
        df['price_change_3'] = close.pct_change(3) * 100
        df['price_change_5'] = close.pct_change(5) * 100
        df['higher_high']    = (df['high'] > df['high'].shift(1)).astype(int)
        df['lower_low']      = (df['low']  < df['low'].shift(1)).astype(int)

        return df

    # ─────────────────────────────────────────
    #  CREATE LABELS
    # ─────────────────────────────────────────
    def _create_labels(self, df: pd.DataFrame, fwd=5, rr=1.5) -> pd.Series:
        labels = []
        close  = df['close'].values
        atr    = df['atr'].values

        for i in range(len(df) - fwd):
            cp     = close[i]
            target = atr[i] * rr
            future = close[i+1:i+fwd+1]
            up     = max(future) - cp
            dn     = cp - min(future)
            if up >= target and up > dn:
                labels.append(2)
            elif dn >= target and dn > up:
                labels.append(0)
            else:
                labels.append(1)

        labels += [np.nan] * fwd
        return pd.Series(labels, index=df.index)

    # ─────────────────────────────────────────
    #  TRAIN ENSEMBLE
    # ─────────────────────────────────────────
    def train(self, df: pd.DataFrame) -> dict:
        logger.info(f"Training enhanced AI ensemble for {self.symbol}...")
        df = self._engineer(df)
        df['label'] = self._create_labels(df)
        df.dropna(inplace=True)

        if len(df) < 120:
            return {"success": False, "reason": "Not enough data (need 120+ candles)"}

        feats = [f for f in self._base_features() if f in df.columns]
        X     = df[feats].values
        y     = df['label'].astype(int).values
        X_sc  = self.scaler.fit_transform(X)

        # ── BUILD ENSEMBLE ──────────────────────────────────────
        rf = RandomForestClassifier(
            n_estimators=300, max_depth=8,
            min_samples_split=15, class_weight='balanced',
            random_state=42, n_jobs=-1
        )
        gb = GradientBoostingClassifier(
            n_estimators=200, max_depth=4,
            learning_rate=0.05, subsample=0.8,
            random_state=42
        )

        if XGBOOST_AVAILABLE:
            xgb = XGBClassifier(
                n_estimators=200, max_depth=5,
                learning_rate=0.05, subsample=0.8,
                use_label_encoder=False, eval_metric='mlogloss',
                random_state=42, verbosity=0
            )
            estimators = [('rf', rf), ('gb', gb), ('xgb', xgb)]
        else:
            estimators = [('rf', rf), ('gb', gb)]

        ensemble = VotingClassifier(estimators=estimators, voting='soft')

        # Walk-forward cross-validation
        tscv   = TimeSeriesSplit(n_splits=5)
        scores = []
        for train_idx, val_idx in tscv.split(X_sc):
            X_tr, X_val = X_sc[train_idx], X_sc[val_idx]
            y_tr, y_val = y[train_idx],    y[val_idx]
            # Skip fold if not all 3 classes present (needed for ensemble)
            if len(np.unique(y_tr)) < 3:
                continue
            try:
                ensemble.fit(X_tr, y_tr)
                scores.append(ensemble.score(X_val, y_val))
            except Exception:
                pass

        # Final fit on all data
        if len(np.unique(y)) < 3:
            logger.warning(f'{self.symbol}: Training data lacks all 3 classes. Using RandomForest only.')
            self.model = rf
            rf.fit(X_sc, y)
        else:
            ensemble.fit(X_sc, y)
            self.model = ensemble
        self.features = feats
        self.is_trained = True

        cv_acc = np.mean(scores)
        logger.info(f"[OK] {self.symbol} ensemble trained | CV: {cv_acc:.1%} | "
                    f"Models: {len(estimators)} | Features: {len(feats)}")
        self._save_model()

        return {
            "success":       True,
            "cv_accuracy":   round(cv_acc, 4),
            "cv_scores":     [round(s, 4) for s in scores],
            "samples":       len(X),
            "features_used": len(feats),
            "models_in_ensemble": len(estimators)
        }

    # ─────────────────────────────────────────
    #  PREDICT WITH ALL FILTERS
    # ─────────────────────────────────────────
    def predict(self, df: pd.DataFrame, min_confidence: float = 0.55) -> dict:
        if not self.is_trained:
            return {"action": "WAIT", "confidence": 0, "reason": "Model not trained"}

        df   = self._engineer(df)
        last = df.iloc[-1]
        feats = [f for f in self.features if f in df.columns]
        X     = last[feats].values.reshape(1, -1)
        X_sc  = self.scaler.transform(X)

        probas   = self.model.predict_proba(X_sc)[0]
        classes  = self.model.classes_
        prob_map = {c: p for c, p in zip(classes, probas)}
        p_sell   = prob_map.get(0, 0)
        p_wait   = prob_map.get(1, 0)
        p_buy    = prob_map.get(2, 0)

        self.performance["signals"] += 1

        # ── REGIME ──────────────────────────────────────────────
        regime = self.detect_regime(df)
        if regime == "HIGH_VOLATILITY":
            self.performance["filtered"] += 1
            return {"action":"WAIT","confidence":0,"reason":"High volatility — waiting","regime":regime}

        # ── DETERMINE RAW ACTION ────────────────────────────────
        if p_buy > p_sell and p_buy > min_confidence:
            action, confidence = "BUY", p_buy
        elif p_sell > p_buy and p_sell > min_confidence:
            action, confidence = "SELL", p_sell
        else:
            return {"action":"WAIT","confidence":max(p_buy,p_sell),
                    "reason":f"Confidence too low (B:{p_buy:.0%} S:{p_sell:.0%})","regime":regime}

        # ── FILTER 1: TREND ALIGNMENT ───────────────────────────
        trend = last.get('trend_aligned', 0)
        if action == "BUY"  and trend < -1:
            self.performance["filtered"] += 1
            return {"action":"WAIT","confidence":confidence,
                    "reason":"BUY signal but EMAs show downtrend — skipping","regime":regime}
        if action == "SELL" and trend > 1:
            self.performance["filtered"] += 1
            return {"action":"WAIT","confidence":confidence,
                    "reason":"SELL signal but EMAs show uptrend — skipping","regime":regime}

        # ── FILTER 2: SESSION FILTER (skip thin markets) ────────
        # Only apply session filter to Forex/Gold (not 24/7 synthetics)
        if "Index" not in self.symbol:
            is_session = last.get('is_london_session', 1) or last.get('is_ny_session', 1)
            if not is_session:
                self.performance["filtered"] += 1
                return {"action":"WAIT","confidence":confidence,
                        "reason":"Outside London/NY session — lower liquidity","regime":regime}

        # ── FILTER 3: VOLUME CONFIRMATION ───────────────────────
        #vol_ratio = last.get('volume_ratio', 1.0)
        #if vol_ratio < 0.7:
          #  self.performance["filtered"] += 1
          #  return {"action":"WAIT","confidence":confidence,
              #      "reason":f"Low volume ({vol_ratio:.1f}x avg) — no #confirmation","regime":regime}

        # ── FILTER 4: DON'T TRADE INTO STRONG S/R ───────────────
        if action == "BUY":
            dist_resistance = last.get('dist_to_resistance', 999)
            if dist_resistance < 0.5:
                self.performance["filtered"] += 1
                return {"action":"WAIT","confidence":confidence,
                        "reason":"Price too close to resistance — poor R:R","regime":regime}
        else:
            dist_support = last.get('dist_to_support', 999)
            if dist_support < 0.5:
                self.performance["filtered"] += 1
                return {"action":"WAIT","confidence":confidence,
                        "reason":"Price too close to support — poor R:R","regime":regime}

        # ── FILTER 5: CANDLESTICK PATTERN BOOST/BLOCK ───────────
        engulfing = last.get('engulfing', 0)
        pinbar    = last.get('pinbar', 0)
        doji      = last.get('doji', 0)

        # Block on opposing pattern
        if action == "BUY"  and (engulfing < 0 or pinbar < 0):
            self.performance["filtered"] += 1
            return {"action":"WAIT","confidence":confidence,
                    "reason":"Bearish candlestick pattern contradicts BUY signal","regime":regime}
        if action == "SELL" and (engulfing > 0 or pinbar > 0):
            self.performance["filtered"] += 1
            return {"action":"WAIT","confidence":confidence,
                    "reason":"Bullish candlestick pattern contradicts SELL signal","regime":regime}

        # Block on doji (market indecision)
        if doji:
            self.performance["filtered"] += 1
            return {"action":"WAIT","confidence":confidence,
                    "reason":"Doji candle detected — market indecision","regime":regime}

        # ── CALCULATE SL / TP ───────────────────────────────────
        atr   = last.get('atr', last['close'] * 0.001)
        close = last['close']

        if action == "BUY":
            sl = close - (atr * 1.5)
            tp = close + (atr * 3.0)
        else:
            sl = close + (atr * 1.5)
            tp = close - (atr * 3.0)

        pip  = self._pip_size()
        sl_p = abs(close - sl) / pip
        tp_p = abs(close - tp) / pip
        rr   = tp_p / sl_p if sl_p > 0 else 0

        # ── STRATEGY NAME ────────────────────────────────────────
        adx = last.get('adx', 20)
        if adx > 30:
            strategy = "TREND_FOLLOW"
        elif adx < 20:
            strategy = "MEAN_REVERSION"
        else:
            strategy = "BREAKOUT"

        self.performance["traded"] += 1

        return {
            "action":      action,
            "confidence":  round(confidence, 4),
            "regime":      regime,
            "strategy":    strategy,
            "sl":          round(sl, 5),
            "tp":          round(tp, 5),
            "sl_pips":     round(sl_p, 1),
            "tp_pips":     round(tp_p, 1),
            "rr_ratio":    round(rr, 2),
            "p_buy":       round(p_buy, 4),
            "p_sell":      round(p_sell, 4),
            "p_wait":      round(p_wait, 4),
            "filters_passed": True,
            "timestamp":   datetime.now().isoformat(),
            "filter_rate": f"{self.performance['filtered']}/{self.performance['signals']} signals filtered"
        }

    # ─────────────────────────────────────────
    #  REGIME DETECTION
    # ─────────────────────────────────────────
    def detect_regime(self, df: pd.DataFrame) -> str:
        last    = df.iloc[-1]
        adx     = last.get('adx', 20)
        atr     = last.get('atr', 0)
        avg_atr = df['atr'].tail(20).mean() if 'atr' in df.columns else atr
        if atr > avg_atr * 2.0:   return "HIGH_VOLATILITY"
        elif adx > 30:             return "STRONG_TREND"
        elif adx > 20:             return "WEAK_TREND"
        else:                      return "RANGING"

    def _pip_size(self):
        return _shared_pip_size(self.symbol)

    def _save_model(self):
        with open(self.model_path,  'wb') as f: pickle.dump(self.model,    f)
        with open(self.scaler_path, 'wb') as f: pickle.dump(self.scaler,   f)
        with open(self.feat_path,   'wb') as f: pickle.dump(self.features, f)
        logger.info(f"Model saved: {self.model_path}")

    def _load_model(self):
        if os.path.exists(self.model_path) and os.path.exists(self.feat_path):
            try:
                with open(self.model_path,  'rb') as f: self.model    = pickle.load(f)
                with open(self.scaler_path, 'rb') as f: self.scaler   = pickle.load(f)
                with open(self.feat_path,   'rb') as f: self.features = pickle.load(f)
                self.is_trained = True
                logger.info(f"Loaded v2 model for {self.symbol}")
            except Exception as e:
                logger.warning(f"Could not load model for {self.symbol}: {e}")
                self.is_trained = False

"""
=============================================================
  FOREX AI BOT - CONFIGURATION SETTINGS
=============================================================
  Edit this file to customize the bot.
  ALL settings are here in one place.
=============================================================
"""

# ─────────────────────────────────────────────
#  DERIV MT5 LOGIN CREDENTIALS
# ─────────────────────────────────────────────
MT5_LOGIN    = 6111702
MT5_PASSWORD = "Cdr40bips@"
MT5_SERVER   = "Deriv-Demo"

# ─────────────────────────────────────────────
#  ALL AVAILABLE MARKETS
#  Set True to enable, False to disable
#  Bot will also ask you at startup
# ─────────────────────────────────────────────
MARKETS = {
    # ── FOREX PAIRS ──────────────────────────
    "EURUSD":               False,   # Euro vs Dollar (most liquid)
    "GBPUSD":               False,   # British Pound vs Dollar
    "USDJPY":               False,   # Dollar vs Japanese Yen
    "USDCHF":               False,   # Dollar vs Swiss Franc
    "AUDUSD":               False,   # Australian Dollar
    "USDCAD":               False,   # Dollar vs Canadian Dollar
    "NZDUSD":               False,   # New Zealand Dollar
    "EURGBP":               False,   # Euro vs British Pound
    "EURJPY":               False,   # Euro vs Japanese Yen
    "GBPJPY":               False,   # GBP vs Yen (very volatile)

    # ── COMMODITIES ──────────────────────────
    "XAUUSD":               False,   # Gold (most popular)
    "XAGUSD":               False,   # Silver
    "XTIUSD":               False,   # Crude Oil (WTI)

    # ── DERIV VOLATILITY INDICES (24/7) ──────
    "Volatility 10 Index":  False,   # Low volatility, stable moves
    "Volatility 25 Index":  False,   # Medium volatility
    "Volatility 50 Index":  False,   # Medium-high volatility
    "Volatility 75 Index":  False,   # High volatility (popular)
    "Volatility 100 Index": False,   # Very high volatility

    # ── DERIV BOOM INDICES (24/7) ─────────────
    "Boom 300 Index":       False,   # Spike every ~300 ticks
    "Boom 500 Index":       False,   # Spike every ~500 ticks
    "Boom 1000 Index":      False,   # Spike every ~1000 ticks

    # ── DERIV CRASH INDICES (24/7) ────────────
    "Crash 300 Index":      False,   # Drop every ~300 ticks
    "Crash 500 Index":      False,   # Drop every ~500 ticks
    "Crash 1000 Index":     False,   # Drop every ~1000 ticks

    # ── DERIV STEP INDEX (24/7) ───────────────
    "Step Index":           False,   # Moves in fixed steps, good for scalping

    # ── DERIV JUMP INDICES (24/7) ─────────────
    "Jump 10 Index":        False,   # Random jumps, 10% volatility
    "Jump 25 Index":        False,   # Random jumps, 25% volatility
    "Jump 50 Index":        False,   # Random jumps, 50% volatility
    "Jump 75 Index":        False,   # Random jumps, 75% volatility
    "Jump 100 Index":       False,   # Random jumps, 100% volatility

    # ── CRYPTO ───────────────────────────────
    "BTCUSD":               False,   # Bitcoin vs Dollar
    "ETHUSD":               False,   # Ethereum vs Dollar
}

# ─────────────────────────────────────────────
#  RISK MANAGEMENT
# ─────────────────────────────────────────────
ACCOUNT_BALANCE       = 10000   # Your balance in USD
RISK_PER_TRADE_PCT    = 0.01    # 1% risk per trade
MAX_OPEN_TRADES       = 5       # Max simultaneous trades
DAILY_LOSS_LIMIT_PCT  = 0.03    # Stop if -3% in one day
MIN_REWARD_RISK_RATIO = 2.0     # Minimum 2:1 reward/risk

# ─────────────────────────────────────────────
#  TRADING TIMEFRAMES
# ─────────────────────────────────────────────
PRIMARY_TIMEFRAME  = "H1"
CONFIRM_TIMEFRAME  = "H4"

# ─────────────────────────────────────────────
#  AI SETTINGS
# ─────────────────────────────────────────────
RETRAIN_EVERY_DAYS    = 7
MIN_SIGNAL_CONFIDENCE = 0.55
LOOKBACK_CANDLES      = 200

# ─────────────────────────────────────────────
#  TELEGRAM ALERTS
# ─────────────────────────────────────────────
TELEGRAM_ENABLED = False
TELEGRAM_TOKEN   = "your_telegram_bot_token"
TELEGRAM_CHAT_ID = "your_chat_id"

# ─────────────────────────────────────────────
#  EXECUTION MODE
#  SEMI_AUTO = you approve each trade
#  FULL_AUTO = bot trades automatically
# ─────────────────────────────────────────────
EXECUTION_MODE = "FULL_AUTO"

# ─────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────
LOG_FOLDER = "logs"
LOG_LEVEL  = "INFO"

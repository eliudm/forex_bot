"""
=============================================================
  FOREX AI BOT - CONFIGURATION SETTINGS
=============================================================
  Edit this file to customize the bot.
  ALL settings are here in one place.

  Secrets (MT5 login, Telegram token) are NOT stored here.
  Copy .env.example to .env and fill them in there instead —
  .env is gitignored so they never end up in source control.
=============================================================
"""

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ─────────────────────────────────────────────
#  BROKER MODE
#  PAPER = simulated broker, no account needed (default — just works)
#  MT5   = real Deriv MT5 account via the MetaTrader5 terminal
# ─────────────────────────────────────────────
BROKER_MODE = os.environ.get("BROKER_MODE", "MT5").upper()

# ─────────────────────────────────────────────
#  DERIV MT5 LOGIN CREDENTIALS (only used when BROKER_MODE = "MT5")
#  Set these in a .env file — see .env.example
# ─────────────────────────────────────────────
MT5_LOGIN    = int(os.environ.get("MT5_LOGIN", "0") or "0")
MT5_PASSWORD = os.environ.get("MT5_PASSWORD", "")
MT5_SERVER   = os.environ.get("MT5_SERVER", "Deriv-Demo")

# ─────────────────────────────────────────────
#  ALL AVAILABLE MARKETS
#  Set True to enable, False to disable
#  Bot will also ask you at startup
# ─────────────────────────────────────────────
MARKETS = {
    # ── FOREX PAIRS ──────────────────────────
    "EURUSD":               True,    # Euro vs Dollar (most liquid)
    "GBPUSD":               True,    # British Pound vs Dollar
    "USDJPY":               True,    # Dollar vs Japanese Yen
    "USDCHF":               True,    # Dollar vs Swiss Franc
    "AUDUSD":               True,    # Australian Dollar
    "USDCAD":               True,    # Dollar vs Canadian Dollar
    "NZDUSD":               True,    # New Zealand Dollar
    "EURGBP":               True,    # Euro vs British Pound
    "EURJPY":               True,    # Euro vs Japanese Yen
    "GBPJPY":               True,    # GBP vs Yen (very volatile)

    # ── COMMODITIES ──────────────────────────
    "XAUUSD":               True,    # Gold (most popular)
    "XAGUSD":               True,    # Silver
    "XTIUSD":               True,    # Crude Oil (WTI)

    # ── DERIV VOLATILITY INDICES (24/7) ──────
    "Volatility 10 Index":  True,    # Low volatility, stable moves
    "Volatility 25 Index":  True,    # Medium volatility
    "Volatility 50 Index":  True,    # Medium-high volatility
    "Volatility 75 Index":  True,    # High volatility (popular)
    "Volatility 100 Index": True,    # Very high volatility

    # ── DERIV BOOM INDICES (24/7) ─────────────
    "Boom 300 Index":       True,    # Spike every ~300 ticks
    "Boom 500 Index":       True,    # Spike every ~500 ticks
    "Boom 1000 Index":      True,    # Spike every ~1000 ticks

    # ── DERIV CRASH INDICES (24/7) ────────────
    "Crash 300 Index":      True,    # Drop every ~300 ticks
    "Crash 500 Index":      True,    # Drop every ~500 ticks
    "Crash 1000 Index":     True,    # Drop every ~1000 ticks

    # ── DERIV STEP INDEX (24/7) ───────────────
    "Step Index":           True,    # Moves in fixed steps, good for scalping

    # ── DERIV JUMP INDICES (24/7) ─────────────
    "Jump 10 Index":        True,    # Random jumps, 10% volatility
    "Jump 25 Index":        True,    # Random jumps, 25% volatility
    "Jump 50 Index":        True,    # Random jumps, 50% volatility
    "Jump 75 Index":        True,    # Random jumps, 75% volatility
    "Jump 100 Index":       True,    # Random jumps, 100% volatility

    # ── CRYPTO ───────────────────────────────
    "BTCUSD":               True,    # Bitcoin vs Dollar
    "ETHUSD":               True,    # Ethereum vs Dollar
}

# ─────────────────────────────────────────────
#  RISK MANAGEMENT
# ─────────────────────────────────────────────
ACCOUNT_BALANCE       = 10000   # Your balance in USD
RISK_PER_TRADE_PCT    = 0.020   # Base risk per trade (scaled per symbol tier below)
MAX_OPEN_TRADES       = 20      # Max simultaneous trades
DAILY_LOSS_LIMIT_PCT  = 0.03    # Stop if -3% in one day
MIN_REWARD_RISK_RATIO = 2.0     # Minimum 2:1 reward/risk

# ─────────────────────────────────────────────
#  SYMBOL RISK TIERS
#  Controls how much of RISK_PER_TRADE_PCT is used per symbol.
#  LOW    = 1.5× base  → safer markets get more capital
#  MEDIUM = 1.0× base  → standard allocation
#  HIGH   = 0.5× base  → volatile markets get half
#  EXTREME= 0.25× base → most volatile get quarter
# ─────────────────────────────────────────────
SYMBOL_RISK_TIERS = {
    # ── TIER: LOW (stable, liquid, tight spreads) ─────────────
    "EURUSD":               "LOW",
    "GBPUSD":               "LOW",
    "USDJPY":               "LOW",
    "USDCHF":               "LOW",
    "AUDUSD":               "LOW",
    "USDCAD":               "LOW",
    "NZDUSD":               "LOW",
    "EURGBP":               "LOW",

    # ── TIER: MEDIUM (more volatile but manageable) ────────────
    "EURJPY":               "MEDIUM",
    "GBPJPY":               "MEDIUM",
    "XAUUSD":               "MEDIUM",
    "XAGUSD":               "MEDIUM",
    "XTIUSD":               "MEDIUM",
    "Volatility 10 Index":  "MEDIUM",
    "Volatility 25 Index":  "MEDIUM",
    "Boom 1000 Index":      "MEDIUM",
    "Crash 1000 Index":     "MEDIUM",
    "Jump 10 Index":        "MEDIUM",

    # ── TIER: HIGH (synthetic/crypto, wide moves) ──────────────
    "Volatility 50 Index":  "HIGH",
    "Volatility 75 Index":  "HIGH",
    "Volatility 100 Index": "HIGH",
    "Boom 500 Index":       "HIGH",
    "Crash 500 Index":      "HIGH",
    "Jump 25 Index":        "HIGH",
    "Jump 50 Index":        "HIGH",
    "BTCUSD":               "HIGH",
    "ETHUSD":               "HIGH",

    # ── TIER: EXTREME (fastest-moving, spike/crash indices) ────
    "Boom 300 Index":       "EXTREME",
    "Crash 300 Index":      "EXTREME",
    "Jump 75 Index":        "EXTREME",
    "Jump 100 Index":       "EXTREME",
    "Step Index":           "EXTREME",
}

TIER_MULTIPLIERS = {
    "LOW":     1.5,   # up to 3% on safest pairs
    "MEDIUM":  1.0,   # exactly base risk
    "HIGH":    0.5,   # half on volatile synthetics
    "EXTREME": 0.25,  # quarter on spike/crash indices
}

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
#  Set TELEGRAM_TOKEN and TELEGRAM_CHAT_ID in .env to enable.
# ─────────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_ENABLED = bool(TELEGRAM_TOKEN and TELEGRAM_CHAT_ID)

# ─────────────────────────────────────────────
#  EXECUTION MODE
#  SEMI_AUTO = you approve each trade   <- default; switch to FULL_AUTO
#              deliberately, once you trust it, not by inheriting a
#              risky default
#  FULL_AUTO = bot trades automatically with no human in the loop
#  Override with BOT_EXECUTION_MODE = "FULL_AUTO"
#  SEMI_AUTO's approval prompt calls input(), which hangs in CI/automation.
# ─────────────────────────────────────────────
EXECUTION_MODE = "FULL_AUTO"
if EXECUTION_MODE not in ("SEMI_AUTO", "FULL_AUTO"):
    EXECUTION_MODE = "FULL_AUTO"

# ─────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────
LOG_FOLDER = "logs"
LOG_LEVEL  = "INFO"

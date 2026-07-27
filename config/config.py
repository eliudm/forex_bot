# ============================================================
# config.py — Central Bot Configuration
# ============================================================
# BEGINNER GUIDE:
#   This file controls ALL settings for your bot.
#   Fill in your MT5 login, password, and Telegram details.
#   Start with EXECUTION_MODE = "SEMI_AUTO" so you approve
#   every trade before it goes live. Only switch to FULL_AUTO
#   after you're satisfied with performance on demo.
# ============================================================

import os

# ── YOUR ACCOUNT ──────────────────────────────────────────────
ACCOUNT_BALANCE      = 500          # Your starting capital in USD
RISK_PER_TRADE_PCT   = 0.01         # Risk 1% per trade. On $500 = $5 risk per trade
MAX_OPEN_TRADES      = 3            # Max trades open at once (keep low for small account)
DAILY_LOSS_LIMIT_PCT = 0.03         # Bot pauses if you lose 3% in a day ($15 on $500)
MIN_RR_RATIO         = 2.0          # Only take trades where profit target >= 2x stop loss

# ── WHICH MARKETS TO TRADE ───────────────────────────────────
# Bot will ask you before it trades any of these.
# To disable a market, remove it from the list.
ALLOWED_MARKETS = {
    "forex":     ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD"],
    "gold":      ["XAUUSD"],
    "synthetic": [
        "Volatility 75 Index",
        "Boom 1000 Index",  "Boom 500 Index",
        "Crash 1000 Index", "Crash 500 Index",
    ],
}

# ── TIMEFRAMES ───────────────────────────────────────────────
# M5=5min, M15=15min, H1=1hour, H4=4hour
# Explanation: The bot looks at 2 timeframes.
#   PRIMARY = where it looks for entry signals
#   CONFIRM = bigger picture to make sure we're with the trend
PRIMARY_TIMEFRAME  = "M15"          # Signal timeframe
CONFIRM_TIMEFRAME  = "H1"           # Trend confirmation timeframe
SYNTHETIC_TF       = "M5"           # Synthetics move faster, use 5min

# ── EXECUTION MODE ───────────────────────────────────────────
# "SEMI_AUTO"  → Bot sends you a Telegram alert asking to approve/reject each trade
# "FULL_AUTO"  → Bot places trades automatically (use after testing)
# "BACKTEST"   → Runs on historical data to test performance (no real trades)
EXECUTION_MODE = "SEMI_AUTO"

# ── AI ENGINE SETTINGS ───────────────────────────────────────
AI_CONFIDENCE_THRESHOLD = 0.65      # Only trade if AI model is 65%+ confident
AI_RETRAIN_EVERY_DAYS   = 7         # Retrain AI model every 7 days on fresh data
LOOKBACK_CANDLES        = 200       # How many past candles AI analyses per signal

# ── RISK MANAGEMENT RULES ────────────────────────────────────
# These rules protect your account while trades are open:
TRAILING_STOP_ACTIVATE_R = 0.75     # Start trailing stop once up 0.75R in profit
BREAKEVEN_AT_R           = 0.5      # Move stop loss to entry (break-even) at 0.5R profit
PARTIAL_CLOSE_AT_R       = 1.0      # Close half the trade at 1R profit, let rest run
NEWS_FILTER_MINUTES      = 15       # Pause trading 15 min before/after major news
MAX_SPREAD_PIPS          = 3.0      # Skip trade if broker spread is above 3 pips

# ── MT5 BROKER CREDENTIALS (Deriv) ───────────────────────────
# Step 1: Open a FREE demo account at deriv.com
# Step 2: Go to Deriv → Platforms → MetaTrader 5 → Create account
# Step 3: Fill in your account number, password, and server below
MT5_LOGIN    = 6111702              # Your Deriv MT5 account number (e.g. 12345678)
MT5_PASSWORD = "Cdr40bips@"                   # Your Deriv MT5 password
MT5_SERVER   = "Deriv-Demo"         # "Deriv-Demo" for testing, "Deriv-Server" for live

# ── TELEGRAM ALERTS ──────────────────────────────────────────
# Step 1: Open Telegram, search for @BotFather
# Step 2: Send /newbot, follow instructions, copy the token below
# Step 3: Message your bot once, then run get_chat_id.py to get your chat ID
TELEGRAM_TOKEN   = ""               # Looks like: 7234567890:AAFxxxxxxxxxxxxxxxxxxxx
TELEGRAM_CHAT_ID = ""               # Looks like: 123456789

# ── SMALL ACCOUNT PROTECTION ($500) ──────────────────────────
MIN_LOT_SIZE          = 0.01        # Smallest trade = 0.01 lots (micro lot)
MAX_LOT_SIZE          = 0.05        # Never trade more than 0.05 lots at once
USE_CENT_ACCOUNT      = True        # Deriv cent account: $500 acts like $50,000
                                    # in cents — STRONGLY recommended for beginners
SYNTHETIC_NEWS_FILTER = False       # Synthetic indices are unaffected by news events

# ── LOGGING ──────────────────────────────────────────────────
LOG_FOLDER = os.path.join(os.path.dirname(__file__), "..", "logs")
LOG_LEVEL  = "INFO"                 # Change to "DEBUG" to see more detail

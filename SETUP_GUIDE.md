# 🤖 AI Forex Trading Bot — Complete Setup Guide
## For Beginners | Deriv + MT5 | $500 Account

---

## ⚡ QUICK START (4 Steps)

### Step 1: Install Python
Download Python 3.10+ from https://python.org/downloads
- On Windows: tick "Add Python to PATH" during install
- Test: open Command Prompt and type `python --version`

### Step 2: Install Required Libraries
Open Command Prompt / Terminal in the bot folder and run:
```
pip install MetaTrader5 pandas numpy scikit-learn requests pandas-ta streamlit plotly
```

### Step 3: Set Up Deriv MT5 Account
1. Go to https://deriv.com and create a FREE account
2. Click "Platforms" → "MetaTrader 5" → "Create Account"
3. Choose "Demo" account first (practice with $10,000 virtual money)
4. Download and install MT5 from the Deriv page
5. Log in to MT5 with your Deriv credentials
6. In MT5, go to "View" → "Market Watch" → right-click → "Show All"
   (This makes Boom/Crash/Volatility symbols available)

### Step 4: Configure the Bot
Open `config/config.py` and fill in:
```python
MT5_LOGIN    = 12345678        # Your Deriv MT5 account number
MT5_PASSWORD = "YourPassword"  # Your MT5 password
MT5_SERVER   = "Deriv-Demo"    # Keep as Demo until ready for live
```

---

## 📱 Set Up Telegram Alerts (Optional but Recommended)

1. Open Telegram → search "@BotFather"
2. Send: `/newbot`
3. Choose a name (e.g. "My Forex Bot")
4. Copy the TOKEN it gives you
5. Open your new bot, send any message
6. Visit: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
7. Find `"chat":{"id":123456789}` — that's your CHAT_ID
8. Add both to config.py:
```python
TELEGRAM_TOKEN   = "7234567890:AAFxxxxxxxxxx"
TELEGRAM_CHAT_ID = "123456789"
```

---

## 🚀 Running the Bot

### Start the bot:
```
python main.py
```
The bot will:
1. Connect to your MT5 account
2. Ask which markets you want to scan
3. Scan for signals every 5 minutes
4. Send Telegram alert when a signal is found
5. Wait for your APPROVE/REJECT (in SEMI_AUTO mode)

### Start the dashboard:
```
streamlit run dashboard/app.py
```
Open http://localhost:8501 in your browser.

### Run a backtest:
```
python backtest/run_backtest.py
```

---

## 📊 Understanding the Bot's Decisions

### AI Confidence Score
- 65-70%: Acceptable signal (minimum threshold)
- 70-80%: Good signal
- 80-90%: Strong signal
- 90%+:   Very high confidence (rare)

### Risk per Trade on $500
| Risk % | Dollar Risk | Reward (2:1 R:R) |
|--------|-------------|------------------|
| 1%     | $5          | $10              |
| 0.5%   | $2.50       | $5               |
| 2%     | $10         | $20              |

### Symbol Names in Deriv MT5
| What You Know | Deriv MT5 Symbol Name |
|--------------|----------------------|
| Gold         | XAUUSD               |
| EUR/USD      | EURUSD               |
| GBP/USD      | GBPUSD               |
| Volatility 75| Volatility 75 Index  |
| Boom 1000    | Boom 1000 Index      |
| Crash 1000   | Crash 1000 Index     |

---

## ⚠️ IMPORTANT WARNINGS

1. **ALWAYS test on a DEMO account first** (at least 2-4 weeks)
2. **Never risk money you cannot afford to lose**
3. **The bot is NOT 100% accurate** — no bot is
4. **Start with minimum lot sizes** (0.01 lots)
5. **Watch the daily loss limit** (set at 3% = $15/day)
6. **Synthetic indices trade 24/7** — the bot can run overnight

---

## 🛠 File Structure
```
forex_bot/
├── main.py              ← START HERE — runs the bot
├── config/config.py     ← All settings (fill in your details)
├── ai_engine/
│   ├── indicators.py    ← Calculates RSI, MACD, ATR, etc.
│   └── strategy_engine.py ← AI picks the best strategy
├── bridge/
│   └── mt5_connector.py ← Connects to MetaTrader 5
├── strategies/
│   └── strategy_library.py ← All 5 trading strategies
├── risk/
│   └── risk_manager.py  ← Protects your account
├── alerts/
│   └── telegram_alerts.py ← Sends you Telegram messages
├── backtest/
│   └── backtest_engine.py ← Test on historical data
├── dashboard/
│   └── app.py           ← Web monitoring dashboard
└── SETUP_GUIDE.md       ← This file
```

---

## 🆘 Common Problems & Fixes

**"MT5 not installed" error**
→ Install from: https://www.metatrader5.com/en/download
→ MT5 Python library only works on Windows

**"Cannot connect to Deriv-Demo"**
→ Make sure MT5 app is open and logged in first
→ Check your login/password/server in config.py

**"No candle data for symbol"**
→ In MT5: View → Market Watch → right-click → Show All
→ The symbol must be visible in Market Watch

**"Telegram not configured"**
→ Add your TOKEN and CHAT_ID to config.py
→ In SEMI_AUTO mode without Telegram, bot logs signals to console

---

*Built for Deriv.com | MT5 Platform | Version 1.0*

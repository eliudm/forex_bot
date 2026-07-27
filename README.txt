# 🤖 FOREX AI BOT — COMPLETE SETUP GUIDE
# For Deriv MT5 | Written for Beginners

==============================================================
  READ THIS ENTIRE FILE BEFORE TOUCHING ANY CODE
==============================================================

This guide will take you from ZERO to a running trading bot.
Follow every step IN ORDER. Do not skip steps.

Estimated setup time: 45–90 minutes (first time)
──────────────────────────────────────────────────────────────


════════════════════════════════════════════════════════
  STEP 1 — CREATE YOUR DERIV ACCOUNT
════════════════════════════════════════════════════════

1. Go to https://deriv.com and click "Create free account"
2. Complete registration with your email
3. Verify your email address
4. Log in to your Deriv dashboard

IMPORTANT: Start with a DEMO account first!
  - In your Deriv dashboard, look for "DMT5" or "Deriv MT5"
  - Create a "Financial" demo account (for Forex/Gold)
  - Create a "Synthetic Indices" demo account (for Boom/Crash/Volatility)
  - Each gives you virtual money to test the bot safely

You will need from Deriv MT5:
  ✅ Login number  (e.g., 12345678)
  ✅ Password      (you set this when creating MT5 account)
  ✅ Server name   (e.g., "Deriv-Demo" for demo, "Deriv-Server" for live)


════════════════════════════════════════════════════════
  STEP 2 — INSTALL METATRADER 5
════════════════════════════════════════════════════════

1. Go to https://www.metatrader5.com/en/download
2. Download and install MetaTrader 5 for Windows
   (Note: MT5 works best on Windows. On Mac, use Wine or a VPS)

3. Open MetaTrader 5
4. Click File → Login to Trade Account
5. Enter your Deriv MT5 credentials:
   - Login:    your MT5 account number
   - Password: your MT5 password
   - Server:   Deriv-Demo (for demo) or Deriv-Server (for live)

6. Verify you can see prices in the Market Watch panel
   - Press Ctrl+M to show Market Watch
   - Right-click in Market Watch → Show All
   - You should see EURUSD, XAUUSD, Volatility 75 Index, etc.


════════════════════════════════════════════════════════
  STEP 3 — INSTALL PYTHON
════════════════════════════════════════════════════════

The bot's AI engine runs in Python. Here's how to install it:

1. Go to https://www.python.org/downloads/
2. Download Python 3.10 or newer (3.11 recommended)
3. Run the installer

   ⚠️  CRITICAL: On the first install screen, CHECK the box that says
       "Add Python to PATH" before clicking Install Now

4. Verify installation:
   - Open Command Prompt (press Windows + R, type "cmd", press Enter)
   - Type: python --version
   - You should see: Python 3.11.x (or similar)
   - If you see an error, Python was not added to PATH correctly


════════════════════════════════════════════════════════
  STEP 4 — SET UP THE BOT PROJECT
════════════════════════════════════════════════════════

1. Copy this entire "forex_bot" folder to a location you remember
   Example: C:\Users\YourName\forex_bot\

2. Open Command Prompt and navigate to the folder:
   > cd C:\Users\YourName\forex_bot

3. Install required Python packages:
   > pip install -r requirements.txt

   This will install:
   - MetaTrader5  (connects Python to MT5)
   - pandas       (handles data tables)
   - numpy        (math operations)
   - scikit-learn (machine learning)
   - requests     (for Telegram alerts)

   ⏳ This may take 2–5 minutes. Wait for it to finish.

4. Verify MetaTrader5 package works:
   > python -c "import MetaTrader5 as mt5; print('MT5 OK:', mt5.__version__)"
   
   You should see: MT5 OK: 5.0.45 (or similar version)


════════════════════════════════════════════════════════
  STEP 5 — CONFIGURE YOUR CREDENTIALS
════════════════════════════════════════════════════════

1. Open the file: config/settings.py
   (You can open it with Notepad or any text editor)

2. Update these lines with YOUR credentials:

   MT5_LOGIN    = 12345678          ← Your MT5 account number
   MT5_PASSWORD = "your_password"   ← Your MT5 password
   MT5_SERVER   = "Deriv-Demo"      ← "Deriv-Demo" or "Deriv-Server"

3. Set your starting balance:
   ACCOUNT_BALANCE = 10,000            ← Your actual balance

4. KEEP EXECUTION_MODE = "SEMI_AUTO" for now
   (This means the bot asks your permission before each trade)

5. Save the file


════════════════════════════════════════════════════════
  STEP 6 — INSTALL THE MQL5 EXPERT ADVISOR
════════════════════════════════════════════════════════

The Expert Advisor (EA) is a script that runs inside MT5.
It handles trailing stops and break-even automatically.

1. Open MetaTrader 5
2. Press Ctrl+Shift+D to open MetaEditor
3. In MetaEditor: File → New → Expert Advisor (from template)
4. Name it "ForexAIBot"
5. Delete all the default code
6. Open the file: mql5/ForexAIBot.mq5 (from this project)
7. Copy ALL the code and paste it into MetaEditor
8. Press F7 to compile
   - You should see "0 errors, 0 warnings" at the bottom
   - If you see errors, double-check you copied the entire file

9. Go back to MetaTrader 5 main window
10. In the Navigator panel (Ctrl+N), find Expert Advisors → ForexAIBot
11. Drag it onto any chart (e.g., EURUSD H1)
12. In the settings popup:
    - Check "Allow live trading"
    - Click OK

13. Make sure the "Algo Trading" button in the toolbar is GREEN
    (It's the button that looks like a play button with a robot)


════════════════════════════════════════════════════════
  STEP 7 — RUN THE DASHBOARD
════════════════════════════════════════════════════════

The dashboard gives you a visual control panel in your browser.

1. Navigate to the dashboard folder:
   > cd C:\Users\YourName\forex_bot\dashboard

2. Open index.html in your browser
   (Double-click the file, or drag it into Chrome/Firefox)

3. You will see:
   - Account overview cards
   - Market signal table with toggles
   - Bot controls (Start/Stop/Mode)
   - Live activity log
   - Equity curve chart

NOTE: The dashboard currently runs in DEMO MODE (simulated signals).
Full real-time data requires connecting it to the Python backend
(covered in the advanced setup section below).


════════════════════════════════════════════════════════
  STEP 8 — START THE BOT
════════════════════════════════════════════════════════

Make sure MetaTrader 5 is open and logged in FIRST.

1. Open Command Prompt
2. Navigate to the bot folder:
   > cd C:\Users\YourName\forex_bot

3. Start the bot:
   > python main_bot.py

4. You will see a market selection menu:
   ══════════════════════════════════════════
     🤖  FOREX AI BOT - DERIV EDITION
   ══════════════════════════════════════════
   
     SELECT MARKETS TO TRADE:
     (Type numbers separated by commas, e.g.: 1,2,4)
   
       [1] Gold (XAUUSD)
       [2] Forex - Euro/USD
       [3] Forex - GBP/USD
       [4] Deriv Synthetic - Volatility 75
       [5] Deriv Synthetic - Boom 1000
       [6] Deriv Synthetic - Crash 1000
   
       [A] All markets
       [Q] Quit

5. Type your choice (e.g., "1,2" for Gold and EURUSD) and press Enter

6. The bot will:
   - Connect to Deriv MT5
   - Download historical data for each market
   - Train the AI model (takes 10–30 seconds per market)
   - Start scanning every hour

7. When a signal is found (in SEMI_AUTO mode), you'll see:
   ───────────────────────────────────────────────────
     🚨 NEW SIGNAL: 📈 BUY  XAUUSD
   ───────────────────────────────────────────────────
     Confidence :  72%
     Market Regime: STRONG_TREND
     Stop Loss  :  1920.50
     Take Profit:  1935.00
     R:R Ratio  :  1:2.5
     Risk Amount:  $5.00
   ───────────────────────────────────────────────────
     APPROVE? [Y = Yes / N = No]:

8. Type Y to approve or N to reject

To stop the bot at any time: Press Ctrl+C


════════════════════════════════════════════════════════
  STEP 9 — RUN A BACKTEST FIRST (Highly Recommended)
════════════════════════════════════════════════════════

Before trading live, test the strategy on historical data:

1. Open Command Prompt in the bot folder
2. Run:
   > python backtest/backtester.py

3. You will see a performance report like:
   ═══════════════════════════════════════════════════
     📊 BACKTEST RESULTS — XAUUSD
   ═══════════════════════════════════════════════════
     Initial Balance : $500.00
     Final Balance   : $623.50
     Total Return    : +24.70%
     Win Rate        : 63.0%
     Profit Factor   : 1.82
     Sharpe Ratio    : 1.34
     Max Drawdown    : 7.40%
   ═══════════════════════════════════════════════════

WHAT TO LOOK FOR:
   ✅ Win Rate > 55% (good)
   ✅ Profit Factor > 1.5 (good)
   ✅ Max Drawdown < 15% (safe)
   ✅ Sharpe Ratio > 1.0 (good)
   ❌ If any of these look bad, do NOT trade live yet


════════════════════════════════════════════════════════
  STEP 10 — OPTIONAL: TELEGRAM ALERTS SETUP
════════════════════════════════════════════════════════

Get trade alerts directly on your phone!

1. Open Telegram on your phone
2. Search for @BotFather
3. Send: /newbot
4. Follow the prompts, give your bot a name
5. BotFather will give you a TOKEN like:
   110201543:AAHdqTcvCH1vGWJxfSeofSs4tHmvDEGDzB8

6. Search for @userinfobot on Telegram
7. Send: /start
8. It will show your Chat ID like: 987654321

9. Open config/settings.py and update:
   TELEGRAM_ENABLED = True
   TELEGRAM_TOKEN   = "110201543:AAHdqTcvCH1vGWJxfSeofSs4tHmvDEGDzB8"
   TELEGRAM_CHAT_ID = "987654321"


════════════════════════════════════════════════════════
  PROJECT FILE STRUCTURE EXPLAINED
════════════════════════════════════════════════════════

forex_bot/
│
├── main_bot.py              ← START HERE. Run this to start the bot.
│
├── config/
│   └── settings.py          ← YOUR SETTINGS. Edit this first.
│
├── ai_engine/
│   ├── indicators.py        ← Calculates RSI, MACD, EMA, ATR etc.
│   ├── strategy_engine.py   ← AI brain. Generates BUY/SELL signals.
│   └── risk_manager.py      ← Protects your account from big losses.
│
├── bridge/
│   └── mt5_bridge.py        ← Connects Python to Deriv MT5.
│
├── mql5/
│   └── ForexAIBot.mq5       ← Install this inside MetaTrader 5.
│
├── backtest/
│   └── backtester.py        ← Test strategy on historical data.
│
├── alerts/
│   └── telegram_alerts.py   ← Sends alerts to your Telegram.
│
├── dashboard/
│   └── index.html           ← Visual control panel in your browser.
│
├── logs/                    ← All bot activity saved here.
│   └── bot_YYYYMMDD.log
│
├── models/                  ← Trained AI models saved here (auto-created).
│
└── requirements.txt         ← Python packages list.


════════════════════════════════════════════════════════
  TIPS FOR HIGH SUCCESS RATE
════════════════════════════════════════════════════════

1. START ON DEMO ACCOUNT
   Never skip demo testing. Run for at least 2–4 weeks.

2. USE SEMI_AUTO MODE FIRST
   Review every signal. Learn what good signals look like.

3. DON'T CHANGE RISK SETTINGS
   1% per trade with 3% daily limit is designed to protect you.
   Do NOT increase these until you have 3+ months of live data.

4. LET THE AI RETRAIN WEEKLY
   The bot retrains every 7 days automatically. Don't interrupt it.

5. BACKTEST BEFORE GOING LIVE
   Run backtest/backtester.py on each market before enabling it.

6. KEEP MT5 OPEN
   The bot needs MT5 running. Consider a Windows VPS for 24/7 operation.

7. CHECK LOGS DAILY
   Review logs/ folder every morning to see what the bot did overnight.

8. DON'T TRADE DURING MAJOR NEWS
   The bot has a news filter but you should also check the economic
   calendar at https://www.forexfactory.com/calendar

9. FOR SYNTHETIC INDICES (Boom/Crash/Volatility):
   - These trade 24/7 including weekends
   - Volatility 75 moves a LOT — keep risk at 0.5% per trade
   - Boom/Crash have predictable spike patterns — great for AI


════════════════════════════════════════════════════════
  TROUBLESHOOTING
════════════════════════════════════════════════════════

Problem: "MT5 initialize() failed"
Solution: Make sure MetaTrader 5 is OPEN and LOGGED IN before
          running the Python bot.

Problem: "MT5 login failed"
Solution: Double-check MT5_LOGIN, MT5_PASSWORD, MT5_SERVER
          in config/settings.py. Try logging in manually in MT5 first.

Problem: "No data received for [symbol]"
Solution: In MT5, right-click Market Watch → Show All.
          Then right-click the symbol → Chart Window.
          This forces MT5 to load the symbol data.

Problem: "Not enough data to train"
Solution: In MT5, open a chart for that symbol, then Tools →
          History Center → Download more data.

Problem: "pip is not recognized"
Solution: Reinstall Python and make sure to check
          "Add Python to PATH" during installation.

Problem: ModuleNotFoundError: No module named 'MetaTrader5'
Solution: Run: pip install MetaTrader5
          Note: MetaTrader5 Python package only works on Windows.


════════════════════════════════════════════════════════
  SUPPORT AND NEXT STEPS
════════════════════════════════════════════════════════

Once comfortable with the bot, consider these upgrades:

Phase 2 Upgrades:
- Add more currency pairs (USDJPY, USDCAD, AUDUSD)
- Add Crash 500 and Boom 500 (more signals, lower volatility)
- Improve AI with LSTM neural network (needs more data)
- Add web-based dashboard with real-time charts (Flask/Streamlit)
- Deploy to a Windows VPS for 24/7 automated trading

Recommended VPS providers for MT5:
- Contabo (affordable, good for MT5)
- ForexVPS (specialized for trading bots)
- AWS Lightsail (scalable)

══════════════════════════════════════════════════════
  ⚠️  DISCLAIMER
══════════════════════════════════════════════════════
This bot is a tool to assist in trading decisions.
It does NOT guarantee profits. Forex and synthetic
index trading involves significant risk of loss.
Always start with demo money. Never trade with funds
you cannot afford to lose.
══════════════════════════════════════════════════════

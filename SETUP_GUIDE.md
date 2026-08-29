# Setup Guide

## Fastest path: paper trading (no account needed)

```bash
pip install -r requirements.txt
python main.py
```

`config/settings.py` defaults to `BROKER_MODE = "PAPER"`, which uses a
simulated broker (`bridge/paper_broker.py`) with synthetic price data — no
Deriv account, no MetaTrader install, nothing to configure. This is enough
to see the full pipeline (signal → risk check → trade → close → performance
tracking) actually run. It is **not** live market data — treat any paper
results as a pipeline smoke test, not a performance claim.

Pick your markets and execution mode at the prompts, or skip them for
scripted/automated runs:

```bash
BOT_MARKETS=EURUSD,XAUUSD BOT_MAX_SCANS=5 python main.py
```

## Backtesting

```bash
python backtest/run_backtest.py
```

Runs the strategy against synthetic historical data for a handful of
symbols and prints win rate, profit factor, max drawdown, and Sharpe ratio
for each. Past performance — backtested or live — never guarantees future
results.

## Going live: Deriv MT5 account

Only do this after you're comfortable with how the bot behaves in paper
mode.

### 1. Create a Deriv account and demo MT5 login
1. Go to <https://deriv.com> and create a free account, verify your email.
2. In your Deriv dashboard, open **DMT5 / Deriv MT5** and create a demo
   account (Financial, for Forex/Gold; Synthetic Indices, for
   Boom/Crash/Volatility symbols — you can create both).
3. Note the **login number**, **password**, and **server** (e.g.
   `Deriv-Demo`) it gives you.

### 2. Install MetaTrader 5
1. Download from <https://www.metatrader5.com/en/download> (Windows —
   the `MetaTrader5` Python package only works on Windows).
2. Open MT5, **File → Login to Trade Account**, and log in with the
   credentials from step 1.
3. Press `Ctrl+M` for Market Watch, right-click → **Show All** so
   Boom/Crash/Volatility/Step/Jump symbols are visible — the bot can't
   fetch data for a symbol that isn't in Market Watch.

### 3. Install Python dependencies
```bash
pip install -r requirements.txt
pip install MetaTrader5
```

### 4. Configure credentials
Copy `.env.example` to `.env` and fill in your details — **never** put
credentials directly in `config/settings.py`; `.env` is gitignored
specifically so secrets never end up in git history:

```
MT5_LOGIN=12345678
MT5_PASSWORD=your_password
MT5_SERVER=Deriv-Demo
```

Then set `BROKER_MODE = "MT5"` in `config/settings.py`.

### 5. Run it
```bash
python main.py
```
Start with `EXECUTION_MODE = "SEMI_AUTO"` (in `config/settings.py`) so you
approve every trade before it fires. Only move to `FULL_AUTO` after
watching it run correctly on demo for a meaningful stretch of time.

## Telegram alerts (optional)

1. Open Telegram, message **@BotFather**, send `/newbot`, follow the
   prompts, and copy the token it gives you.
2. Message your new bot once (anything).
3. Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` and find
   `"chat":{"id": ...}` — that's your chat ID.
4. Add both to `.env`:
   ```
   TELEGRAM_TOKEN=7234567890:AAFxxxxxxxxxxxxxxxxxxxx
   TELEGRAM_CHAT_ID=123456789
   ```
   Telegram alerts turn on automatically once both are set.

## Dashboard

```bash
python dashboard/server.py
```
Open <http://localhost:5000>. It reads real state from `logs/` (the loss
detector's state file, the signal file the bot writes each scan) — it
shows nothing until the bot has actually run.

## Understanding confidence and risk

| AI Confidence | Meaning                          |
|---------------|-----------------------------------|
| < 55%         | Below the live default threshold — WAIT |
| 55-70%        | Acceptable signal                 |
| 70-85%        | Good signal                       |
| 85%+          | Strong signal (rare)               |

Risk per trade on a $10,000 paper balance at the default 1% risk setting:

| Risk % | Dollar Risk | Reward at 2:1 R:R |
|--------|-------------|--------------------|
| 0.5%   | $50         | $100                |
| 1%     | $100        | $200                |
| 2%     | $200        | $400                |

## Common problems

**"Could not connect to the broker" in MT5 mode**
→ Make sure MT5 is open and logged in, and that `.env` has the right
login/password/server (check the exact spelling of `MT5_SERVER`).

**"No data for <symbol>"**
→ In MT5: View → Market Watch → right-click → Show All. The symbol must
be visible in Market Watch.

**Telegram messages aren't sending**
→ Check `TELEGRAM_TOKEN`/`TELEGRAM_CHAT_ID` in `.env`. With neither set,
alerts print a preview to the console instead of sending — that's
expected, not a bug.

**Console crashes with `UnicodeEncodeError`**
→ Should not happen anymore (`main.py` and `backtest/run_backtest.py`
reconfigure stdout to UTF-8 on startup) — if you hit this in another
script, it's the same root cause: emoji output on a non-UTF-8 Windows
console codepage.

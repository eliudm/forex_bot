# Forex AI Trading Bot

A multi-market trading bot: technical indicators feed an ensemble ML model
(Random Forest + Gradient Boosting + XGBoost) per symbol, signals pass
through a risk manager and a drawdown/loss-streak monitor before anything
gets traded, and a backtester lets you check a strategy's historical
performance before running it live.

It runs out of the box in **paper trading mode** — a simulated broker with
synthetic price data — so you can see the whole pipeline work without a
broker account. Flip a config switch to trade a real Deriv MT5 demo/live
account once you're ready.

No claim of guaranteed profit here, no "it barely needs supervision." It's a
real, working, honestly-labeled trading pipeline you can inspect, test, and
extend. Trading carries real risk of loss — read [SETUP_GUIDE.md](SETUP_GUIDE.md)
before ever pointing this at a live account.

## What it actually does

- Calculates ~15 technical indicators (RSI, MACD, EMA, Bollinger Bands, ATR,
  ADX, Stochastic) plus candlestick pattern and session features
- Trains a per-symbol ensemble classifier (BUY / SELL / WAIT) with
  walk-forward cross-validation
- Applies a risk manager (daily loss limit, max open trades, min
  risk:reward) before any trade is placed
- Tracks drawdown, win/loss streaks, and rolling profit factor, and
  automatically reduces size, raises the confidence bar, or pauses trading
  when performance degrades (`ai_engine/loss_detector.py`)
- Records every trade for later performance reporting, broken down by
  symbol, strategy, session, and market regime
- Optionally sends Telegram alerts, including approve/reject buttons for
  semi-automatic mode

## Project structure
```text
forex_bot/
├── ai_engine/          # indicators, ML signal engine, risk manager, loss detector
├── alerts/             # Telegram alert integration
├── backtest/           # backtesting engine + a synthetic-data demo suite
├── bridge/             # broker interface: PaperBroker (default) and MT5Bridge
├── config/             # settings.py (edit this) + compat.py (internal)
├── dashboard/          # Flask dashboard reading real bot state (logs/*.json)
├── mql5/               # standalone MetaTrader 5 Expert Advisor (separate from the Python bot)
├── tests/              # pytest suite
├── main.py             # entry point — python main.py
└── requirements.txt    # Python dependencies
```

## Quick start (paper trading — no account needed)
```bash
pip install -r requirements.txt
python main.py
```
Pick your markets and mode at the prompts. `BROKER_MODE` defaults to
`PAPER` in `config/settings.py`, so it runs immediately against a
simulated broker with synthetic price data — clearly not a live feed, but
enough to prove every stage of the pipeline (signal → risk check →
execution → close → performance tracking) actually works.

Run the backtest suite (a handful of symbols on synthetic data):
```bash
python backtest/run_backtest.py
```

Run the test suite:
```bash
pip install -r requirements-dev.txt
pytest
```

Start the dashboard (reads real state from `logs/`, not fabricated numbers):
```bash
python dashboard/server.py    # http://localhost:5000
```

## Going live on a real Deriv MT5 account

See [SETUP_GUIDE.md](SETUP_GUIDE.md) for the full walkthrough. In short:
1. `pip install MetaTrader5` (Windows only)
2. Copy `.env.example` to `.env` and fill in your MT5 login/password/server
3. Set `BROKER_MODE = "MT5"` in `config/settings.py`
4. Start on a **demo** account and watch it for at least a few weeks before
   ever considering real money

Never commit `.env` or put credentials directly in `config/settings.py` —
`.env` is gitignored specifically so secrets never end up in source control.

## Recommended workflow
- Prove the pipeline works in PAPER mode first.
- Backtest before touching a real account.
- Move to an MT5 **demo** account and watch it run for weeks.
- Review logs, risk settings, and the loss detector's thresholds before
  ever enabling `FULL_AUTO` on real money.

## Notes
- This project is for learning, testing, and experimentation.
- Trading financial markets carries real risk of loss.
- Past performance — backtested or live — does not guarantee future results.

## License
This project is provided as-is for educational and experimental use.

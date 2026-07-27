# Forex AI Trading Bot

This repository contains an AI-assisted trading bot for Deriv MetaTrader 5 workflows. It is designed to scan multiple markets, generate trading signals, apply risk controls, and optionally send Telegram alerts.

## What the bot does
- Connects to a Deriv MT5 environment
- Scans forex, commodities, synthetic indices, and crypto markets
- Uses rule-based and AI-assisted signal generation
- Supports semi-auto approval and full-auto execution modes
- Includes backtesting and logging components
- Sends alerts for high-confidence trading opportunities

## Project structure
```text
forex_bot/
├── ai_engine/          # signal generation, indicators, risk, loss detection
├── alerts/             # Telegram alert integration
├── backtest/           # backtesting engine and scripts
├── bridge/             # MT5 bridge and connector logic
├── config/             # configuration and settings
├── dashboard/          # optional dashboard assets
├── logs/               # runtime logs and state files
├── models/             # trained model artifacts
├── risk/               # risk-related utilities
├── strategies/         # strategy definitions
├── utils/              # logging and helper utilities
├── main.py             # main entry point
├── main_bot.py         # bot orchestration entry point
└── requirements.txt    # Python dependencies
```

## Quick start
1. Install Python 3.10+ and ensure it is available on your PATH.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure your broker and bot settings in the configuration files under the config folder.
4. Start the bot:
   ```bash
   python main.py
   ```
   or
   ```bash
   python main_bot.py
   ```

## Recommended workflow
- Start with demo trading only.
- Run the backtest module before live execution.
- Review logs and risk settings before enabling auto execution.
- Keep Telegram and risk limits configured carefully.

## Notes
- This project is intended for learning, testing, and experimentation.
- Trading financial markets carries real risk of loss.
- Past performance does not guarantee future results.

## License
This project is provided as-is for educational and experimental use.

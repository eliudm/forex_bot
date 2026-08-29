"""Compatibility helpers for shared runtime settings across entry points."""

from __future__ import annotations

import os
from typing import Any, Dict

try:
    from config.settings import (
        ACCOUNT_BALANCE,
        RISK_PER_TRADE_PCT,
        MAX_OPEN_TRADES,
        DAILY_LOSS_LIMIT_PCT,
        MIN_REWARD_RISK_RATIO,
        PRIMARY_TIMEFRAME,
        LOOKBACK_CANDLES,
        MIN_SIGNAL_CONFIDENCE,
        EXECUTION_MODE,
        RETRAIN_EVERY_DAYS,
        TELEGRAM_ENABLED,
        BROKER_MODE,
    )
except Exception:  # pragma: no cover - fallback for local/dev use
    ACCOUNT_BALANCE = 10000
    RISK_PER_TRADE_PCT = 0.01
    MAX_OPEN_TRADES = 5
    DAILY_LOSS_LIMIT_PCT = 0.03
    MIN_REWARD_RISK_RATIO = 2.0
    PRIMARY_TIMEFRAME = "H1"
    LOOKBACK_CANDLES = 200
    MIN_SIGNAL_CONFIDENCE = 0.55
    EXECUTION_MODE = "FULL_AUTO"
    RETRAIN_EVERY_DAYS = 7
    TELEGRAM_ENABLED = False
    BROKER_MODE = "PAPER"


def get_runtime_config() -> Dict[str, Any]:
    """Return a normalized runtime config dictionary for bot entry points."""
    return {
        "account_balance": float(ACCOUNT_BALANCE),
        "risk_per_trade_pct": float(RISK_PER_TRADE_PCT),
        "max_open_trades": int(MAX_OPEN_TRADES),
        "daily_loss_limit_pct": float(DAILY_LOSS_LIMIT_PCT),
        "min_reward_risk_ratio": float(MIN_REWARD_RISK_RATIO),
        "primary_timeframe": PRIMARY_TIMEFRAME,
        "lookback_candles": int(LOOKBACK_CANDLES),
        "min_signal_confidence": float(MIN_SIGNAL_CONFIDENCE),
        "execution_mode": EXECUTION_MODE,
        "retrain_every_days": int(RETRAIN_EVERY_DAYS),
        "telegram_enabled": bool(TELEGRAM_ENABLED),
        "broker_mode": BROKER_MODE,
        "workspace_root": os.path.abspath(os.path.dirname(os.path.dirname(__file__))),
    }

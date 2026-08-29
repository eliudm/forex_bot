"""
bridge/__init__.py — Broker factory

Returns the broker implementation selected by BROKER_MODE in
config/settings.py ("PAPER" by default, "MT5" for a real Deriv account).
Both implementations expose the same interface: connect, disconnect,
get_candles, get_price, get_account, calculate_lot_size, place_trade,
get_open_positions, close_trade, tick, get_closed_trades.

MT5Bridge is imported lazily so that PAPER mode (the default) never
requires the MetaTrader5 package to be installed.
"""

from config.compat import get_runtime_config


def get_bridge():
    mode = get_runtime_config().get("broker_mode", "PAPER")
    if mode == "MT5":
        from bridge.mt5_bridge import MT5Bridge
        return MT5Bridge()
    from bridge.paper_broker import PaperBroker
    return PaperBroker()

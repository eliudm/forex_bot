"""
Regression test for a real money-losing bug: MT5Bridge.calculate_lot_size()
used to treat info.trade_tick_value (the $ value of one TICK per lot) as if
it were the $ value of one PIP per lot. On a standard 5-digit-quoted forex
symbol, 1 pip = 10 ticks, so this inflated every computed lot size ~10x —
risking roughly 10x the intended amount on every live trade.

No real MT5 terminal is available in CI/dev, but mt5.symbol_info() is a pure
data lookup we can fake — importing bridge.mt5_bridge only needs the
MetaTrader5 *package* installed, not a running terminal.
"""
from types import SimpleNamespace
from unittest.mock import patch

from bridge.mt5_bridge import MT5Bridge


def _fake_symbol_info(tick_value, tick_size, volume_min=0.01, volume_max=50.0, volume_step=0.01):
    return SimpleNamespace(
        trade_tick_value=tick_value, trade_tick_size=tick_size,
        volume_min=volume_min, volume_max=volume_max, volume_step=volume_step,
    )


def test_lot_size_uses_pip_value_not_raw_tick_value():
    # EURUSD, 5-digit quoting: tick_size=0.00001, tick_value ~$1/lot/tick.
    # True pip value (10 ticks) is ~$10/lot/pip.
    bridge = MT5Bridge()
    with patch("bridge.mt5_bridge.mt5.symbol_info",
               return_value=_fake_symbol_info(tick_value=1.0, tick_size=0.00001)):
        lot = bridge.calculate_lot_size("EURUSD", sl_pips=20, risk_pct=0.01, balance=10000)

    # risk_amount = $100; correct pip_value = $10/lot -> lot = 100 / (20*10) = 0.5
    assert lot == 0.5, f"expected 0.5 lots (10x-bug would give 5.0), got {lot}"


def test_lot_size_respects_broker_min_and_max():
    bridge = MT5Bridge()
    with patch("bridge.mt5_bridge.mt5.symbol_info",
               return_value=_fake_symbol_info(tick_value=1.0, tick_size=0.00001,
                                               volume_min=0.1, volume_max=1.0)):
        # Tiny risk that would compute below volume_min
        lot = bridge.calculate_lot_size("EURUSD", sl_pips=20, risk_pct=0.0001, balance=100)
        assert lot == 0.1

        # Huge risk that would compute above volume_max
        lot = bridge.calculate_lot_size("EURUSD", sl_pips=1, risk_pct=0.5, balance=1_000_000)
        assert lot == 1.0

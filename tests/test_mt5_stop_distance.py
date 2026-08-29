from types import SimpleNamespace
from unittest.mock import patch

from bridge.mt5_bridge import MT5Bridge


def _fake_info(trade_stops_level=100, point=0.00001):
    return SimpleNamespace(trade_stops_level=trade_stops_level, point=point)


def test_widens_a_buy_stop_that_is_too_close():
    bridge = MT5Bridge()
    price = 1.08500
    # min_distance = 100 * 0.00001 = 0.001; both SL and TP are far too tight
    with patch("bridge.mt5_bridge.mt5.symbol_info", return_value=_fake_info()):
        sl, tp = bridge._enforce_min_stop_distance("EURUSD", "BUY", price, sl=1.08490, tp=1.08505)

    assert sl <= price - 0.001
    assert tp >= price + 0.001


def test_widens_a_sell_stop_that_is_too_close():
    bridge = MT5Bridge()
    price = 1.08500
    with patch("bridge.mt5_bridge.mt5.symbol_info", return_value=_fake_info()):
        sl, tp = bridge._enforce_min_stop_distance("EURUSD", "SELL", price, sl=1.08505, tp=1.08495)

    assert sl >= price + 0.001
    assert tp <= price - 0.001


def test_leaves_stops_untouched_when_already_far_enough():
    bridge = MT5Bridge()
    price = 1.08500
    original_sl, original_tp = 1.08000, 1.09000
    with patch("bridge.mt5_bridge.mt5.symbol_info", return_value=_fake_info()):
        sl, tp = bridge._enforce_min_stop_distance("EURUSD", "BUY", price, sl=original_sl, tp=original_tp)

    assert sl == original_sl
    assert tp == original_tp


def test_no_op_when_broker_reports_no_minimum():
    bridge = MT5Bridge()
    with patch("bridge.mt5_bridge.mt5.symbol_info", return_value=_fake_info(trade_stops_level=0)):
        sl, tp = bridge._enforce_min_stop_distance("EURUSD", "BUY", 1.0850, sl=1.08499, tp=1.08501)

    assert (sl, tp) == (1.08499, 1.08501)

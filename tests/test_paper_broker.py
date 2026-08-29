import os

from bridge.paper_broker import PaperBroker


def _broker(tmp_path):
    return PaperBroker(state_path=str(tmp_path / "paper_state.json"))


def test_connect_and_get_candles(tmp_path):
    b = _broker(tmp_path)
    assert b.connect() is True

    df = b.get_candles("EURUSD", "H1", 250)
    assert len(df) == 250
    assert list(df.columns) == ["time", "open", "high", "low", "close", "volume"]


def test_place_trade_appears_in_open_positions(tmp_path):
    b = _broker(tmp_path)
    b.connect()
    price = b.get_price("EURUSD")

    trade = b.place_trade("EURUSD", "BUY", 0.1,
                           sl=price["ask"] - 0.001, tp=price["ask"] + 0.001)
    assert trade["ticket"] > 0

    open_positions = b.get_open_positions()
    assert len(open_positions) == 1
    assert open_positions[0]["ticket"] == trade["ticket"]


def test_tick_settles_trade_and_updates_balance(tmp_path):
    b = _broker(tmp_path)
    b.connect()
    starting_balance = b.get_account()["balance"]
    price = b.get_price("EURUSD")

    # SL set just below price so it fills almost immediately regardless of drift
    b.place_trade("EURUSD", "BUY", 0.1, sl=price["ask"] - 0.0002, tp=price["ask"] + 0.05)

    closures = []
    for _ in range(500):
        b.tick()
        closures = b.get_closed_trades()
        if closures:
            break

    assert closures, "expected the position to close within 500 simulated bars"
    assert b.get_open_positions() == []
    assert b.get_account()["balance"] == starting_balance + closures[0]["profit"]


def test_state_persists_across_instances(tmp_path):
    path = str(tmp_path / "state.json")
    b1 = PaperBroker(state_path=path)
    b1.connect()
    price = b1.get_price("XAUUSD")
    b1.place_trade("XAUUSD", "SELL", 0.5, sl=price["bid"] + 5, tp=price["bid"] - 5)
    b1.disconnect()

    b2 = PaperBroker(state_path=path)
    assert len(b2.get_open_positions()) == 1

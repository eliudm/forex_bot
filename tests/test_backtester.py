import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backtest"))

from run_backtest import generate_sample_data
from backtester import Backtester


def test_backtest_runs_end_to_end_and_produces_metrics():
    # XAUUSD/n=800/min_confidence=0.45 is the exact combination run_backtest.py
    # uses by default, and is known (deterministically, given the per-symbol
    # seeded RNG) to clear the confidence bar and produce trades.
    df = generate_sample_data(n=800, symbol="XAUUSD")
    bt = Backtester(symbol="XAUUSD", initial_balance=500, risk_pct=0.01, min_confidence=0.45)
    bt.load_data(df)

    result = bt.run(train_pct=0.7)

    assert "error" not in result, result.get("error")
    assert result["total_trades"] > 0
    assert set(result) >= {"win_rate", "profit_factor", "max_drawdown_pct", "sharpe_ratio"}


def test_two_different_symbols_get_different_data():
    """Regression test: generate_sample_data() used to reseed with a fixed
    constant, making every symbol's synthetic series identical apart from
    a price-scale factor."""
    a = generate_sample_data(n=200, symbol="EURUSD")
    b = generate_sample_data(n=200, symbol="XAUUSD")

    a_returns = a["close"].pct_change().dropna().round(6)
    b_returns = b["close"].pct_change().dropna().round(6)
    assert not a_returns.equals(b_returns)

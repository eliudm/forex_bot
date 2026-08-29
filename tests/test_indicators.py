import numpy as np
import pandas as pd

from ai_engine.indicators import IndicatorEngine


def _sample_ohlcv(n=300):
    rng = np.random.default_rng(1)
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    return pd.DataFrame({
        "time":   pd.date_range("2024-01-01", periods=n, freq="h"),
        "open":   close + rng.normal(0, 0.1, n),
        "high":   close + np.abs(rng.normal(0.3, 0.1, n)),
        "low":    close - np.abs(rng.normal(0.3, 0.1, n)),
        "close":  close,
        "volume": rng.integers(100, 5000, n).astype(float),
    })


def test_add_all_produces_expected_columns_with_no_nans():
    df = IndicatorEngine().add_all(_sample_ohlcv())

    expected = {"ema20", "ema50", "ema200", "rsi", "macd_line", "macd_signal",
                "bb_upper", "bb_lower", "atr", "adx", "stoch_k", "stoch_d"}
    assert expected.issubset(df.columns)
    assert len(df) > 0
    assert not df[list(expected)].isna().any().any()


def test_rsi_stays_within_0_100():
    df = IndicatorEngine().add_all(_sample_ohlcv())
    assert df["rsi"].between(0, 100).all()

import importlib


def test_runtime_config_exposes_expected_values():
    compat = importlib.import_module("config.compat")
    settings = compat.get_runtime_config()

    assert settings["execution_mode"] in {"SEMI_AUTO", "FULL_AUTO", "BACKTEST"}
    assert settings["risk_per_trade_pct"] > 0
    assert settings["max_open_trades"] >= 1
    assert settings["min_signal_confidence"] >= 0.0

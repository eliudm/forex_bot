from alerts.telegram_alerts import TelegramAlerts


def test_unconfigured_alerts_dont_raise(capsys):
    """With no token/chat id set, sends should no-op (print a preview) rather than crash."""
    alerts = TelegramAlerts()
    alerts.token = ""
    alerts.chat_id = ""

    assert alerts.send("hello") is False
    assert alerts.send_trade_opened({"symbol": "EURUSD", "direction": "BUY",
                                      "price": 1.085, "sl": 1.08, "tp": 1.09,
                                      "lot": 0.1, "ticket": 1}) is False
    assert alerts.send_trade_closed({"symbol": "EURUSD", "profit": 5.0, "ticket": 1}) is False

    out = capsys.readouterr().out
    assert "hello" in out

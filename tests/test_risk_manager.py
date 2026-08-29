from ai_engine.risk_manager import RiskManager


def _account(balance=10000):
    return {"balance": balance, "equity": balance, "margin_free": balance}


def test_daily_loss_survives_a_restart(tmp_path):
    """
    Regression test: RiskManager used to track daily_loss purely in memory.
    If the process restarted mid-day (crash, update, connectivity drop) after
    already hitting losses, the daily loss limit silently forgot them and
    would let the account lose the full daily limit AGAIN on top of that.
    """
    state_path = str(tmp_path / "risk_state.json")

    rm1 = RiskManager(balance=10000, daily_loss_pct=0.03, state_path=state_path)
    rm1.record_trade_result(-250)  # most of the 3% ($300) daily limit already used

    rm2 = RiskManager(balance=10000, daily_loss_pct=0.03, state_path=state_path)
    assert rm2.daily_loss == 250

    signal = {"rr_ratio": 2.0, "confidence": 0.8}
    result = rm2.check_trade(signal, open_positions=[], account=_account())
    assert result["approved"] is True  # $250 of $300 used, still under the limit

    rm2.record_trade_result(-60)  # now $310 lost total -> over the $300 (3%) limit
    result = rm2.check_trade(signal, open_positions=[], account=_account())
    assert result["approved"] is False
    assert "Daily loss limit" in result["reason"]


def test_stale_state_from_a_previous_day_is_ignored(tmp_path):
    import json
    from datetime import date, timedelta

    state_path = str(tmp_path / "risk_state.json")
    with open(state_path, "w") as f:
        json.dump({
            "daily_loss": 999,
            "daily_trades": [],
            "last_reset_date": (date.today() - timedelta(days=1)).isoformat(),
        }, f)

    rm = RiskManager(balance=10000, state_path=state_path)
    assert rm.daily_loss == 0.0  # yesterday's loss must not carry over

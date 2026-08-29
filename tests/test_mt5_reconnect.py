import json
from datetime import datetime, timedelta
from unittest.mock import patch

from bridge.mt5_bridge import MT5Bridge


# ── history watermark persistence ───────────────────────────────────

def test_watermark_defaults_to_now_when_no_state_file(tmp_path):
    before = datetime.now()
    bridge = MT5Bridge(history_state_path=str(tmp_path / "state.json"))
    assert bridge._last_history_check >= before


def test_watermark_survives_a_restart(tmp_path):
    path = str(tmp_path / "state.json")
    b1 = MT5Bridge(history_state_path=path)
    checkpoint = datetime.now() - timedelta(hours=3)
    b1._last_history_check = checkpoint
    b1._save_history_watermark()

    b2 = MT5Bridge(history_state_path=path)
    assert abs((b2._last_history_check - checkpoint).total_seconds()) < 1


def test_stale_watermark_is_capped_not_used_verbatim(tmp_path):
    """
    Regression scenario: a bot left offline for months shouldn't silently
    try to query months of history — cap the lookback and say so, rather
    than either crashing on a huge query or (worse) missing the cap and
    silently skipping everything before it.
    """
    path = str(tmp_path / "state.json")
    ancient = datetime.now() - timedelta(days=90)
    with open(path, "w") as f:
        json.dump({"last_history_check": ancient.isoformat()}, f)

    bridge = MT5Bridge(history_state_path=path)
    floor = datetime.now() - timedelta(days=MT5Bridge.MAX_HISTORY_LOOKBACK_DAYS)
    assert bridge._last_history_check >= floor - timedelta(seconds=5)
    assert bridge._last_history_check > ancient


def test_get_closed_trades_persists_the_new_watermark(tmp_path):
    path = str(tmp_path / "state.json")
    bridge = MT5Bridge(history_state_path=path)

    with patch("bridge.mt5_bridge.mt5.history_deals_get", return_value=None):
        bridge.get_closed_trades()

    with open(path) as f:
        saved = json.load(f)
    assert "last_history_check" in saved


# ── self-healing reconnect ───────────────────────────────────────────

def test_ensure_connected_is_a_noop_when_already_healthy(tmp_path):
    bridge = MT5Bridge(history_state_path=str(tmp_path / "state.json"))
    with patch("bridge.mt5_bridge.mt5.terminal_info", return_value=object()), \
         patch("bridge.mt5_bridge.mt5.account_info", return_value=object()), \
         patch.object(bridge, "connect") as mock_connect:
        assert bridge.ensure_connected() is True
        mock_connect.assert_not_called()


def test_ensure_connected_reconnects_when_terminal_info_is_none(tmp_path):
    bridge = MT5Bridge(history_state_path=str(tmp_path / "state.json"))
    with patch("bridge.mt5_bridge.mt5.terminal_info", return_value=None), \
         patch.object(bridge, "connect", return_value=True) as mock_connect:
        assert bridge.ensure_connected() is True
        mock_connect.assert_called_once()


def test_ensure_connected_reports_failure_when_reconnect_fails(tmp_path):
    bridge = MT5Bridge(history_state_path=str(tmp_path / "state.json"))
    with patch("bridge.mt5_bridge.mt5.terminal_info", return_value=None), \
         patch.object(bridge, "connect", return_value=False):
        assert bridge.ensure_connected() is False

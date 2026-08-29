from ai_engine.loss_detector import LossDetector, BotStatus


def _detector(tmp_path, base_min_confidence=0.55):
    return LossDetector(
        initial_balance=10000,
        save_path=str(tmp_path / "loss_detector_state.json"),
        base_min_confidence=base_min_confidence,
    )


def test_normal_status_uses_the_configured_base_confidence(tmp_path):
    """
    Regression test: NORMAL status used to hardcode min_confidence=0.65
    regardless of config.settings.MIN_SIGNAL_CONFIDENCE, so the number
    main.py's startup banner displayed ("Confidence threshold: 55%") never
    matched what was actually enforced.
    """
    d = _detector(tmp_path, base_min_confidence=0.55)
    adj = d.get_trade_adjustments()
    assert adj["status"] == "NORMAL"
    assert adj["min_confidence"] == 0.55


def test_caution_and_recovery_escalate_relative_to_the_base(tmp_path):
    d = _detector(tmp_path, base_min_confidence=0.55)

    d.status = BotStatus.CAUTION
    assert abs(d.get_trade_adjustments()["min_confidence"] - 0.58) < 1e-9

    d.status = BotStatus.RECOVERY
    assert abs(d.get_trade_adjustments()["min_confidence"] - 0.65) < 1e-9


def test_paused_and_emergency_block_trading_regardless_of_base(tmp_path):
    d = _detector(tmp_path, base_min_confidence=0.55)

    d.status = BotStatus.PAUSED
    assert d.get_trade_adjustments()["can_trade"] is False

    d.status = BotStatus.EMERGENCY
    assert d.get_trade_adjustments()["can_trade"] is False

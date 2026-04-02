from app.core.risk import RiskManager


def test_risk_manager_initial_state():
    rm = RiskManager()
    can_trade, reason = rm.can_trade()
    assert can_trade is True
    assert reason == "OK"
    assert rm.consecutive_losses == 0
    assert rm.daily_pnl == 0.0
    assert rm.is_paused is False


def test_risk_manager_pause_blocks_trading():
    rm = RiskManager()
    rm.pause()
    can_trade, reason = rm.can_trade()
    assert can_trade is False
    assert "paused" in reason.lower()


def test_risk_manager_resume():
    rm = RiskManager()
    rm.pause()
    rm.resume()
    can_trade, _ = rm.can_trade()
    assert can_trade is True


def test_risk_manager_consecutive_losses():
    rm = RiskManager()
    rm.record_trade(-1.0)
    rm.record_trade(-1.0)
    rm.record_trade(-1.0)
    # max_consecutive_losses defaults to 3
    can_trade, reason = rm.can_trade()
    assert can_trade is False
    assert "consecutive" in reason.lower()


def test_risk_manager_consecutive_losses_reset_on_win():
    rm = RiskManager()
    rm.record_trade(-1.0)
    rm.record_trade(-1.0)
    rm.record_trade(0.5)  # Win resets counter
    assert rm.consecutive_losses == 0
    can_trade, _ = rm.can_trade()
    assert can_trade is True


def test_risk_manager_daily_pnl():
    rm = RiskManager()
    rm.record_trade(1.0)
    rm.record_trade(-0.5)
    assert rm.daily_pnl == 0.5
    # Last trade was a loss
    assert rm.consecutive_losses == 1


def test_risk_manager_reset_daily():
    rm = RiskManager()
    rm.record_trade(-1.0)
    rm.record_trade(-1.0)
    rm.pause()
    rm.reset_daily()
    assert rm.daily_pnl == 0.0
    assert rm.consecutive_losses == 0
    assert rm.is_paused is False

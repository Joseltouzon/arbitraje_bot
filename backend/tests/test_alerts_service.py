import pytest

from app.services.alerts import AlertType, AlertsService


def test_alerts_service_initial_state():
    service = AlertsService()
    assert len(service._alerts) == 0
    assert service._counter == 0


def test_add_alert():
    service = AlertsService()
    alert = service.add(AlertType.ERROR, "Test error", {"key": "value"})

    assert alert.id == 1
    assert alert.type == AlertType.ERROR
    assert alert.message == "Test error"
    assert alert.details == {"key": "value"}


def test_error_shortcut():
    service = AlertsService()
    alert = service.error("Error message", code=500)

    assert alert.type == AlertType.ERROR
    assert alert.message == "Error message"
    assert alert.details == {"code": 500}


def test_warning_shortcut():
    service = AlertsService()
    alert = service.warning("Warning message", pair="BTCUSDT")

    assert alert.type == AlertType.WARNING
    assert alert.message == "Warning message"
    assert alert.details == {"pair": "BTCUSDT"}


def test_circuit_breaker_shortcut():
    service = AlertsService()
    alert = service.circuit_breaker("Circuit breaker", errors=5, timeout=60)

    assert alert.type == AlertType.CIRCUIT_BREAKER
    assert alert.details == {"errors": 5, "timeout": 60}


def test_trade_failed_shortcut():
    service = AlertsService()
    alert = service.trade_failed("Trade failed", currencies=["USDT", "BTC", "ETH"])

    assert alert.type == AlertType.TRADE_FAILED
    assert alert.details == {"currencies": ["USDT", "BTC", "ETH"]}


def test_trade_success_shortcut():
    service = AlertsService()
    alert = service.trade_success("Trade success", profit=1.5, profit_pct=0.5)

    assert alert.type == AlertType.TRADE_SUCCESS
    assert alert.details == {"profit": 1.5, "profit_pct": 0.5}


def test_info_shortcut():
    service = AlertsService()
    alert = service.info("Info message")

    assert alert.type == AlertType.INFO
    assert alert.message == "Info message"


def test_get_all_returns_reversed():
    service = AlertsService()
    service.error("Error 1")
    service.warning("Warning 1")
    service.error("Error 2")

    alerts = service.get_all()
    assert len(alerts) == 3
    assert alerts[0]["message"] == "Error 2"
    assert alerts[-1]["message"] == "Error 1"


def test_get_by_type():
    service = AlertsService()
    service.error("Error 1")
    service.warning("Warning 1")
    service.error("Error 2")

    errors = service.get_by_type(AlertType.ERROR)
    assert len(errors) == 2
    assert all(a["type"] == "error" for a in errors)


def test_get_recent():
    service = AlertsService()
    for i in range(25):
        service.info(f"Message {i}")

    recent = service.get_recent(5)
    assert len(recent) == 5


def test_clear():
    service = AlertsService()
    service.error("Error")
    service.warning("Warning")

    assert len(service._alerts) == 2
    service.clear()
    assert len(service._alerts) == 0


def test_count():
    service = AlertsService()
    service.error("E1")
    service.error("E2")
    service.warning("W1")
    service.circuit_breaker("CB1")

    counts = service.count()
    assert counts[AlertType.ERROR] == 2
    assert counts[AlertType.WARNING] == 1
    assert counts[AlertType.CIRCUIT_BREAKER] == 1
    assert counts[AlertType.INFO] == 0


def test_max_capacity():
    service = AlertsService()
    for i in range(105):
        service.info(f"Message {i}")

    assert len(service._alerts) == 100


def test_to_dict_format():
    service = AlertsService()
    alert = service.error("Test error", code=500)

    d = service._to_dict(alert)
    assert "id" in d
    assert d["type"] == "error"
    assert d["message"] == "Test error"
    assert d["details"] == {"code": 500}
    assert "timestamp" in d

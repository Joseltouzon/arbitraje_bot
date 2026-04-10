import pytest
from fastapi.testclient import TestClient

from app.services.alerts import alerts_service


@pytest.fixture(autouse=True)
def clear_alerts():
    alerts_service.clear()
    yield
    alerts_service.clear()


class TestAlertsRoute:
    def test_get_alerts_empty(self, client: TestClient):
        response = client.get("/api/alerts/")
        assert response.status_code == 200
        data = response.json()
        assert data["alerts"] == []
        assert data["total"] == 0

    def test_get_alerts_with_data(self, client: TestClient):
        alerts_service.error("Test error")
        alerts_service.warning("Test warning")

        response = client.get("/api/alerts/")
        assert response.status_code == 200
        data = response.json()
        assert len(data["alerts"]) == 2
        assert data["total"] == 2

    def test_get_alerts_with_limit(self, client: TestClient):
        for i in range(10):
            alerts_service.info(f"Info {i}")

        response = client.get("/api/alerts/?limit=3")
        assert response.status_code == 200
        data = response.json()
        assert len(data["alerts"]) == 3

    def test_get_alerts_filter_by_type(self, client: TestClient):
        alerts_service.error("Error 1")
        alerts_service.warning("Warning 1")
        alerts_service.error("Error 2")

        response = client.get("/api/alerts/?alert_type=error")
        assert response.status_code == 200
        data = response.json()
        assert len(data["alerts"]) == 2
        assert all(a["type"] == "error" for a in data["alerts"])

    def test_get_alerts_invalid_type_returns_all(self, client: TestClient):
        alerts_service.error("Error 1")
        alerts_service.warning("Warning 1")

        response = client.get("/api/alerts/?alert_type=invalid")
        assert response.status_code == 200
        data = response.json()
        assert len(data["alerts"]) == 2

    def test_get_alerts_returns_count(self, client: TestClient):
        alerts_service.error("Error 1")
        alerts_service.warning("Warning 1")
        alerts_service.circuit_breaker("CB 1")

        response = client.get("/api/alerts/")
        data = response.json()
        assert "count" in data
        assert data["count"]["error"] == 1
        assert data["count"]["warning"] == 1
        assert data["count"]["circuit_breaker"] == 1

    def test_clear_alerts(self, client: TestClient):
        alerts_service.error("Error 1")
        alerts_service.warning("Warning 1")

        response = client.post("/api/alerts/clear")
        assert response.status_code == 200
        assert response.json()["status"] == "cleared"

        get_response = client.get("/api/alerts/")
        assert get_response.json()["total"] == 0

    def test_get_alert_types(self, client: TestClient):
        response = client.get("/api/alerts/types")
        assert response.status_code == 200
        data = response.json()
        assert "types" in data
        types = data["types"]
        assert len(types) == 6
        type_values = [t["value"] for t in types]
        assert "error" in type_values
        assert "warning" in type_values
        assert "circuit_breaker" in type_values
        assert "trade_failed" in type_values
        assert "trade_success" in type_values
        assert "info" in type_values

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class AlertType(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    CIRCUIT_BREAKER = "circuit_breaker"
    TRADE_FAILED = "trade_failed"
    TRADE_SUCCESS = "trade_success"
    INFO = "info"


@dataclass
class Alert:
    id: int
    type: AlertType
    message: str
    details: dict[str, Any] | None = None
    timestamp: datetime = field(default_factory=datetime.now)


class AlertsService:
    MAX_ALERTS = 100

    def __init__(self) -> None:
        self._alerts: deque[Alert] = deque(maxlen=self.MAX_ALERTS)
        self._counter = 0

    def add(
        self,
        alert_type: AlertType,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> Alert:
        self._counter += 1
        alert = Alert(
            id=self._counter,
            type=alert_type,
            message=message,
            details=details,
        )
        self._alerts.append(alert)
        return alert

    def error(self, message: str, **kwargs: Any) -> Alert:
        return self.add(AlertType.ERROR, message, kwargs)

    def warning(self, message: str, **kwargs: Any) -> Alert:
        return self.add(AlertType.WARNING, message, kwargs)

    def circuit_breaker(self, message: str, **kwargs: Any) -> Alert:
        return self.add(AlertType.CIRCUIT_BREAKER, message, kwargs)

    def trade_failed(self, message: str, **kwargs: Any) -> Alert:
        return self.add(AlertType.TRADE_FAILED, message, kwargs)

    def trade_success(self, message: str, **kwargs: Any) -> Alert:
        return self.add(AlertType.TRADE_SUCCESS, message, kwargs)

    def info(self, message: str, **kwargs: Any) -> Alert:
        return self.add(AlertType.INFO, message, kwargs)

    def get_all(self) -> list[dict[str, Any]]:
        return [self._to_dict(a) for a in reversed(self._alerts)]

    def get_by_type(self, alert_type: AlertType) -> list[dict[str, Any]]:
        return [self._to_dict(a) for a in reversed(self._alerts) if a.type == alert_type]

    def get_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        return [self._to_dict(a) for a in list(reversed(self._alerts))[-limit:]]

    def clear(self) -> None:
        self._alerts.clear()

    def count(self) -> dict[AlertType, int]:
        counts: dict[AlertType, int] = {t: 0 for t in AlertType}
        for alert in self._alerts:
            counts[alert.type] += 1
        return counts

    @staticmethod
    def _to_dict(alert: Alert) -> dict[str, Any]:
        return {
            "id": alert.id,
            "type": alert.type.value,
            "message": alert.message,
            "details": alert.details,
            "timestamp": alert.timestamp.isoformat(),
        }


alerts_service = AlertsService()

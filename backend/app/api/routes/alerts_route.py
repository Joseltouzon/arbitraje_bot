from fastapi import APIRouter, Query

from app.services.alerts import AlertType, alerts_service

router = APIRouter()


@router.get("/")
async def get_alerts(
    limit: int = Query(default=20, ge=1, le=100),
    alert_type: str | None = None,
) -> dict:
    if alert_type:
        try:
            at = AlertType(alert_type)
            alerts = alerts_service.get_by_type(at)
        except ValueError:
            alerts = alerts_service.get_recent(limit)
    else:
        alerts = alerts_service.get_recent(limit)

    return {
        "alerts": alerts,
        "count": alerts_service.count(),
        "total": len(alerts_service._alerts),
    }


@router.post("/clear")
async def clear_alerts() -> dict:
    alerts_service.clear()
    return {"status": "cleared"}


@router.get("/types")
async def get_alert_types() -> dict:
    return {
        "types": [{"value": t.value, "label": t.value.replace("_", " ").title()} for t in AlertType]
    }

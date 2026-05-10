"""/api/v1/metrics 路由。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ...service import ControlPlaneService
from ..deps import get_service

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/catalog")
def catalog(service: ControlPlaneService = Depends(get_service)) -> dict[str, Any]:
    return {"ok": True, **service.metric_catalog_view()}


@router.get("/live")
def live_metrics(service: ControlPlaneService = Depends(get_service)) -> dict[str, Any]:
    view = service.metric_catalog_view()
    return {"ok": True, "metrics": view.get("liveMetrics", [])}


@router.post("/catalog/sync")
def sync_metric_metadata(service: ControlPlaneService = Depends(get_service)) -> dict[str, Any]:
    return service.sync_metric_metadata()

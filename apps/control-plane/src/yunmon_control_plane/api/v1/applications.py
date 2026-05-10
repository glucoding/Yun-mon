"""/api/v1/applications 路由。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ...service import ControlPlaneService
from ..deps import get_service

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("/discovery")
def discovery(service: ControlPlaneService = Depends(get_service)) -> dict[str, Any]:
    try:
        return {"ok": True, "applications": service.applications_view()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

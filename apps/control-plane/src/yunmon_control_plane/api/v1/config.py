"""/api/v1/config 路由。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...service import ControlPlaneService
from ..deps import get_actor, get_service, require_permission

router = APIRouter(prefix="/config", tags=["config"])


class ConfigPayload(BaseModel):
    config: dict[str, Any] | None = None


@router.get("")
def get_config(service: ControlPlaneService = Depends(get_service)) -> dict[str, Any]:
    return {"ok": True, "config": service.state_store.load_dict()}


@router.put("")
def put_config(
    payload: ConfigPayload,
    service: ControlPlaneService = Depends(get_service),
    actor: str = Depends(get_actor),
    _user=Depends(require_permission("config:write")),
) -> dict[str, Any]:
    if payload.config is None:
        raise HTTPException(status_code=400, detail="缺少 config 字段")
    try:
        result = service.apply_state(payload.config, actor=actor)
        reload_result = service.reload_prometheus()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    runtime = service.runtime_status()
    return {
        "ok": True,
        "config": result["state"],
        "snapshot": result["snapshot"],
        "prometheusReload": reload_result,
        "runtime": runtime,
    }


@router.post("/apply")
def post_apply(
    payload: ConfigPayload,
    service: ControlPlaneService = Depends(get_service),
    actor: str = Depends(get_actor),
    _user=Depends(require_permission("config:write")),
) -> dict[str, Any]:
    config = payload.config if payload.config is not None else service.state_store.load_dict()
    try:
        result = service.apply_state(config, actor=actor)
        reload_result = service.reload_prometheus()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "ok": True,
        "config": result["state"],
        "snapshot": result["snapshot"],
        "prometheusReload": reload_result,
    }

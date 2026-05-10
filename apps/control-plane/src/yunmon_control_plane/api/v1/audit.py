"""/api/v1/audit 路由(P2-1 / P2-2)。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..deps import AppContext, get_actor, get_context, require_permission

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/snapshots")
def list_snapshots(
    ctx: AppContext = Depends(get_context),
    _user=Depends(require_permission("audit:read")),
) -> dict[str, Any]:
    return {"ok": True, "snapshots": ctx.snapshot_store.list_snapshots()}


@router.get("/snapshots/{snapshot_id}")
def snapshot_detail(
    snapshot_id: str,
    ctx: AppContext = Depends(get_context),
    _user=Depends(require_permission("audit:read")),
) -> dict[str, Any]:
    try:
        return {"ok": True, "snapshot": ctx.snapshot_store.get(snapshot_id)}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/snapshots/{snapshot_id}/rollback")
def rollback(
    snapshot_id: str,
    ctx: AppContext = Depends(get_context),
    actor: str = Depends(get_actor),
    _user=Depends(require_permission("audit:rollback")),
) -> dict[str, Any]:
    try:
        result = ctx.service.rollback_to(snapshot_id, actor=actor)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "snapshot": result["snapshot"], "config": result["state"]}

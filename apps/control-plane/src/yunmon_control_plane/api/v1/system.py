"""/api/v1/system 路由。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...jobs import JobContext, JobManager
from ...service import ControlPlaneService
from ..deps import AppContext, get_context, get_service, require_permission

router = APIRouter(prefix="/system", tags=["system"])


class RestartRequest(BaseModel):
    includeControlPlane: bool = False
    build: bool = True


@router.get("/services")
def list_services(service: ControlPlaneService = Depends(get_service)) -> dict[str, Any]:
    try:
        return {"ok": True, **service.list_services()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/runtime")
def runtime(service: ControlPlaneService = Depends(get_service)) -> dict[str, Any]:
    return {"ok": True, "runtime": service.runtime_status()}


@router.post("/prometheus/reload")
def reload_prometheus(
    service: ControlPlaneService = Depends(get_service),
    _user=Depends(require_permission("system:restart")),
) -> dict[str, Any]:
    try:
        return {"ok": True, "result": service.reload_prometheus()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/restart")
def restart_stack(
    payload: RestartRequest,
    ctx: AppContext = Depends(get_context),
    _user=Depends(require_permission("system:restart")),
) -> dict[str, Any]:
    service: ControlPlaneService = ctx.service
    jobs: JobManager = ctx.jobs

    def _runner(job_ctx: JobContext) -> Any:
        job_ctx.log("开始 reconcile 监测栈")
        job_ctx.progress(20)
        result = service.reconcile_stack(
            build=payload.build, include_control_plane=payload.includeControlPlane
        )
        job_ctx.progress(95)
        job_ctx.log("reconcile 完成")
        return result

    job = jobs.submit("system.restart", _runner)
    return {"ok": True, "jobId": job.id}

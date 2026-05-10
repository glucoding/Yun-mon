"""/api/v1/jobs 路由(P2-3)。"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ..deps import AppContext, get_context

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
def list_jobs(ctx: AppContext = Depends(get_context)) -> dict[str, Any]:
    return {"ok": True, "jobs": [job.to_dict() for job in ctx.jobs.list()]}


@router.get("/{job_id}")
def get_job(job_id: str, ctx: AppContext = Depends(get_context)) -> dict[str, Any]:
    try:
        return {"ok": True, "job": ctx.jobs.get(job_id).to_dict()}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{job_id}/stream")
async def stream_job(job_id: str, ctx: AppContext = Depends(get_context)) -> StreamingResponse:
    try:
        ctx.jobs.get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    async def event_stream():
        async for event in ctx.jobs.stream(job_id):
            payload = json.dumps(event["data"], ensure_ascii=False)
            yield f"event: {event['event']}\ndata: {payload}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

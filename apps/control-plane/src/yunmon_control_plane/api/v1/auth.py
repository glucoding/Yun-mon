"""/api/v1/auth 路由(P3-1)。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import AppContext, get_context

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refreshToken: str


@router.post("/login")
def login(payload: LoginRequest, ctx: AppContext = Depends(get_context)) -> dict[str, Any]:
    bundle = ctx.auth.login(payload.username, payload.password)
    if bundle is None:
        raise HTTPException(status_code=401, detail="账号或密码错误")
    return {
        "ok": True,
        "accessToken": bundle.access_token,
        "refreshToken": bundle.refresh_token,
        "expiresIn": bundle.expires_in,
    }


@router.post("/refresh")
def refresh(payload: RefreshRequest, ctx: AppContext = Depends(get_context)) -> dict[str, Any]:
    bundle = ctx.auth.refresh(payload.refreshToken)
    if bundle is None:
        raise HTTPException(status_code=401, detail="refreshToken 无效或已过期")
    return {
        "ok": True,
        "accessToken": bundle.access_token,
        "refreshToken": bundle.refresh_token,
        "expiresIn": bundle.expires_in,
    }


@router.post("/logout")
def logout() -> dict[str, Any]:
    # 当前为无状态 JWT,客户端丢弃 token 即可。
    return {"ok": True}

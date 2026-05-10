"""FastAPI 依赖注入。"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..audit import AuditLogger, SnapshotStore
from ..clients import DockerFacade, PrometheusClient
from ..config import Settings
from ..jobs import JobManager
from ..security import AccountStore, AuthService, User
from ..service import ControlPlaneService
from ..state import StateStore


@dataclass
class AppContext:
    settings: Settings
    state_store: StateStore
    snapshot_store: SnapshotStore
    docker: DockerFacade
    prometheus: PrometheusClient
    audit: AuditLogger
    accounts: AccountStore
    auth: AuthService
    jobs: JobManager
    service: ControlPlaneService


def get_context(request: Request) -> AppContext:
    return request.app.state.context


def get_service(ctx: AppContext = Depends(get_context)) -> ControlPlaneService:
    return ctx.service


_bearer = HTTPBearer(auto_error=False)


def _actor_from_request(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    return f"anonymous:{request.client.host if request.client else 'unknown'}|{auth[:0]}"


def get_actor(
    request: Request,
    ctx: AppContext = Depends(get_context),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    settings: Settings = ctx.settings
    if not settings.auth_enabled:
        return _actor_from_request(request)
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少 Bearer Token")
    user = ctx.auth.verify_access(credentials.credentials)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效或已过期")
    return user.username


def require_permission(permission: str):
    def _checker(
        ctx: AppContext = Depends(get_context),
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    ) -> User | None:
        if not ctx.settings.auth_enabled:
            return None
        if credentials is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少 Bearer Token")
        user = ctx.auth.verify_access(credentials.credentials)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效或已过期")
        if not user.has_permission(permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"缺少权限: {permission}")
        return user

    return _checker

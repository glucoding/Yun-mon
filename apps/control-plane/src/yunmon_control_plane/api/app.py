"""FastAPI 应用工厂。"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from ..audit import AuditLogger, SnapshotStore
from ..clients import DockerFacade, PrometheusClient
from ..collectors import ContainerStatsCollector
from ..config import Settings, get_settings
from ..jobs import JobManager
from ..metrics import (
    http_requests_total,
    render_metrics,
    uptime_seconds,
)
from ..security import AccountStore, AuthService
from ..service import ControlPlaneService
from ..state import StateStore
from .deps import AppContext
from .v1 import (
    applications as applications_router,
)
from .v1 import (
    audit as audit_router,
)
from .v1 import (
    auth as auth_router,
)
from .v1 import (
    config as config_router,
)
from .v1 import (
    jobs as jobs_router,
)
from .v1 import (
    metrics_catalog as metrics_router,
)
from .v1 import (
    system as system_router,
)


def _build_context(settings: Settings) -> AppContext:
    state_store = StateStore(settings.state_path)
    state_store.ensure()

    snapshot_store = SnapshotStore(
        settings.snapshots_dir,
        keep_count=settings.snapshot_keep_count,
        keep_days=settings.snapshot_keep_days,
    )
    docker = DockerFacade(_docker_base_url(settings.docker_socket))
    prometheus = PrometheusClient()

    audit_path = settings.audit_log_path or settings.audit_log_dir / "audit.log.jsonl"
    audit = AuditLogger(audit_path)

    accounts = AccountStore(settings.accounts_path)
    if settings.auth_enabled:
        accounts.ensure_admin(rounds=settings.bcrypt_rounds)

    auth_service = AuthService(
        accounts,
        secret=settings.jwt_secret,
        access_ttl=settings.jwt_access_ttl_seconds,
        refresh_ttl=settings.jwt_refresh_ttl_seconds,
    )

    jobs = JobManager(max_workers=2)

    service = ControlPlaneService(
        settings=settings,
        state_store=state_store,
        snapshot_store=snapshot_store,
        docker_facade=docker,
        prometheus_client=prometheus,
    )

    return AppContext(
        settings=settings,
        state_store=state_store,
        snapshot_store=snapshot_store,
        docker=docker,
        prometheus=prometheus,
        audit=audit,
        accounts=accounts,
        auth=auth_service,
        jobs=jobs,
        service=service,
    )


def _docker_base_url(socket_path: str) -> str:
    if socket_path.startswith(("unix://", "tcp://", "npipe://")):
        return socket_path
    if Path(socket_path).is_absolute() or socket_path.startswith("/"):
        return f"unix://{socket_path}"
    return socket_path


_SERVER_START = time.time()


def create_app(*, settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def _lifespan(app: FastAPI):
        # OpenTelemetry 自动埋点(P2-7),仅在配置了 endpoint 时启用
        if settings.otel_endpoint:
            try:  # pragma: no cover - 取决于运行时是否安装
                from opentelemetry import trace
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
                from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
                from opentelemetry.sdk.resources import Resource
                from opentelemetry.sdk.trace import TracerProvider
                from opentelemetry.sdk.trace.export import BatchSpanProcessor

                provider = TracerProvider(
                    resource=Resource.create({"service.name": settings.otel_service_name})
                )
                provider.add_span_processor(
                    BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_endpoint))
                )
                trace.set_tracer_provider(provider)
                FastAPIInstrumentor.instrument_app(app)
            except Exception:
                pass

        # 容器级 docker stats 采集(填补 cAdvisor 在 Docker Desktop on Windows
        # 上无法识别容器的空白)。仅当 docker socket 可达时启用。
        ctx: AppContext = app.state.context
        collector: ContainerStatsCollector | None = None
        if Path(ctx.settings.docker_socket).exists():
            collector = ContainerStatsCollector(
                ctx.docker,
                interval_seconds=ctx.settings.container_stats_interval_seconds,
            )
            await collector.start()
            app.state.container_stats_collector = collector
        try:
            yield
        finally:
            if collector is not None:
                await collector.stop()

    app = FastAPI(
        title="Yun-mon Control Plane",
        version="0.2.0",
        description="Yun-mon 统一监测控制台 API",
        lifespan=_lifespan,
    )
    app.state.context = _build_context(settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
    )

    @app.middleware("http")
    async def _metrics_and_audit_middleware(request: Request, call_next):
        ctx: AppContext = app.state.context
        start = time.time()
        actor = "anonymous"
        if ctx.settings.auth_enabled:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.lower().startswith("bearer "):
                user = ctx.auth.verify_access(auth_header.split(" ", 1)[1])
                if user is not None:
                    actor = user.username
        try:
            response = await call_next(request)
            http_requests_total.labels(
                method=request.method,
                path=request.url.path,
                status=str(response.status_code),
            ).inc()
            if request.method.upper() in {"POST", "PUT", "DELETE", "PATCH"} and not request.url.path.endswith(
                ("/healthz", "/metrics")
            ):
                ctx.audit.write(
                    actor=actor,
                    ip=request.client.host if request.client else "",
                    user_agent=request.headers.get("user-agent", ""),
                    action=f"{request.method} {request.url.path}",
                    target=request.url.path,
                    status="ok" if response.status_code < 400 else f"http_{response.status_code}",
                    latency_ms=int((time.time() - start) * 1000),
                )
            return response
        except Exception as exc:
            http_requests_total.labels(
                method=request.method, path=request.url.path, status="500"
            ).inc()
            ctx.audit.write(
                actor=actor,
                ip=request.client.host if request.client else "",
                user_agent=request.headers.get("user-agent", ""),
                action=f"{request.method} {request.url.path}",
                target=request.url.path,
                status="exception",
                error=str(exc),
                latency_ms=int((time.time() - start) * 1000),
            )
            raise

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        ctx: AppContext = app.state.context
        return {
            "ok": True,
            "status": "ok",
            "timestamp": datetime.now(UTC).isoformat(),
            "stateFile": str(ctx.settings.state_path),
            "dockerSocketPresent": Path(ctx.settings.docker_socket).exists(),
        }

    @app.get("/metrics")
    def metrics() -> Response:
        uptime_seconds.set(int(time.time() - _SERVER_START))
        return PlainTextResponse(
            render_metrics().decode("utf-8"),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        ctx: AppContext = app.state.context
        for path in (ctx.settings.web_dist / "index.html", ctx.settings.static_legacy / "index.html"):
            if path.exists():
                return HTMLResponse(path.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>Yun-mon Control Plane</h1><p>前端尚未构建,请执行 `pnpm build`。</p>")

    api_prefix = "/api/v1"
    app.include_router(config_router.router, prefix=api_prefix)
    app.include_router(system_router.router, prefix=api_prefix)
    app.include_router(applications_router.router, prefix=api_prefix)
    app.include_router(metrics_router.router, prefix=api_prefix)
    app.include_router(audit_router.router, prefix=api_prefix)
    app.include_router(jobs_router.router, prefix=api_prefix)
    app.include_router(auth_router.router, prefix=api_prefix)

    ctx: AppContext = app.state.context
    # `web/dist/assets` 目录可能在前端尚未构建时不存在；此处做兜底创建,
    # 这样即使运行时通过 docker cp 注入新前端产物,无需修改代码即可被静态文件服务托管。
    assets_dir = ctx.settings.web_dist / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
    if ctx.settings.static_legacy.exists():
        app.mount("/static", StaticFiles(directory=str(ctx.settings.static_legacy)), name="static")

    # 启动时执行一次 apply,保证渲染产物与 desired-state 一致
    try:
        ctx.service.apply_state(ctx.state_store.load_dict(), actor="system:bootstrap", summary="bootstrap apply")
    except Exception:
        # 启动期渲染失败不应让进程崩溃,日志已经在 service 层落
        pass

    return app

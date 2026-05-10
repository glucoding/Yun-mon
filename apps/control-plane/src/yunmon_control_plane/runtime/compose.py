"""DockerComposeExecutor:走 stack-agent 优先,回退到容器级 docker restart。"""

from __future__ import annotations

import time
from typing import Any

from ..clients.docker_client import DockerError, DockerFacade
from ..clients.prometheus import PrometheusClient
from .executor import ReconcilePlan, ReconcileResult, ServiceState

_RESTARTABLE_SERVICES = (
    "cadvisor",
    "demo-service",
    "promtail",
    "loki",
    "alertmanager",
    "prometheus",
    "grafana",
    "otel-collector",
)


class DockerComposeExecutor:
    def __init__(
        self,
        *,
        docker_facade: DockerFacade,
        stack_agent_factory,
        prometheus_client: PrometheusClient,
        project_name: str,
    ) -> None:
        self._docker = docker_facade
        self._stack_agent_factory = stack_agent_factory  # () -> StackAgentClient | None
        self._prometheus = prometheus_client
        self._project_name = project_name

    # --- public -----------------------------------------------------------

    def list_services(self) -> list[ServiceState]:
        services = self._docker.list_project_services(self._project_name)
        return [
            ServiceState(
                name=svc.name,
                service=svc.service,
                state=svc.state,
                status=svc.status,
                image=svc.image,
                ports=svc.ports,
            )
            for svc in services
        ]

    def reload_prometheus(self) -> dict[str, Any]:
        return self._prometheus.reload()

    def runtime_status(self) -> dict[str, Any]:
        agent = self._stack_agent_factory()
        result: dict[str, Any] = {
            "restartStrategy": "docker-api",
            "stackAgent": {
                "enabled": agent is not None,
                "baseUrl": getattr(agent, "base_url", ""),
                "configured": agent is not None,
                "reachable": False,
                "health": None,
                "error": None,
            },
        }
        if agent is None:
            return result
        try:
            health = agent.healthz()
            result["stackAgent"]["reachable"] = True
            result["stackAgent"]["health"] = health
            result["restartStrategy"] = "host-agent"
        except Exception as exc:
            result["stackAgent"]["error"] = str(exc)
        return result

    def reconcile(self, plan: ReconcilePlan) -> ReconcileResult:
        agent = self._stack_agent_factory()
        services = list(plan.services or _RESTARTABLE_SERVICES)
        if plan.include_control_plane and "control-plane" not in services:
            services.append("control-plane")

        if agent is not None:
            try:
                response = agent.reconcile(
                    build=plan.build,
                    include_control_plane=plan.include_control_plane,
                    services=services,
                )
                return ReconcileResult(
                    mode="host-agent-reconcile",
                    project=self._project_name,
                    services=services,
                    runtime=self.runtime_status(),
                    extras={"agentResult": response},
                )
            except Exception as exc:
                # 回退到容器重启
                return self._restart_containers(services, fallback_reason=str(exc))

        return self._restart_containers(services)

    def restart_services(self, services: list[str]) -> ReconcileResult:
        return self._restart_containers(services or list(_RESTARTABLE_SERVICES))

    # --- internals --------------------------------------------------------

    def _restart_containers(
        self, services: list[str], *, fallback_reason: str | None = None
    ) -> ReconcileResult:
        existing = self._docker.list_project_services(self._project_name)
        service_map = {svc.service: svc for svc in existing}
        restarted: list[str] = []
        errors: list[str] = []
        for name in services:
            if name not in service_map:
                errors.append(f"{name}: 未运行")
                continue
            try:
                self._docker.restart(service_map[name].id)
                restarted.append(name)
            except DockerError as exc:
                errors.append(f"{name}: {exc}")
        if errors:
            raise RuntimeError("Docker API 重启不完整: " + "; ".join(errors))
        time.sleep(2)
        return ReconcileResult(
            mode="docker-api-restart",
            project=self._project_name,
            services=restarted,
            runtime=self.runtime_status(),
            extras={
                "fallbackReason": fallback_reason,
                "message": (
                    "通过 Docker API 完成容器级重启;若涉及端口、镜像构建等改动,仍需要在宿主机执行 "
                    "`docker compose up -d --build`。"
                ),
            },
        )

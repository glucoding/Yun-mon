"""RuntimeExecutor 抽象。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ServiceState:
    name: str
    service: str
    state: str
    status: str
    image: str
    ports: list[str]


@dataclass
class ReconcilePlan:
    services: list[str]
    build: bool = True
    include_control_plane: bool = False


@dataclass
class ReconcileResult:
    mode: str
    project: str
    services: list[str]
    runtime: dict[str, Any] = field(default_factory=dict)
    extras: dict[str, Any] = field(default_factory=dict)


class RuntimeExecutor(Protocol):
    """所有运行时(DockerCompose/Kubernetes/...)需实现的最小协议。"""

    def list_services(self) -> list[ServiceState]: ...

    def reconcile(self, plan: ReconcilePlan) -> ReconcileResult: ...

    def restart_services(self, services: list[str]) -> ReconcileResult: ...

    def reload_prometheus(self) -> dict[str, Any]: ...

    def runtime_status(self) -> dict[str, Any]: ...

"""Docker 客户端封装(P1-5 用官方 SDK 替代裸 socket)。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:  # pragma: no cover - 测试环境可能未安装 docker SDK
    import docker
    from docker.errors import DockerException
except ImportError as exc:  # pragma: no cover
    docker = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


class DockerError(RuntimeError):
    """统一的 Docker 操作异常。"""


@dataclass(frozen=True)
class DockerService:
    id: str
    name: str
    service: str
    state: str
    status: str
    image: str
    ports: list[str]
    raw_ports: list[dict[str, Any]]
    network_ips: list[str]
    compose_project: str
    labels: dict[str, str]


def _format_ports(ports: list[dict[str, Any]] | None) -> list[str]:
    formatted = []
    for port in ports or []:
        private = port.get("PrivatePort")
        public = port.get("PublicPort")
        kind = port.get("Type", "tcp")
        ip = port.get("IP") or "0.0.0.0"
        if public is None:
            formatted.append(f"{private}/{kind}")
        else:
            formatted.append(f"{ip}:{public}->{private}/{kind}")
    return formatted


def build_docker_client(base_url: str) -> Any:
    if docker is None:
        raise DockerError(f"docker SDK 未安装: {_IMPORT_ERROR}")
    try:
        return docker.DockerClient(base_url=base_url, timeout=60)
    except DockerException as exc:
        raise DockerError(f"无法连接 Docker socket {base_url}: {exc}") from exc


class DockerFacade:
    """对 docker SDK 的薄封装,统一异常类型并暴露我们关心的少量操作。"""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url
        self._client: Any | None = None

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = build_docker_client(self._base_url)
        return self._client

    def list_project_services(self, project_name: str) -> list[DockerService]:
        try:
            containers = self.client.containers.list(
                all=True,
                filters={"label": f"com.docker.compose.project={project_name}"},
            )
        except Exception as exc:  # docker SDK exposes many subclasses
            raise DockerError(f"列出 Compose 项目 {project_name!r} 容器失败: {exc}") from exc

        services: list[DockerService] = []
        for container in containers:
            attrs = container.attrs or {}
            labels = (attrs.get("Config", {}).get("Labels") or {}) | (attrs.get("Labels") or {})
            ports = list((attrs.get("NetworkSettings", {}).get("Ports") or {}).items())
            raw_ports = []
            for private_with_proto, host_bindings in ports:
                private_str, _, kind = private_with_proto.partition("/")
                try:
                    private_port = int(private_str)
                except ValueError:
                    private_port = 0
                if not host_bindings:
                    raw_ports.append({"PrivatePort": private_port, "Type": kind or "tcp"})
                else:
                    for binding in host_bindings:
                        raw_ports.append(
                            {
                                "PrivatePort": private_port,
                                "PublicPort": int(binding.get("HostPort", 0)) or None,
                                "IP": binding.get("HostIp"),
                                "Type": kind or "tcp",
                            }
                        )

            networks = (attrs.get("NetworkSettings", {}).get("Networks") or {}).values()
            ips = [n.get("IPAddress") for n in networks if n.get("IPAddress")]

            services.append(
                DockerService(
                    id=container.id,
                    name=container.name,
                    service=labels.get("com.docker.compose.service", ""),
                    state=container.status or "unknown",
                    status=attrs.get("State", {}).get("Status", "")
                    or attrs.get("Status", "")
                    or container.status,
                    image=container.image.tags[0] if container.image and container.image.tags else "",
                    ports=_format_ports(raw_ports),
                    raw_ports=raw_ports,
                    network_ips=ips,
                    compose_project=labels.get("com.docker.compose.project", ""),
                    labels=labels,
                )
            )
        return services

    def list_running_containers(self) -> list[DockerService]:
        try:
            containers = self.client.containers.list(all=False)
        except Exception as exc:
            raise DockerError(f"列出运行中容器失败: {exc}") from exc

        services: list[DockerService] = []
        for container in containers:
            attrs = container.attrs or {}
            labels = (attrs.get("Config", {}).get("Labels") or {}) | (attrs.get("Labels") or {})

            raw_ports: list[dict[str, Any]] = []
            for private_with_proto, host_bindings in (
                (attrs.get("NetworkSettings", {}).get("Ports") or {}).items()
            ):
                private_str, _, kind = private_with_proto.partition("/")
                try:
                    private_port = int(private_str)
                except ValueError:
                    continue
                if not host_bindings:
                    raw_ports.append({"PrivatePort": private_port, "Type": kind or "tcp"})
                else:
                    for binding in host_bindings:
                        raw_ports.append(
                            {
                                "PrivatePort": private_port,
                                "PublicPort": int(binding.get("HostPort", 0)) or None,
                                "IP": binding.get("HostIp"),
                                "Type": kind or "tcp",
                            }
                        )

            ips = [
                n.get("IPAddress")
                for n in (attrs.get("NetworkSettings", {}).get("Networks") or {}).values()
                if n.get("IPAddress")
            ]

            services.append(
                DockerService(
                    id=container.id,
                    name=container.name,
                    service=labels.get("com.docker.compose.service", ""),
                    state=container.status or "unknown",
                    status=attrs.get("Status", "") or container.status,
                    image=container.image.tags[0] if container.image and container.image.tags else "",
                    ports=_format_ports(raw_ports),
                    raw_ports=raw_ports,
                    network_ips=ips,
                    compose_project=labels.get("com.docker.compose.project", ""),
                    labels=labels,
                )
            )
        return services

    def restart(self, container_id: str, timeout: int = 30) -> None:
        try:
            container = self.client.containers.get(container_id)
            container.restart(timeout=timeout)
        except Exception as exc:
            raise DockerError(f"重启容器 {container_id} 失败: {exc}") from exc

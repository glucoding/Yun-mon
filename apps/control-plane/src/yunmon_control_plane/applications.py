"""应用自动发现。

P0-6:Docker 失败时不再静默清空,改为抛出错误,由调用方决定保留旧 SD 还是抛 5xx。
"""

from __future__ import annotations

from typing import Any

from .clients.docker_client import DockerError, DockerFacade

INTERNAL_PLATFORM_SERVICES = {
    "control-plane",
    "prometheus",
    "alertmanager",
    "loki",
    "promtail",
    "grafana",
    "cadvisor",
    "otel-collector",
}


def _container_scrape_targets(container: Any, target_port: int) -> list[str]:
    targets = []
    for port in container.raw_ports or []:
        if port.get("PrivatePort") == target_port and port.get("PublicPort"):
            targets.append(f"host.docker.internal:{port['PublicPort']}")
    if targets:
        return targets
    return [f"{ip}:{target_port}" for ip in container.network_ips]


def _normalize_application_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "appId": str(item.get("appId", "")).strip(),
        "enabled": bool(item.get("enabled", False)),
        "displayName": str(item.get("displayName", "")).strip(),
        "serviceName": str(item.get("serviceName", "")).strip(),
        "targetPort": item.get("targetPort"),
        "metricsPath": str(item.get("metricsPath", "")).strip(),
        "environment": str(item.get("environment", "")).strip(),
    }


def discover_applications(state: dict[str, Any], docker_facade: DockerFacade) -> list[dict[str, Any]]:
    """合并 desired-state 中的覆盖与 Docker 自动发现结果。

    若 auto-discovery 关闭,只返回 configured items。
    """
    apps = state["applications"]
    defaults = apps["defaults"]
    overrides = {
        normalized["appId"]: normalized
        for normalized in (_normalize_application_item(item) for item in apps.get("items", []))
        if normalized["appId"]
    }
    seen: set[str] = set()
    items: list[dict[str, Any]] = []

    if not apps.get("autoDiscoveryEnabled", True):
        for app_id, override in overrides.items():
            entry = dict(override)
            entry.update(
                {
                    "discoveryType": "configured",
                    "autoDiscovered": False,
                    "configured": True,
                    "containers": [],
                    "targets": [],
                }
            )
            items.append(entry)
            seen.add(app_id)
        items.sort(key=_sort_key)
        return items

    containers = docker_facade.list_running_containers()
    grouped: dict[str, dict[str, Any]] = {}

    for container in containers:
        compose_service = container.service
        if compose_service in INTERNAL_PLATFORM_SERVICES:
            continue
        service_label = container.labels.get("service_name", "") or ""
        app_id = service_label or compose_service or container.name
        app_id = str(app_id).strip()
        if not app_id:
            continue

        group = grouped.setdefault(
            app_id,
            {
                "appId": app_id,
                "displayName": app_id,
                "serviceName": service_label or compose_service or app_id,
                "discoveryType": "docker",
                "autoDiscovered": True,
                "containers": [],
                "targets": [],
                "enabled": defaults["enabled"],
                "targetPort": None,
                "metricsPath": defaults["metricsPath"],
                "environment": defaults["environment"],
                "hasMonitoringLabels": False,
            },
        )
        group["containers"].append(
            {
                "id": container.id,
                "name": container.name,
                "image": container.image,
                "composeService": compose_service,
                "rawPorts": container.raw_ports,
                "ports": container.ports,
                "networkIps": container.network_ips,
            }
        )
        monitoring_port = container.labels.get("monitoring_port")
        if monitoring_port:
            try:
                group["targetPort"] = int(monitoring_port)
                group["hasMonitoringLabels"] = (
                    str(container.labels.get("monitoring_enabled", "")).lower() == "true"
                )
            except ValueError:
                pass
        metrics_path = container.labels.get("monitoring_metrics_path")
        if metrics_path:
            group["metricsPath"] = metrics_path
        if (
            str(container.labels.get("monitoring_enabled", "")).lower() == "true"
            and group["targetPort"]
        ):
            group["enabled"] = True

    for app_id, group in grouped.items():
        override = overrides.get(app_id)
        if override:
            group["enabled"] = override["enabled"]
            group["displayName"] = override["displayName"] or group["displayName"]
            group["serviceName"] = override["serviceName"] or group["serviceName"]
            if override["targetPort"] is not None:
                group["targetPort"] = override["targetPort"]
            group["metricsPath"] = override["metricsPath"] or group["metricsPath"]
            group["environment"] = override["environment"] or group["environment"]
            group["configured"] = True
        else:
            group["configured"] = False

        if group["targetPort"]:
            group["targets"] = sorted(
                {
                    target
                    for container in group["containers"]
                    for target in _container_scrape_targets(_FakeContainer(container), group["targetPort"])
                }
            )
        items.append(group)
        seen.add(app_id)

    for app_id, override in overrides.items():
        if app_id in seen:
            continue
        entry = dict(override)
        entry.update(
            {
                "discoveryType": "configured",
                "autoDiscovered": False,
                "configured": True,
                "containers": [],
                "targets": [],
            }
        )
        items.append(entry)

    items.sort(key=_sort_key)
    return items


def _sort_key(item: dict[str, Any]) -> str:
    return str(item.get("displayName") or item.get("serviceName") or item.get("appId") or "").lower()


class _FakeContainer:
    """临时适配 _container_scrape_targets 接受 dataclass 或 dict。"""

    def __init__(self, src: dict[str, Any]):
        self.raw_ports = src.get("rawPorts") or []
        self.network_ips = src.get("networkIps") or []


__all__ = ["INTERNAL_PLATFORM_SERVICES", "DockerError", "discover_applications"]

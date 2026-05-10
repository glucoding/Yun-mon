"""schema v1 → v2:引入 clusters / alertReceivers / otelCollector / slos 字段。"""

from __future__ import annotations

from typing import Any


def upgrade_v1_to_v2(state: dict[str, Any]) -> dict[str, Any]:
    new_state = dict(state)

    if "clusters" not in new_state or not new_state["clusters"]:
        system = new_state.get("system", {}) or {}
        new_state["clusters"] = [
            {
                "id": "default",
                "name": str(system.get("clusterName") or "默认集群"),
                "type": "docker-compose",
                "isPrimary": True,
                "description": "由 v1 → v2 自动迁移生成的默认集群。",
            }
        ]

    if "alertReceivers" not in new_state:
        new_state["alertReceivers"] = [
            {
                "name": "platform-default",
                "kind": "webhook",
                "enabled": False,
                "config": {"url": ""},
                "matchers": [],
            },
            {
                "name": "platform-critical",
                "kind": "webhook",
                "enabled": False,
                "config": {"url": ""},
                "matchers": [{"severity": "critical"}],
            },
        ]

    new_state.setdefault(
        "otelCollector",
        {"enabled": False, "exporters": {"logging": True, "otlpHttpEndpoint": ""}},
    )

    new_state.setdefault("slos", [])

    ports = new_state.setdefault("ports", {})
    ports.setdefault("otelCollectorOtlpHttpPort", 4318)
    ports.setdefault("otelCollectorOtlpGrpcPort", 4317)

    new_state.pop("dockerStatsExporter", None)
    return new_state

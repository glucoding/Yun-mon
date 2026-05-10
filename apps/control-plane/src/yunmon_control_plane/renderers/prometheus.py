"""渲染 Prometheus 主配置和 file_sd targets。"""

from __future__ import annotations

import json
from typing import Any

from ._yaml import dump_yaml


def render_prometheus(state: dict[str, Any]) -> str:
    prometheus = state["prometheus"]
    labels = prometheus["externalLabels"]
    refresh = prometheus["dockerDiscoveryRefreshInterval"]

    config = {
        "global": {
            "scrape_interval": prometheus["scrapeInterval"],
            "evaluation_interval": prometheus["evaluationInterval"],
            "external_labels": {"cluster": labels["cluster"], "env": labels["env"]},
        },
        "rule_files": ["/etc/prometheus/rules/*.yml"],
        "scrape_configs": [
            {
                "job_name": "prometheus",
                "static_configs": [{"targets": ["prometheus:9090"], "labels": {"service": "prometheus"}}],
            },
            {
                "job_name": "cadvisor",
                "static_configs": [{"targets": ["cadvisor:8080"], "labels": {"service": "cadvisor"}}],
            },
            {
                "job_name": "loki",
                "metrics_path": "/metrics",
                "static_configs": [{"targets": ["loki:3100"], "labels": {"service": "loki"}}],
            },
            {
                "job_name": "control_plane",
                "metrics_path": "/metrics",
                "static_configs": [{"targets": ["control-plane:8090"], "labels": {"service": "control-plane"}}],
            },
            {
                "job_name": "stack_agent",
                "metrics_path": "/metrics",
                "static_configs": [
                    {"targets": ["host.docker.internal:19090"], "labels": {"service": "stack-agent"}}
                ],
            },
            {
                "job_name": "applications",
                "file_sd_configs": [
                    {
                        "files": ["/etc/prometheus/file_sd/applications-targets.json"],
                        "refresh_interval": refresh,
                    }
                ],
            },
        ],
        "alerting": {
            "alertmanagers": [{"static_configs": [{"targets": ["alertmanager:9093"]}]}],
        },
    }

    if state["otelCollector"]["enabled"]:
        config["scrape_configs"].append(
            {
                "job_name": "otel_collector",
                "metrics_path": "/metrics",
                "static_configs": [
                    {"targets": ["otel-collector:8889"], "labels": {"service": "otel-collector"}}
                ],
            }
        )

    return dump_yaml(config)


def render_application_targets(applications_view: list[dict[str, Any]], default_metrics_path: str, environment: str) -> str:
    """根据已发现/已配置的应用列表渲染 file_sd 目标。"""
    items = []
    for app in applications_view:
        if not app.get("enabled"):
            continue
        targets = app.get("targets") or []
        if not targets:
            continue
        labels = {
            "service": app.get("serviceName") or app["appId"],
            "app_id": app["appId"],
            "app_display_name": app.get("displayName") or app["appId"],
            "env": app.get("environment") or environment,
            "__metrics_path__": app.get("metricsPath") or default_metrics_path,
        }
        items.append({"targets": sorted(set(targets)), "labels": labels})
    return json.dumps(items, indent=2, ensure_ascii=False) + "\n"

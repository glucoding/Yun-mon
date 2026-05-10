"""desired-state 的默认值构造。

P0-5：默认 stackAgent.sharedToken 留空,由 StateStore.ensure 在首次启动时自动生成。
"""

from __future__ import annotations

import secrets
from typing import Any

from ..catalog.canonical import canonical_copy

CURRENT_SCHEMA_VERSION = 2


def build_default_state(*, generate_token: bool = True) -> dict[str, Any]:
    return {
        "metadata": {
            "schemaVersion": CURRENT_SCHEMA_VERSION,
            "lastAppliedAt": None,
        },
        "system": {
            "monitoringProject": "yun-mon",
            "environment": "local",
            "clusterName": "yun-mon-local",
        },
        "clusters": [
            {
                "id": "default",
                "name": "默认集群",
                "type": "docker-compose",
                "isPrimary": True,
                "description": "本地 Docker Compose 部署的默认集群。",
            }
        ],
        "ports": {
            "grafanaHostPort": 13000,
            "demoServiceHostPort": 18080,
            "controlPlaneHostPort": 18090,
            "prometheusHostPort": 9090,
            "alertmanagerHostPort": 9093,
            "lokiHostPort": 3100,
            "cadvisorHostPort": 8081,
            "otelCollectorOtlpHttpPort": 4318,
            "otelCollectorOtlpGrpcPort": 4317,
        },
        "grafana": {
            "adminUser": "admin",
            "adminPassword": "admin123456",
            "allowSignUp": False,
        },
        "demoService": {
            "appEnv": "local",
            "logDir": "/var/log/yunmon",
            "javaOpts": "-XX:+UseContainerSupport -XX:MaxRAMPercentage=75.0",
            "monitoringEnabled": True,
            "monitoringPort": 8080,
            "serviceName": "demo-service",
            "metricsPath": "/actuator/prometheus",
        },
        "applications": {
            "autoDiscoveryEnabled": True,
            "defaults": {
                "enabled": False,
                "metricsPath": "/actuator/prometheus",
                "environment": "local",
            },
            "items": [
                {
                    "appId": "demo-service",
                    "enabled": True,
                    "displayName": "Demo Service",
                    "serviceName": "demo-service",
                    "targetPort": 8080,
                    "metricsPath": "/actuator/prometheus",
                    "environment": "local",
                }
            ],
        },
        "metricCatalog": canonical_copy(),
        "prometheus": {
            "scrapeInterval": "15s",
            "evaluationInterval": "30s",
            "dockerDiscoveryRefreshInterval": "30s",
            "externalLabels": {
                "cluster": "yun-mon-local",
                "env": "local",
            },
        },
        "alertmanager": {
            "resolveTimeout": "5m",
            "groupBy": ["alertname", "service", "severity"],
            "groupWait": "15s",
            "groupInterval": "2m",
            "repeatInterval": "4h",
        },
        "alertReceivers": [
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
        ],
        "loki": {
            "authEnabled": False,
            "pathPrefix": "/loki",
            "replicationFactor": 1,
            "reportingEnabled": False,
        },
        "promtail": {
            "positionsFile": "/tmp/positions.yaml",
            "clientUrl": "http://loki:3100/loki/api/v1/push",
            "logPath": "/var/log/yunmon/*.log",
        },
        "cadvisor": {
            "dockerOnly": True,
            "housekeepingInterval": "30s",
        },
        "otelCollector": {
            "enabled": False,
            "exporters": {
                "logging": True,
                "otlpHttpEndpoint": "",
            },
        },
        "stackAgent": {
            "enabled": True,
            "baseUrl": "http://host.docker.internal:19090",
            "sharedToken": secrets.token_urlsafe(32) if generate_token else "",
        },
        "slos": [],
    }

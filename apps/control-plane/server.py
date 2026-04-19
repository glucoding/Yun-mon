import http.client
import json
import mimetypes
import os
import socket
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

WORKSPACE = Path(os.environ.get("CONTROL_PLANE_WORKSPACE", "/workspace"))
HTTP_PORT = int(os.environ.get("CONTROL_PLANE_HTTP_PORT", "8090"))
MONITORING_PROJECT = os.environ.get("MONITORING_PROJECT", "yun-mon")
DOCKER_SOCKET = os.environ.get("DOCKER_SOCKET", "/var/run/docker.sock")

STATE_PATH = WORKSPACE / "infra" / "control-plane" / "desired-state.json"
ENV_PATH = WORKSPACE / ".env"
PROMETHEUS_PATH = WORKSPACE / "infra" / "prometheus" / "prometheus.yml"
PROMETHEUS_FILE_SD_PATH = WORKSPACE / "infra" / "prometheus" / "file_sd" / "applications-targets.json"
METRIC_RULES_PATH = WORKSPACE / "infra" / "prometheus" / "rules" / "metric-catalog-rules.yml"
ALERTMANAGER_PATH = WORKSPACE / "infra" / "alertmanager" / "alertmanager.yml"
LOKI_PATH = WORKSPACE / "infra" / "loki" / "loki-config.yml"
PROMTAIL_PATH = WORKSPACE / "infra" / "promtail" / "promtail-config.yml"
CONTROL_DASHBOARD_PATH = WORKSPACE / "infra" / "grafana" / "dashboards" / "control-center.json"
METRIC_DASHBOARD_PATH = WORKSPACE / "infra" / "grafana" / "dashboards" / "metric-catalog.json"
STATIC_DIR = Path(__file__).resolve().parent / "static"

RESTARTABLE_SERVICES = [
    "cadvisor",
    "docker-stats-exporter",
    "demo-service",
    "promtail",
    "loki",
    "alertmanager",
    "prometheus",
    "grafana",
]
SERVICE_ORDER = RESTARTABLE_SERVICES + ["control-plane"]
INTERNAL_PLATFORM_SERVICES = {
    "control-plane",
    "docker-stats-exporter",
    "prometheus",
    "alertmanager",
    "loki",
    "promtail",
    "grafana",
    "cadvisor",
}
METRICS_LOCK = threading.Lock()
METRICS = {
    "http_requests_total": 0,
    "config_apply_total": 0,
    "config_apply_failures_total": 0,
    "stack_restarts_total": 0,
    "stack_restart_failures_total": 0,
    "prometheus_reload_total": 0,
    "prometheus_reload_failures_total": 0,
    "last_successful_apply_timestamp": 0,
    "last_successful_restart_timestamp": 0,
}
SERVER_START_TIME = time.time()

DEFAULT_STATE = {
    "metadata": {
        "schemaVersion": 1,
        "lastAppliedAt": None,
    },
    "system": {
        "monitoringProject": "yun-mon",
        "environment": "local",
        "clusterName": "yun-mon-local",
    },
    "ports": {
        "grafanaHostPort": 13000,
        "demoServiceHostPort": 18080,
        "controlPlaneHostPort": 18090,
        "prometheusHostPort": 9090,
        "alertmanagerHostPort": 9093,
        "lokiHostPort": 3100,
        "cadvisorHostPort": 8081,
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
    "metricCatalog": {
        "categories": [
            {
                "id": "basic",
                "name": "基础指标",
                "description": "直接来源于应用、容器或平台采集链路的原始指标。",
            },
            {
                "id": "composite",
                "name": "组合指标",
                "description": "通过多个基础指标或录制规则组合而成的服务级指标。",
            },
            {
                "id": "macro",
                "name": "宏观指标",
                "description": "反映平台整体健康度、规模和治理效果的宏观视角指标。",
            },
        ],
        "items": [
            {
                "metricId": "business_orders_processed_total",
                "metricName": "yunmon_business_orders_processed_total",
                "displayName": "订单处理总数",
                "category": "basic",
                "sourceType": "raw",
                "ruleMode": "external",
                "description": "示例业务累计处理成功的订单数量。",
                "expression": "",
                "derivedFrom": [],
                "unit": "short",
                "enabled": True,
                "visualization": {
                    "panelType": "stat",
                    "unit": "short",
                    "decimals": 0,
                    "colorMode": "value",
                    "showOnDashboard": True,
                },
            },
            {
                "metricId": "business_orders_failed_total",
                "metricName": "yunmon_business_orders_failed_total",
                "displayName": "订单失败总数",
                "category": "basic",
                "sourceType": "raw",
                "ruleMode": "external",
                "description": "示例业务累计处理失败的订单数量。",
                "expression": "",
                "derivedFrom": [],
                "unit": "short",
                "enabled": True,
                "visualization": {
                    "panelType": "stat",
                    "unit": "short",
                    "decimals": 0,
                    "colorMode": "background",
                    "showOnDashboard": True,
                },
            },
            {
                "metricId": "business_queue_depth",
                "metricName": "yunmon_business_queue_depth",
                "displayName": "业务队列深度",
                "category": "basic",
                "sourceType": "raw",
                "ruleMode": "external",
                "description": "示例业务当前待处理队列深度。",
                "expression": "",
                "derivedFrom": [],
                "unit": "short",
                "enabled": True,
                "visualization": {
                    "panelType": "gauge",
                    "unit": "short",
                    "decimals": 0,
                    "colorMode": "value",
                    "showOnDashboard": True,
                },
            },
            {
                "metricId": "http_requests_rate1m",
                "metricName": "service:http_requests:rate1m",
                "displayName": "HTTP 吞吐率(1m)",
                "category": "composite",
                "sourceType": "recording_rule",
                "ruleMode": "external",
                "description": "按服务聚合的 1 分钟 HTTP 请求速率。",
                "expression": 'sum by (service, status) (rate(http_server_requests_seconds_count{job="applications"}[1m]))',
                "derivedFrom": ["http_server_requests_seconds_count"],
                "unit": "reqps",
                "enabled": True,
                "visualization": {
                    "panelType": "timeseries",
                    "unit": "reqps",
                    "decimals": 2,
                    "colorMode": "palette-classic",
                    "showOnDashboard": True,
                },
            },
            {
                "metricId": "http_errors_ratio5m",
                "metricName": "service:http_errors:ratio5m",
                "displayName": "HTTP 5xx 错误率(5m)",
                "category": "composite",
                "sourceType": "recording_rule",
                "ruleMode": "external",
                "description": "按服务聚合的 5 分钟 HTTP 5xx 错误比例。",
                "expression": 'sum by (service) (rate(http_server_requests_seconds_count{job="applications",status=~"5.."}[5m])) / clamp_min(sum by (service) (rate(http_server_requests_seconds_count{job="applications"}[5m])), 0.001)',
                "derivedFrom": ["http_server_requests_seconds_count"],
                "unit": "percentunit",
                "enabled": True,
                "visualization": {
                    "panelType": "timeseries",
                    "unit": "percentunit",
                    "decimals": 3,
                    "colorMode": "thresholds",
                    "showOnDashboard": True,
                },
            },
            {
                "metricId": "http_latency_p95_5m",
                "metricName": "service:http_latency:p95_5m",
                "displayName": "HTTP P95 延迟(5m)",
                "category": "composite",
                "sourceType": "recording_rule",
                "ruleMode": "external",
                "description": "按服务聚合的 5 分钟 P95 HTTP 延迟。",
                "expression": 'histogram_quantile(0.95, sum by (service, le) (rate(http_server_requests_seconds_bucket{job="applications"}[5m])))',
                "derivedFrom": ["http_server_requests_seconds_bucket"],
                "unit": "s",
                "enabled": True,
                "visualization": {
                    "panelType": "timeseries",
                    "unit": "s",
                    "decimals": 3,
                    "colorMode": "palette-classic",
                    "showOnDashboard": True,
                },
            },
            {
                "metricId": "applications_up_total",
                "metricName": "platform:applications:up_total",
                "displayName": "在线应用数",
                "category": "macro",
                "sourceType": "recording_rule",
                "ruleMode": "managed",
                "description": "当前已纳入监管并在线的应用实例总数。",
                "expression": 'sum(up{job="applications"})',
                "derivedFrom": ["up"],
                "unit": "short",
                "enabled": True,
                "visualization": {
                    "panelType": "stat",
                    "unit": "short",
                    "decimals": 0,
                    "colorMode": "background",
                    "showOnDashboard": True,
                },
            },
            {
                "metricId": "applications_up_ratio",
                "metricName": "platform:applications:up_ratio",
                "displayName": "应用在线率",
                "category": "macro",
                "sourceType": "recording_rule",
                "ruleMode": "managed",
                "description": "当前应用实例的总体在线比例。",
                "expression": 'sum(up{job="applications"}) / clamp_min(count(up{job="applications"}), 1)',
                "derivedFrom": ["up"],
                "unit": "percentunit",
                "enabled": True,
                "visualization": {
                    "panelType": "gauge",
                    "unit": "percentunit",
                    "decimals": 3,
                    "colorMode": "thresholds",
                    "showOnDashboard": True,
                },
            },
        ],
    },
    "dockerStatsExporter": {
        "maxWorkers": 8,
        "targetProject": "yun-mon",
    },
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
    "stackAgent": {
        "enabled": True,
        "baseUrl": "http://host.docker.internal:19090",
        "sharedToken": "yunmon-local-agent-token",
    },
}

CANONICAL_METRIC_CATALOG = {
    "categories": [
        {
            "id": "basic",
            "name": "基础指标",
            "description": "直接来源于应用、容器或平台采集链路的原始指标。",
        },
        {
            "id": "composite",
            "name": "组合指标",
            "description": "通过多个基础指标或记录规则组合而成的服务级指标。",
        },
        {
            "id": "macro",
            "name": "宏观指标",
            "description": "反映平台整体健康度、规模和治理效果的宏观视角指标。",
        },
    ],
    "items": [
        {
            "metricId": "business_orders_processed_total",
            "metricName": "yunmon_business_orders_processed_total",
            "displayName": "订单处理总数",
            "category": "basic",
            "sourceType": "raw",
            "ruleMode": "external",
            "description": "示例业务累计处理成功的订单数量。",
            "expression": "",
            "derivedFrom": [],
            "unit": "short",
            "enabled": True,
            "visualization": {
                "panelType": "stat",
                "unit": "short",
                "decimals": 0,
                "colorMode": "value",
                "showOnDashboard": True,
            },
        },
        {
            "metricId": "business_orders_failed_total",
            "metricName": "yunmon_business_orders_failed_total",
            "displayName": "订单失败总数",
            "category": "basic",
            "sourceType": "raw",
            "ruleMode": "external",
            "description": "示例业务累计处理失败的订单数量。",
            "expression": "",
            "derivedFrom": [],
            "unit": "short",
            "enabled": True,
            "visualization": {
                "panelType": "stat",
                "unit": "short",
                "decimals": 0,
                "colorMode": "background",
                "showOnDashboard": True,
            },
        },
        {
            "metricId": "business_queue_depth",
            "metricName": "yunmon_business_queue_depth",
            "displayName": "业务队列深度",
            "category": "basic",
            "sourceType": "raw",
            "ruleMode": "external",
            "description": "示例业务当前待处理队列深度。",
            "expression": "",
            "derivedFrom": [],
            "unit": "short",
            "enabled": True,
            "visualization": {
                "panelType": "gauge",
                "unit": "short",
                "decimals": 0,
                "colorMode": "value",
                "showOnDashboard": True,
            },
        },
        {
            "metricId": "http_requests_rate1m",
            "metricName": "service:http_requests:rate1m",
            "displayName": "HTTP 吞吐率(1m)",
            "category": "composite",
            "sourceType": "recording_rule",
            "ruleMode": "external",
            "description": "按服务聚合的 1 分钟 HTTP 请求速率。",
            "expression": 'sum by (service, status) (rate(http_server_requests_seconds_count{job="applications"}[1m]))',
            "derivedFrom": ["http_server_requests_seconds_count"],
            "unit": "reqps",
            "enabled": True,
            "visualization": {
                "panelType": "timeseries",
                "unit": "reqps",
                "decimals": 2,
                "colorMode": "palette-classic",
                "showOnDashboard": True,
            },
        },
        {
            "metricId": "http_errors_ratio5m",
            "metricName": "service:http_errors:ratio5m",
            "displayName": "HTTP 5xx 错误率(5m)",
            "category": "composite",
            "sourceType": "recording_rule",
            "ruleMode": "external",
            "description": "按服务聚合的 5 分钟 HTTP 5xx 错误比例。",
            "expression": 'sum by (service) (rate(http_server_requests_seconds_count{job="applications",status=~"5.."}[5m])) / clamp_min(sum by (service) (rate(http_server_requests_seconds_count{job="applications"}[5m])), 0.001)',
            "derivedFrom": ["http_server_requests_seconds_count"],
            "unit": "percentunit",
            "enabled": True,
            "visualization": {
                "panelType": "timeseries",
                "unit": "percentunit",
                "decimals": 3,
                "colorMode": "thresholds",
                "showOnDashboard": True,
            },
        },
        {
            "metricId": "http_latency_p95_5m",
            "metricName": "service:http_latency:p95_5m",
            "displayName": "HTTP P95 延迟(5m)",
            "category": "composite",
            "sourceType": "recording_rule",
            "ruleMode": "external",
            "description": "按服务聚合的 5 分钟 P95 HTTP 延迟。",
            "expression": 'histogram_quantile(0.95, sum by (service, le) (rate(http_server_requests_seconds_bucket{job="applications"}[5m])))',
            "derivedFrom": ["http_server_requests_seconds_bucket"],
            "unit": "s",
            "enabled": True,
            "visualization": {
                "panelType": "timeseries",
                "unit": "s",
                "decimals": 3,
                "colorMode": "palette-classic",
                "showOnDashboard": True,
            },
        },
        {
            "metricId": "applications_up_total",
            "metricName": "platform:applications:up_total",
            "displayName": "在线应用数",
            "category": "macro",
            "sourceType": "recording_rule",
            "ruleMode": "managed",
            "description": "当前已纳入监管并在线的应用实例总数。",
            "expression": 'sum(up{job="applications"})',
            "derivedFrom": ["up"],
            "unit": "short",
            "enabled": True,
            "visualization": {
                "panelType": "stat",
                "unit": "short",
                "decimals": 0,
                "colorMode": "background",
                "showOnDashboard": True,
            },
        },
        {
            "metricId": "applications_up_ratio",
            "metricName": "platform:applications:up_ratio",
            "displayName": "应用在线率",
            "category": "macro",
            "sourceType": "recording_rule",
            "ruleMode": "managed",
            "description": "当前应用实例的总体在线比例。",
            "expression": 'sum(up{job="applications"}) / clamp_min(count(up{job="applications"}), 1)',
            "derivedFrom": ["up"],
            "unit": "percentunit",
            "enabled": True,
            "visualization": {
                "panelType": "gauge",
                "unit": "percentunit",
                "decimals": 3,
                "colorMode": "thresholds",
                "showOnDashboard": True,
            },
        },
    ],
}
DEFAULT_STATE["metricCatalog"] = json.loads(json.dumps(CANONICAL_METRIC_CATALOG, ensure_ascii=False))

LEGACY_BUSINESS_METRIC_IDS = {
    "business_orders_processed_total",
    "business_orders_failed_total",
    "business_queue_depth",
}

EXACT_METRIC_HINTS = {
    "http_server_requests_seconds_count": {
        "displayName": "\u0048\u0054\u0054\u0050 \u8bf7\u6c42\u603b\u6570",
        "description": "\u5e94\u7528\u5bf9\u5916\u63d0\u4f9b\u7684 HTTP \u8bf7\u6c42\u7d2f\u8ba1\u8ba1\u6570\uff0c\u662f\u8ba1\u7b97\u541e\u5410\u7387\u3001\u9519\u8bef\u7387\u548c\u5ef6\u8fdf\u7684\u57fa\u7840\u6765\u6e90\u3002",
        "category": "basic",
        "unit": "short",
        "panelType": "timeseries",
        "colorMode": "palette-classic",
    },
    "http_server_requests_seconds_bucket": {
        "displayName": "\u0048\u0054\u0054\u0050 \u5ef6\u8fdf\u6876",
        "description": "\u7528\u4e8e\u7edf\u8ba1 HTTP \u5ef6\u8fdf\u5206\u5e03\u7684\u6876\u578b\u6307\u6807\uff0c\u53ef\u7528\u6765\u7ec4\u5408 P95/P99 \u5ef6\u8fdf\u6307\u6807\u3002",
        "category": "basic",
        "unit": "short",
        "panelType": "timeseries",
        "colorMode": "palette-classic",
    },
    "jvm_memory_used_bytes": {
        "displayName": "\u004a\u0056\u004d \u5185\u5b58\u4f7f\u7528\u91cf",
        "description": "\u5e94\u7528 \u004a\u0056\u004d \u5f53\u524d\u5df2\u4f7f\u7528\u5185\u5b58\uff0c\u53ef\u7528\u4e8e\u89c2\u5bdf\u5806\u548c\u975e\u5806\u8d44\u6e90\u5360\u7528\u3002",
        "category": "basic",
        "unit": "bytes",
        "panelType": "timeseries",
        "colorMode": "palette-classic",
    },
    "process_cpu_usage": {
        "displayName": "\u8fdb\u7a0b \u0043\u0050\u0055 \u4f7f\u7528\u7387",
        "description": "\u5f53\u524d\u5e94\u7528\u8fdb\u7a0b\u7684 CPU \u4f7f\u7528\u7387\uff0c\u53ef\u7528\u4e8e\u5224\u65ad\u670d\u52a1\u8d1f\u8f7d\u548c\u8d44\u6e90\u7d27\u5f20\u7a0b\u5ea6\u3002",
        "category": "basic",
        "unit": "percentunit",
        "panelType": "timeseries",
        "colorMode": "palette-classic",
    },
    "up": {
        "displayName": "\u76ee\u6807\u5728\u7ebf\u72b6\u6001",
        "description": "\u0050\u0072\u006f\u006d\u0065\u0074\u0068\u0065\u0075\u0073 \u5bf9\u91c7\u96c6\u76ee\u6807\u7684\u5b58\u6d3b\u68c0\u6d4b\uff0c\u0031 \u8868\u793a\u53ef\u6293\u53d6\uff0c\u0030 \u8868\u793a\u4e0d\u53ef\u8fbe\u3002",
        "category": "basic",
        "unit": "short",
        "panelType": "stat",
        "colorMode": "background",
    },
    "yunmon_business_orders_processed_total": {
        "displayName": "\u8ba2\u5355\u5904\u7406\u603b\u6570",
        "description": "\u4e1a\u52a1\u5e94\u7528\u7d2f\u8ba1\u5904\u7406\u6210\u529f\u7684\u8ba2\u5355\u6570\u91cf\u3002",
        "category": "business",
        "unit": "short",
        "panelType": "stat",
        "colorMode": "value",
    },
    "yunmon_business_orders_failed_total": {
        "displayName": "\u8ba2\u5355\u5931\u8d25\u603b\u6570",
        "description": "\u4e1a\u52a1\u5e94\u7528\u7d2f\u8ba1\u5904\u7406\u5931\u8d25\u7684\u8ba2\u5355\u6570\u91cf\u3002",
        "category": "business",
        "unit": "short",
        "panelType": "stat",
        "colorMode": "background",
    },
    "yunmon_business_queue_depth": {
        "displayName": "\u4e1a\u52a1\u961f\u5217\u6df1\u5ea6",
        "description": "\u4e1a\u52a1\u5e94\u7528\u5f53\u524d\u5f85\u5904\u7406\u961f\u5217\u7684\u5806\u79ef\u6df1\u5ea6\uff0c\u53ef\u7528\u4e8e\u89c2\u5bdf\u79ef\u538b\u60c5\u51b5\u3002",
        "category": "business",
        "unit": "short",
        "panelType": "gauge",
        "colorMode": "value",
    },
}

PREFIX_METRIC_HINTS = [
    {
        "prefix": "service:",
        "displayName": "\u670d\u52a1\u7ec4\u5408\u6307\u6807",
        "description": "\u8fd9\u662f\u6309\u670d\u52a1\u7ef4\u5ea6\u805a\u5408\u8ba1\u7b97\u51fa\u6765\u7684\u7ec4\u5408\u6307\u6807\uff0c\u53ef\u7528\u4e8e\u670d\u52a1\u5047\u5eb7\u5ea6\u8bc4\u4f30\u3002",
        "category": "composite",
        "unit": "short",
        "panelType": "timeseries",
        "colorMode": "palette-classic",
        "sourceType": "recording_rule",
    },
    {
        "prefix": "platform:",
        "displayName": "\u5e73\u53f0\u5b8f\u89c2\u6307\u6807",
        "description": "\u8fd9\u662f\u9762\u5411\u5e73\u53f0\u6574\u4f53\u8fd0\u884c\u6001\u52bf\u7684\u5b8f\u89c2\u6307\u6807\uff0c\u9002\u5408\u7528\u6765\u770b\u6574\u4f53\u89c4\u6a21\u548c\u5728\u7ebf\u72b6\u6001\u3002",
        "category": "macro",
        "unit": "short",
        "panelType": "stat",
        "colorMode": "background",
        "sourceType": "recording_rule",
    },
    {
        "prefix": "docker_",
        "displayName": "\u5bb9\u5668\u8fd0\u884c\u6307\u6807",
        "description": "\u8fd9\u662f Docker \u5bb9\u5668\u8fd0\u884c\u65f6\u91c7\u96c6\u7684\u57fa\u7840\u8d44\u6e90\u6307\u6807\uff0c\u53ef\u7528\u4e8e\u5bb9\u5668 CPU\u3001\u5185\u5b58\u3001\u7f51\u7edc\u548c IO \u76d1\u63a7\u3002",
        "category": "basic",
        "unit": "short",
        "panelType": "timeseries",
        "colorMode": "palette-classic",
        "sourceType": "raw",
    },
    {
        "prefix": "control_plane_",
        "displayName": "\u63a7\u5236\u9762\u8fd0\u884c\u6307\u6807",
        "description": "\u8fd9\u662f control-plane \u81ea\u8eab\u66b4\u9732\u7684\u8fd0\u884c\u6307\u6807\uff0c\u53ef\u7528\u4e8e\u89c2\u5bdf\u914d\u7f6e\u53d1\u5e03\u548c\u63a7\u5236\u53f0\u8d1f\u8f7d\u72b6\u6001\u3002",
        "category": "basic",
        "unit": "short",
        "panelType": "timeseries",
        "colorMode": "palette-classic",
        "sourceType": "raw",
    },
    {
        "prefix": "stack_agent_",
        "displayName": "\u5bbf\u4e3b\u673a\u4ee3\u7406\u6307\u6807",
        "description": "\u8fd9\u662f host stack-agent \u66b4\u9732\u7684\u5bbf\u4e3b\u673a\u6267\u884c\u6307\u6807\uff0c\u53ef\u7528\u4e8e\u89c2\u5bdf\u91cd\u5efa\u3001\u91cd\u542f\u548c\u534f\u8c03\u72b6\u6001\u3002",
        "category": "basic",
        "unit": "short",
        "panelType": "timeseries",
        "colorMode": "palette-classic",
        "sourceType": "raw",
    },
    {
        "prefix": "yunmon_business_",
        "displayName": "\u4e1a\u52a1\u5e94\u7528\u6307\u6807",
        "description": "\u8fd9\u662f\u4e1a\u52a1\u5e94\u7528\u81ea\u5b9a\u4e49\u66b4\u9732\u7684\u76d1\u6d4b\u6307\u6807\uff0c\u53ef\u4f53\u73b0\u8ba2\u5355\u3001\u961f\u5217\u548c\u4e1a\u52a1\u6210\u679c\u7b49\u4fe1\u606f\u3002",
        "category": "business",
        "unit": "short",
        "panelType": "stat",
        "colorMode": "value",
        "sourceType": "raw",
    },
]

CANONICAL_METRIC_CATALOG = {
    "categories": [
        {
            "id": "basic",
            "name": "\u57fa\u7840\u6307\u6807",
            "description": "\u76f4\u63a5\u6765\u6e90\u4e8e\u5e94\u7528\u3001\u5bb9\u5668\u6216\u5e73\u53f0\u91c7\u96c6\u94fe\u8def\u7684\u539f\u59cb\u6307\u6807\u3002",
        },
        {
            "id": "business",
            "name": "\u4e1a\u52a1\u6307\u6807",
            "description": "\u53cd\u6620\u4e1a\u52a1\u5e94\u7528\u8fd0\u884c\u6548\u679c\u3001\u5904\u7406\u7ed3\u679c\u548c\u6392\u961f\u72b6\u6001\u7684\u4e13\u5c5e\u6307\u6807\u76ee\u5f55\u3002",
        },
        {
            "id": "composite",
            "name": "\u7ec4\u5408\u6307\u6807",
            "description": "\u901a\u8fc7\u591a\u4e2a\u57fa\u7840\u6307\u6807\u6216\u8bb0\u5f55\u89c4\u5219\u7ec4\u5408\u800c\u6210\u7684\u670d\u52a1\u7ea7\u6307\u6807\u3002",
        },
        {
            "id": "macro",
            "name": "\u5b8f\u89c2\u6307\u6807",
            "description": "\u53cd\u6620\u5e73\u53f0\u6574\u4f53\u5065\u5eb7\u5ea6\u3001\u89c4\u6a21\u548c\u6cbb\u7406\u6548\u679c\u7684\u5b8f\u89c2\u89c6\u89d2\u6307\u6807\u3002",
        },
    ],
    "items": [
        {
            "metricId": "http_server_requests_total",
            "metricName": "http_server_requests_seconds_count",
            "displayName": "HTTP \u8bf7\u6c42\u603b\u6570",
            "category": "basic",
            "sourceType": "raw",
            "ruleMode": "external",
            "description": "\u5e94\u7528\u66b4\u9732\u7684 HTTP \u8bf7\u6c42\u7d2f\u8ba1\u8ba1\u6570\uff0c\u53ef\u7528\u4e8e\u8ba1\u7b97\u541e\u5410\u7387\u3001\u9519\u8bef\u7387\u548c\u5ef6\u8fdf\u6307\u6807\u3002",
            "expression": "",
            "derivedFrom": [],
            "unit": "short",
            "enabled": True,
            "visualization": {
                "panelType": "timeseries",
                "unit": "short",
                "decimals": 0,
                "colorMode": "palette-classic",
                "showOnDashboard": False,
            },
        },
        {
            "metricId": "jvm_memory_used_bytes",
            "metricName": "jvm_memory_used_bytes",
            "displayName": "JVM \u5185\u5b58\u4f7f\u7528\u91cf",
            "category": "basic",
            "sourceType": "raw",
            "ruleMode": "external",
            "description": "\u5e94\u7528 JVM \u5f53\u524d\u5df2\u4f7f\u7528\u5185\u5b58\uff0c\u7528\u4e8e\u89c2\u5bdf\u5806\u548c\u975e\u5806\u8d44\u6e90\u5360\u7528\u53d8\u5316\u3002",
            "expression": "",
            "derivedFrom": [],
            "unit": "bytes",
            "enabled": True,
            "visualization": {
                "panelType": "timeseries",
                "unit": "bytes",
                "decimals": 0,
                "colorMode": "palette-classic",
                "showOnDashboard": False,
            },
        },
        {
            "metricId": "process_cpu_usage",
            "metricName": "process_cpu_usage",
            "displayName": "\u8fdb\u7a0b CPU \u4f7f\u7528\u7387",
            "category": "basic",
            "sourceType": "raw",
            "ruleMode": "external",
            "description": "\u5e94\u7528\u8fdb\u7a0b CPU \u4f7f\u7528\u7387\uff0c\u53ef\u4f5c\u4e3a\u670d\u52a1\u8d1f\u8f7d\u548c\u6027\u80fd\u5206\u6790\u7684\u57fa\u7ebf\u6307\u6807\u3002",
            "expression": "",
            "derivedFrom": [],
            "unit": "percentunit",
            "enabled": True,
            "visualization": {
                "panelType": "timeseries",
                "unit": "percentunit",
                "decimals": 3,
                "colorMode": "palette-classic",
                "showOnDashboard": False,
            },
        },
        {
            "metricId": "business_orders_processed_total",
            "metricName": "yunmon_business_orders_processed_total",
            "displayName": "\u8ba2\u5355\u5904\u7406\u603b\u6570",
            "category": "business",
            "sourceType": "raw",
            "ruleMode": "external",
            "description": "\u793a\u4f8b\u4e1a\u52a1\u7d2f\u8ba1\u5904\u7406\u6210\u529f\u7684\u8ba2\u5355\u6570\u91cf\u3002",
            "expression": "",
            "derivedFrom": [],
            "unit": "short",
            "enabled": True,
            "visualization": {
                "panelType": "stat",
                "unit": "short",
                "decimals": 0,
                "colorMode": "value",
                "showOnDashboard": True,
            },
        },
        {
            "metricId": "business_orders_failed_total",
            "metricName": "yunmon_business_orders_failed_total",
            "displayName": "\u8ba2\u5355\u5931\u8d25\u603b\u6570",
            "category": "business",
            "sourceType": "raw",
            "ruleMode": "external",
            "description": "\u793a\u4f8b\u4e1a\u52a1\u7d2f\u8ba1\u5904\u7406\u5931\u8d25\u7684\u8ba2\u5355\u6570\u91cf\u3002",
            "expression": "",
            "derivedFrom": [],
            "unit": "short",
            "enabled": True,
            "visualization": {
                "panelType": "stat",
                "unit": "short",
                "decimals": 0,
                "colorMode": "background",
                "showOnDashboard": True,
            },
        },
        {
            "metricId": "business_queue_depth",
            "metricName": "yunmon_business_queue_depth",
            "displayName": "\u4e1a\u52a1\u961f\u5217\u6df1\u5ea6",
            "category": "business",
            "sourceType": "raw",
            "ruleMode": "external",
            "description": "\u793a\u4f8b\u4e1a\u52a1\u5f53\u524d\u5f85\u5904\u7406\u961f\u5217\u6df1\u5ea6\u3002",
            "expression": "",
            "derivedFrom": [],
            "unit": "short",
            "enabled": True,
            "visualization": {
                "panelType": "gauge",
                "unit": "short",
                "decimals": 0,
                "colorMode": "value",
                "showOnDashboard": True,
            },
        },
        {
            "metricId": "business_orders_failure_ratio",
            "metricName": "business:orders:failure_ratio",
            "displayName": "\u8ba2\u5355\u5931\u8d25\u5360\u6bd4",
            "category": "composite",
            "sourceType": "recording_rule",
            "ruleMode": "managed",
            "description": "\u7531\u8ba2\u5355\u6210\u529f\u603b\u6570\u548c\u5931\u8d25\u603b\u6570\u7ec4\u5408\u8ba1\u7b97\u51fa\u7684\u4e1a\u52a1\u5931\u8d25\u5360\u6bd4\u3002",
            "expression": 'yunmon_business_orders_failed_total / clamp_min(yunmon_business_orders_processed_total + yunmon_business_orders_failed_total, 1)',
            "derivedFrom": ["yunmon_business_orders_failed_total", "yunmon_business_orders_processed_total"],
            "unit": "percentunit",
            "enabled": True,
            "visualization": {
                "panelType": "gauge",
                "unit": "percentunit",
                "decimals": 3,
                "colorMode": "thresholds",
                "showOnDashboard": True,
            },
        },
        {
            "metricId": "http_requests_rate1m",
            "metricName": "service:http_requests:rate1m",
            "displayName": "HTTP \u541e\u5410\u7387(1m)",
            "category": "composite",
            "sourceType": "recording_rule",
            "ruleMode": "external",
            "description": "\u6309\u670d\u52a1\u805a\u5408\u7684 1 \u5206\u949f HTTP \u8bf7\u6c42\u901f\u7387\u3002",
            "expression": 'sum by (service, status) (rate(http_server_requests_seconds_count{job="applications"}[1m]))',
            "derivedFrom": ["http_server_requests_seconds_count"],
            "unit": "reqps",
            "enabled": True,
            "visualization": {
                "panelType": "timeseries",
                "unit": "reqps",
                "decimals": 2,
                "colorMode": "palette-classic",
                "showOnDashboard": True,
            },
        },
        {
            "metricId": "http_errors_ratio5m",
            "metricName": "service:http_errors:ratio5m",
            "displayName": "HTTP 5xx \u9519\u8bef\u7387(5m)",
            "category": "composite",
            "sourceType": "recording_rule",
            "ruleMode": "external",
            "description": "\u6309\u670d\u52a1\u805a\u5408\u7684 5 \u5206\u949f HTTP 5xx \u9519\u8bef\u6bd4\u4f8b\u3002",
            "expression": 'sum by (service) (rate(http_server_requests_seconds_count{job="applications",status=~"5.."}[5m])) / clamp_min(sum by (service) (rate(http_server_requests_seconds_count{job="applications"}[5m])), 0.001)',
            "derivedFrom": ["http_server_requests_seconds_count"],
            "unit": "percentunit",
            "enabled": True,
            "visualization": {
                "panelType": "timeseries",
                "unit": "percentunit",
                "decimals": 3,
                "colorMode": "thresholds",
                "showOnDashboard": True,
            },
        },
        {
            "metricId": "http_latency_p95_5m",
            "metricName": "service:http_latency:p95_5m",
            "displayName": "HTTP P95 \u5ef6\u8fdf(5m)",
            "category": "composite",
            "sourceType": "recording_rule",
            "ruleMode": "external",
            "description": "\u6309\u670d\u52a1\u805a\u5408\u7684 5 \u5206\u949f P95 HTTP \u5ef6\u8fdf\u3002",
            "expression": 'histogram_quantile(0.95, sum by (service, le) (rate(http_server_requests_seconds_bucket{job="applications"}[5m])))',
            "derivedFrom": ["http_server_requests_seconds_bucket"],
            "unit": "s",
            "enabled": True,
            "visualization": {
                "panelType": "timeseries",
                "unit": "s",
                "decimals": 3,
                "colorMode": "palette-classic",
                "showOnDashboard": True,
            },
        },
        {
            "metricId": "applications_up_total",
            "metricName": "platform:applications:up_total",
            "displayName": "\u5728\u7ebf\u5e94\u7528\u6570",
            "category": "macro",
            "sourceType": "recording_rule",
            "ruleMode": "managed",
            "description": "\u5f53\u524d\u5df2\u7eb3\u5165\u76d1\u7ba1\u5e76\u5728\u7ebf\u7684\u5e94\u7528\u5b9e\u4f8b\u603b\u6570\u3002",
            "expression": 'sum(up{job="applications"})',
            "derivedFrom": ["up"],
            "unit": "short",
            "enabled": True,
            "visualization": {
                "panelType": "stat",
                "unit": "short",
                "decimals": 0,
                "colorMode": "background",
                "showOnDashboard": True,
            },
        },
        {
            "metricId": "applications_up_ratio",
            "metricName": "platform:applications:up_ratio",
            "displayName": "\u5e94\u7528\u5728\u7ebf\u7387",
            "category": "macro",
            "sourceType": "recording_rule",
            "ruleMode": "managed",
            "description": "\u5f53\u524d\u5e94\u7528\u5b9e\u4f8b\u7684\u603b\u4f53\u5728\u7ebf\u6bd4\u4f8b\u3002",
            "expression": 'sum(up{job="applications"}) / clamp_min(count(up{job="applications"}), 1)',
            "derivedFrom": ["up"],
            "unit": "percentunit",
            "enabled": True,
            "visualization": {
                "panelType": "gauge",
                "unit": "percentunit",
                "decimals": 3,
                "colorMode": "thresholds",
                "showOnDashboard": True,
            },
        },
    ],
}
DEFAULT_STATE["metricCatalog"] = json.loads(json.dumps(CANONICAL_METRIC_CATALOG, ensure_ascii=False))


def bump_metric(key, delta=1):
    with METRICS_LOCK:
        METRICS[key] = METRICS.get(key, 0) + delta


def set_metric(key, value):
    with METRICS_LOCK:
        METRICS[key] = value


def snapshot_metrics():
    with METRICS_LOCK:
        return dict(METRICS)


def deep_merge(defaults, data):
    if isinstance(defaults, dict):
        result = {}
        data = data if isinstance(data, dict) else {}
        for key, value in defaults.items():
            result[key] = deep_merge(value, data.get(key))
        for key, value in data.items():
            if key not in result:
                result[key] = value
        return result
    return defaults if data is None else data


def slugify_metric_id(metric_name):
    characters = []
    for char in str(metric_name or "").lower():
        if char.isalnum():
            characters.append(char)
        else:
            characters.append("_")
    value = "".join(characters).strip("_")
    while "__" in value:
        value = value.replace("__", "_")
    return value or "managed_metric"


def humanize_metric_name(metric_name):
    text = str(metric_name or "").replace(":", " ").replace(".", " ").replace("_", " ").strip()
    if not text:
        return "未命名指标"
    tokens = [token for token in text.split() if token]
    if not tokens:
        return "未命名指标"
    normalized = []
    for token in tokens:
        if token.isupper():
            normalized.append(token)
        elif token.lower() in {"http", "jvm", "cpu", "io", "p95", "p99", "5xx"}:
            normalized.append(token.upper())
        else:
            normalized.append(token.capitalize())
    return " ".join(normalized)


def infer_metric_profile(metric_name):
    metric_name = str(metric_name or "").strip()
    if metric_name in EXACT_METRIC_HINTS:
        return dict(EXACT_METRIC_HINTS[metric_name])
    for entry in PREFIX_METRIC_HINTS:
        if metric_name.startswith(entry["prefix"]):
            profile = dict(entry)
            profile.pop("prefix", None)
            return profile
    return {
        "displayName": humanize_metric_name(metric_name),
        "description": "\u8fd9\u662f Prometheus \u5df2\u53d1\u73b0\u7684\u5b9e\u65f6\u6307\u6807\uff0c\u5f53\u524d\u8fd8\u672a\u7eb3\u5165\u6307\u6807\u76ee\u5f55\uff0c\u5efa\u8bae\u6839\u636e\u5b9e\u9645\u4e1a\u52a1\u542b\u4e49\u8865\u5145\u540d\u79f0\u3001\u4f5c\u7528\u548c\u53ef\u89c6\u5316\u65b9\u5f0f\u3002",
        "category": "basic",
        "unit": "short",
        "panelType": "timeseries",
        "colorMode": "palette-classic",
        "sourceType": "raw",
    }


def build_metric_template(metric_name, category_id=None):
    profile = infer_metric_profile(metric_name)
    category = category_id or profile.get("category") or "basic"
    source_type = profile.get("sourceType") or ("recording_rule" if ":" in metric_name else "raw")
    rule_mode = "external"
    return {
        "metricId": slugify_metric_id(metric_name),
        "metricName": metric_name,
        "displayName": profile["displayName"],
        "category": category,
        "sourceType": source_type,
        "ruleMode": rule_mode,
        "description": profile["description"],
        "expression": "",
        "derivedFrom": [],
        "unit": profile.get("unit", "short"),
        "enabled": True,
        "visualization": {
            "panelType": profile.get("panelType", "timeseries"),
            "unit": profile.get("unit", "short"),
            "decimals": 0,
            "colorMode": profile.get("colorMode", "palette-classic"),
            "showOnDashboard": False,
        },
    }


def normalize_metric_catalog(state):
    metric_catalog = state.setdefault("metricCatalog", {})
    current_categories = metric_catalog.get("categories", [])
    current_items = metric_catalog.get("items", [])

    category_map = {
        item.get("id"): item
        for item in current_categories
        if isinstance(item, dict) and str(item.get("id", "")).strip()
    }
    normalized_categories = []
    seen_category_ids = set()
    for canonical in CANONICAL_METRIC_CATALOG["categories"]:
        normalized_categories.append(
            {
                "id": canonical["id"],
                "name": canonical["name"],
                "description": canonical["description"],
            }
        )
        seen_category_ids.add(canonical["id"])
    for category in current_categories:
        if not isinstance(category, dict):
            continue
        category_id = str(category.get("id", "")).strip()
        if not category_id or category_id in seen_category_ids:
            continue
        normalized_categories.append(
            {
                "id": category_id,
                "name": str(category.get("name", "")).strip() or category_id,
                "description": str(category.get("description", "")).strip(),
            }
        )
        seen_category_ids.add(category_id)
    metric_catalog["categories"] = normalized_categories

    current_item_map = {
        item.get("metricId"): item
        for item in current_items
        if isinstance(item, dict) and str(item.get("metricId", "")).strip()
    }
    normalized_items = []
    seen_metric_ids = set()
    for canonical in CANONICAL_METRIC_CATALOG["items"]:
        current = current_item_map.get(canonical["metricId"], {})
        merged = deep_merge(canonical, current)
        if canonical["metricId"] in LEGACY_BUSINESS_METRIC_IDS and str(current.get("category", "")).strip() in {"", "basic"}:
            merged["category"] = "business"
        merged["displayName"] = canonical["displayName"]
        merged["description"] = canonical["description"]
        if not isinstance(merged.get("visualization"), dict):
            merged["visualization"] = dict(canonical["visualization"])
        normalized_items.append(merged)
        seen_metric_ids.add(canonical["metricId"])
    for item in current_items:
        if not isinstance(item, dict):
            continue
        metric_id = str(item.get("metricId", "")).strip()
        if not metric_id or metric_id in seen_metric_ids:
            continue
        normalized_items.append(item)
        seen_metric_ids.add(metric_id)
    metric_catalog["items"] = normalized_items
    return state


def timestamp_now():
    return datetime.now(timezone.utc).isoformat()


def yaml_scalar(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def env_value(value):
    text = str(value)
    if not text:
        return '""'
    if any(ch in text for ch in [' ', '"', "'", "#", ":", "\n", "\r", "\t"]):
        escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{escaped}"'
    return text


def format_ports(ports):
    mappings = []
    for port in ports or []:
        private_port = port.get("PrivatePort")
        public_port = port.get("PublicPort")
        port_type = port.get("Type", "tcp")
        ip_address = port.get("IP") or "0.0.0.0"
        if public_port is None:
            mappings.append(f"{private_port}/{port_type}")
        else:
            mappings.append(f"{ip_address}:{public_port}->{private_port}/{port_type}")
    return mappings


def service_sort_key(service):
    value = service.get("service") or service.get("name") or ""
    return (SERVICE_ORDER.index(value) if value in SERVICE_ORDER else len(SERVICE_ORDER), value)


def application_sort_key(application):
    display = application.get("displayName") or application.get("serviceName") or application.get("appId") or ""
    return display.lower()


def normalize_application_item(item):
    return {
        "appId": str(item.get("appId", "")).strip(),
        "enabled": bool(item.get("enabled", False)),
        "displayName": str(item.get("displayName", "")).strip(),
        "serviceName": str(item.get("serviceName", "")).strip(),
        "targetPort": item.get("targetPort"),
        "metricsPath": str(item.get("metricsPath", "")).strip(),
        "environment": str(item.get("environment", "")).strip(),
    }


def application_items_by_id(state):
    items = {}
    for item in state["applications"].get("items", []):
        normalized = normalize_application_item(item)
        if normalized["appId"]:
            items[normalized["appId"]] = normalized
    return items


def container_scrape_targets(container, target_port):
    targets = []
    for port in container.get("rawPorts", []):
        if port.get("PrivatePort") == target_port and port.get("PublicPort"):
            targets.append(f"host.docker.internal:{port['PublicPort']}")
    if targets:
        return targets
    return [f"{ip_address}:{target_port}" for ip_address in container.get("networkIps", [])]


def metric_category_map(state):
    return {item["id"]: item for item in state["metricCatalog"].get("categories", [])}


def metric_items(state):
    return state["metricCatalog"].get("items", [])


def metric_sort_key(metric, category_order):
    return (
        category_order.index(metric.get("category")) if metric.get("category") in category_order else len(category_order),
        metric.get("displayName", ""),
    )


def discover_live_metric_names():
    connection = http.client.HTTPConnection("prometheus", 9090, timeout=10)
    try:
        connection.request("GET", "/api/v1/label/__name__/values")
        response = connection.getresponse()
        body = response.read().decode("utf-8", errors="replace")
        if response.status >= 400:
            raise RuntimeError(f"Prometheus metric discovery failed with {response.status}: {body}")
        payload = json.loads(body)
        return sorted(payload.get("data", []))
    finally:
        connection.close()


def filtered_live_metric_names(state):
    catalog_names = {item["metricName"] for item in metric_items(state)}
    prefixes = (
        "yunmon_",
        "service:",
        "platform:",
        "docker_",
        "http_server_requests",
        "jvm_",
        "process_",
        "up",
        "control_plane_",
        "stack_agent_",
    )
    try:
        names = discover_live_metric_names()
    except Exception:
        return []
    filtered = [name for name in names if name in catalog_names or name.startswith(prefixes)]
    return sorted(set(filtered))


def build_metric_catalog_view(state):
    live_names = set(filtered_live_metric_names(state))
    category_order = [item["id"] for item in state["metricCatalog"].get("categories", [])]
    category_lookup = metric_category_map(state)
    items = []
    for metric in sorted(metric_items(state), key=lambda item: metric_sort_key(item, category_order)):
        metric_view = dict(metric)
        metric_view["live"] = metric["metricName"] in live_names
        metric_view["purpose"] = metric.get("description", "")
        metric_view["categoryName"] = category_lookup.get(metric.get("category"), {}).get("name", metric.get("category"))
        items.append(metric_view)
    unmanaged = [
        {
            **build_metric_template(name),
            "metricName": name,
            "live": True,
            "purpose": infer_metric_profile(name)["description"],
            "recommendedCategory": infer_metric_profile(name)["category"],
            "recommendedCategoryName": category_lookup.get(infer_metric_profile(name)["category"], {}).get(
                "name",
                infer_metric_profile(name)["category"],
            ),
            "suggestedItem": build_metric_template(name),
        }
        for name in live_names
        if name not in {item["metricName"] for item in items}
    ]
    return {
        "categories": state["metricCatalog"]["categories"],
        "items": items,
        "liveMetrics": sorted(live_names),
        "unmanagedLiveMetrics": unmanaged,
    }


def render_metric_catalog_rules(state):
    managed_items = [
        item
        for item in metric_items(state)
        if item.get("enabled") and item.get("sourceType") == "recording_rule" and item.get("ruleMode") == "managed"
    ]
    category_groups = {}
    for item in managed_items:
        category_groups.setdefault(item["category"], []).append(item)

    lines = ["groups:"]
    if not category_groups:
        lines.append("  - name: metric_catalog_managed")
        lines.append("    interval: 30s")
        lines.append("    rules: []")
        return "\n".join(lines) + "\n"

    for category in [entry["id"] for entry in state["metricCatalog"]["categories"]]:
        items = category_groups.get(category, [])
        if not items:
            continue
        lines.append(f"  - name: metric_catalog_{category}")
        lines.append("    interval: 30s")
        lines.append("    rules:")
        for item in items:
            lines.append(f"      - record: {item['metricName']}")
            lines.append(f"        expr: {item['expression']}")
            lines.append("        labels:")
            lines.append(f"          metric_catalog_id: {item['metricId']}")
            lines.append(f"          metric_category: {item['category']}")
    return "\n".join(lines) + "\n"


def dashboard_panel_type(metric):
    panel_type = metric.get("visualization", {}).get("panelType", "stat")
    return panel_type if panel_type in {"timeseries", "stat", "gauge"} else "stat"


def render_metric_dashboard(state):
    panels = []
    y_position = 0
    panel_id = 1
    category_map = metric_category_map(state)
    category_order = [item["id"] for item in state["metricCatalog"]["categories"]]
    visible_metrics = [
        item
        for item in sorted(metric_items(state), key=lambda metric: metric_sort_key(metric, category_order))
        if item.get("enabled") and item.get("visualization", {}).get("showOnDashboard", False)
    ]

    for metric in visible_metrics:
        panel_type = dashboard_panel_type(metric)
        width = 12 if panel_type == "timeseries" else 8
        height = 9 if panel_type == "timeseries" else 8
        x_position = 0 if panel_id % 2 else 12
        if panel_type != "timeseries":
            x_position = ((panel_id - 1) % 3) * 8
        if x_position == 0 and panel_id > 1:
            y_position += height
        field_config = {
            "defaults": {
                "unit": metric["visualization"].get("unit") or metric.get("unit") or "short",
                "decimals": metric["visualization"].get("decimals", 0),
                "color": {"mode": metric["visualization"].get("colorMode", "palette-classic")},
            },
            "overrides": [],
        }
        if panel_type in {"stat", "gauge"}:
            field_config["defaults"]["thresholds"] = {
                "mode": "absolute",
                "steps": [
                    {"color": "green", "value": None},
                    {"color": "orange", "value": 0.7 if metric.get("unit") == "percentunit" else None},
                ],
            }
        panel = {
            "datasource": {"type": "prometheus", "uid": "prometheus"},
            "fieldConfig": field_config,
            "gridPos": {"h": height, "w": width, "x": x_position, "y": y_position},
            "id": panel_id,
            "targets": [
                {
                    "expr": metric["metricName"],
                    "legendFormat": metric["displayName"],
                    "refId": "A",
                }
            ],
            "title": f"{metric['displayName']} · {category_map.get(metric['category'], {}).get('name', metric['category'])}",
            "type": panel_type,
        }
        if panel_type == "timeseries":
            panel["options"] = {
                "legend": {"displayMode": "table", "placement": "bottom"},
                "tooltip": {"mode": "single"},
            }
        elif panel_type == "stat":
            panel["options"] = {
                "reduceOptions": {"values": False, "calcs": ["lastNotNull"], "fields": ""},
                "orientation": "auto",
                "textMode": "auto",
                "colorMode": "value",
                "graphMode": "area",
                "justifyMode": "auto",
            }
        else:
            panel["options"] = {
                "reduceOptions": {"values": False, "calcs": ["lastNotNull"], "fields": ""},
                "showThresholdLabels": False,
                "showThresholdMarkers": True,
            }
        panels.append(panel)
        panel_id += 1

    dashboard = {
        "annotations": {
            "list": [
                {
                    "builtIn": 1,
                    "datasource": {"type": "grafana", "uid": "-- Grafana --"},
                    "enable": True,
                    "hide": True,
                    "iconColor": "rgba(0, 211, 255, 1)",
                    "name": "Annotations & Alerts",
                    "type": "dashboard",
                }
            ]
        },
        "editable": True,
        "graphTooltip": 0,
        "id": None,
        "panels": panels,
        "refresh": "30s",
        "schemaVersion": 39,
        "tags": ["yun-mon", "metric-catalog"],
        "time": {"from": "now-1h", "to": "now"},
        "title": "Yun-mon Metric Catalog",
        "uid": "yunmon-metric-catalog",
        "version": 1,
    }
    return json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n"


def save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_state():
    raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return normalize_metric_catalog(deep_merge(DEFAULT_STATE, raw))


def ensure_state_file():
    if not STATE_PATH.exists():
        save_state(DEFAULT_STATE)


def validate_state(state):
    required_strings = [
        ("system.monitoringProject", state["system"]["monitoringProject"]),
        ("system.environment", state["system"]["environment"]),
        ("system.clusterName", state["system"]["clusterName"]),
        ("grafana.adminUser", state["grafana"]["adminUser"]),
        ("grafana.adminPassword", state["grafana"]["adminPassword"]),
        ("demoService.appEnv", state["demoService"]["appEnv"]),
        ("demoService.logDir", state["demoService"]["logDir"]),
        ("demoService.javaOpts", state["demoService"]["javaOpts"]),
        ("demoService.serviceName", state["demoService"]["serviceName"]),
        ("demoService.metricsPath", state["demoService"]["metricsPath"]),
        ("applications.defaults.metricsPath", state["applications"]["defaults"]["metricsPath"]),
        ("applications.defaults.environment", state["applications"]["defaults"]["environment"]),
        ("metricCatalog.categories[0].name", state["metricCatalog"]["categories"][0]["name"] if state["metricCatalog"]["categories"] else ""),
        ("prometheus.scrapeInterval", state["prometheus"]["scrapeInterval"]),
        ("prometheus.evaluationInterval", state["prometheus"]["evaluationInterval"]),
        ("prometheus.dockerDiscoveryRefreshInterval", state["prometheus"]["dockerDiscoveryRefreshInterval"]),
        ("prometheus.externalLabels.cluster", state["prometheus"]["externalLabels"]["cluster"]),
        ("prometheus.externalLabels.env", state["prometheus"]["externalLabels"]["env"]),
        ("alertmanager.resolveTimeout", state["alertmanager"]["resolveTimeout"]),
        ("alertmanager.groupWait", state["alertmanager"]["groupWait"]),
        ("alertmanager.groupInterval", state["alertmanager"]["groupInterval"]),
        ("alertmanager.repeatInterval", state["alertmanager"]["repeatInterval"]),
        ("loki.pathPrefix", state["loki"]["pathPrefix"]),
        ("promtail.positionsFile", state["promtail"]["positionsFile"]),
        ("promtail.clientUrl", state["promtail"]["clientUrl"]),
        ("promtail.logPath", state["promtail"]["logPath"]),
        ("dockerStatsExporter.targetProject", state["dockerStatsExporter"]["targetProject"]),
        ("cadvisor.housekeepingInterval", state["cadvisor"]["housekeepingInterval"]),
        ("stackAgent.baseUrl", state["stackAgent"]["baseUrl"]),
        ("stackAgent.sharedToken", state["stackAgent"]["sharedToken"]),
    ]
    for key, value in required_strings:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string")

    if not isinstance(state["alertmanager"]["groupBy"], list) or not state["alertmanager"]["groupBy"]:
        raise ValueError("alertmanager.groupBy must be a non-empty list")
    if any(not isinstance(item, str) or not item.strip() for item in state["alertmanager"]["groupBy"]):
        raise ValueError("alertmanager.groupBy items must be non-empty strings")

    bool_fields = [
        ("grafana.allowSignUp", state["grafana"]["allowSignUp"]),
        ("demoService.monitoringEnabled", state["demoService"]["monitoringEnabled"]),
        ("applications.autoDiscoveryEnabled", state["applications"]["autoDiscoveryEnabled"]),
        ("applications.defaults.enabled", state["applications"]["defaults"]["enabled"]),
        ("loki.authEnabled", state["loki"]["authEnabled"]),
        ("loki.reportingEnabled", state["loki"]["reportingEnabled"]),
        ("cadvisor.dockerOnly", state["cadvisor"]["dockerOnly"]),
        ("stackAgent.enabled", state["stackAgent"]["enabled"]),
    ]
    for key, value in bool_fields:
        if not isinstance(value, bool):
            raise ValueError(f"{key} must be a boolean")

    categories = state["metricCatalog"].get("categories", [])
    if not isinstance(categories, list) or not categories:
        raise ValueError("metricCatalog.categories must be a non-empty list")
    seen_category_ids = set()
    for category in categories:
        if not isinstance(category, dict):
            raise ValueError("metricCatalog.categories entries must be objects")
        category_id = str(category.get("id", "")).strip()
        category_name = str(category.get("name", "")).strip()
        if not category_id or not category_name:
            raise ValueError("metricCatalog.categories entries must define id and name")
        if category_id in seen_category_ids:
            raise ValueError(f"Duplicate metric category id: {category_id}")
        seen_category_ids.add(category_id)

    metric_items = state["metricCatalog"].get("items", [])
    if not isinstance(metric_items, list):
        raise ValueError("metricCatalog.items must be a list")
    seen_metric_ids = set()
    seen_metric_names = set()
    for item in metric_items:
        if not isinstance(item, dict):
            raise ValueError("metricCatalog.items entries must be objects")
        metric_id = str(item.get("metricId", "")).strip()
        metric_name = str(item.get("metricName", "")).strip()
        display_name = str(item.get("displayName", "")).strip()
        category = str(item.get("category", "")).strip()
        source_type = str(item.get("sourceType", "")).strip()
        rule_mode = str(item.get("ruleMode", "")).strip()
        unit = str(item.get("unit", "")).strip()
        description = str(item.get("description", "")).strip()
        if not metric_id or not metric_name or not display_name or not category or not source_type or not rule_mode or not unit or not description:
            raise ValueError("metricCatalog.items must define metricId, metricName, displayName, category, sourceType, ruleMode, unit and description")
        if metric_id in seen_metric_ids:
            raise ValueError(f"Duplicate metricCatalog.items metricId: {metric_id}")
        if metric_name in seen_metric_names:
            raise ValueError(f"Duplicate metricCatalog.items metricName: {metric_name}")
        if category not in seen_category_ids:
            raise ValueError(f"metricCatalog.items[{metric_id}].category references unknown category: {category}")
        if source_type not in {"raw", "recording_rule"}:
            raise ValueError(f"metricCatalog.items[{metric_id}].sourceType must be raw or recording_rule")
        if rule_mode not in {"external", "managed"}:
            raise ValueError(f"metricCatalog.items[{metric_id}].ruleMode must be external or managed")
        if metric_id in seen_metric_ids:
            raise ValueError(f"Duplicate metricCatalog.items metricId: {metric_id}")
        seen_metric_ids.add(metric_id)
        seen_metric_names.add(metric_name)
        if not isinstance(item.get("enabled", False), bool):
            raise ValueError(f"metricCatalog.items[{metric_id}].enabled must be a boolean")
        if source_type == "recording_rule" and rule_mode == "managed" and not str(item.get("expression", "")).strip():
            raise ValueError(f"metricCatalog.items[{metric_id}].expression must be defined for managed recording_rule metrics")
        derived_from = item.get("derivedFrom", [])
        if not isinstance(derived_from, list) or any(not isinstance(entry, str) or not entry.strip() for entry in derived_from):
            raise ValueError(f"metricCatalog.items[{metric_id}].derivedFrom must be a list of non-empty strings")
        visualization = item.get("visualization", {})
        if not isinstance(visualization, dict):
            raise ValueError(f"metricCatalog.items[{metric_id}].visualization must be an object")
        panel_type = str(visualization.get("panelType", "")).strip()
        if panel_type not in {"timeseries", "stat", "gauge"}:
            raise ValueError(f"metricCatalog.items[{metric_id}].visualization.panelType must be timeseries, stat or gauge")
        if not isinstance(visualization.get("showOnDashboard", False), bool):
            raise ValueError(f"metricCatalog.items[{metric_id}].visualization.showOnDashboard must be a boolean")
        decimals = visualization.get("decimals", 0)
        if not isinstance(decimals, int) or decimals < 0:
            raise ValueError(f"metricCatalog.items[{metric_id}].visualization.decimals must be a non-negative integer")

    items = state["applications"].get("items", [])
    if not isinstance(items, list):
        raise ValueError("applications.items must be a list")
    seen_app_ids = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("applications.items entries must be objects")
        app_id = str(item.get("appId", "")).strip()
        metrics_path = str(item.get("metricsPath", "")).strip()
        environment = str(item.get("environment", "")).strip()
        if not app_id:
            raise ValueError("applications.items[].appId must be a non-empty string")
        if app_id in seen_app_ids:
            raise ValueError(f"Duplicate applications.items appId: {app_id}")
        seen_app_ids.add(app_id)
        if not metrics_path:
            raise ValueError(f"applications.items[{app_id}].metricsPath must be a non-empty string")
        if not environment:
            raise ValueError(f"applications.items[{app_id}].environment must be a non-empty string")
        if not isinstance(item.get("enabled", False), bool):
            raise ValueError(f"applications.items[{app_id}].enabled must be a boolean")
        if "targetPort" in item and item["targetPort"] is not None:
            if not isinstance(item["targetPort"], int) or item["targetPort"] < 1 or item["targetPort"] > 65535:
                raise ValueError(f"applications.items[{app_id}].targetPort must be between 1 and 65535")

    int_fields = [
        ("ports.grafanaHostPort", state["ports"]["grafanaHostPort"]),
        ("ports.demoServiceHostPort", state["ports"]["demoServiceHostPort"]),
        ("ports.controlPlaneHostPort", state["ports"]["controlPlaneHostPort"]),
        ("ports.prometheusHostPort", state["ports"]["prometheusHostPort"]),
        ("ports.alertmanagerHostPort", state["ports"]["alertmanagerHostPort"]),
        ("ports.lokiHostPort", state["ports"]["lokiHostPort"]),
        ("ports.cadvisorHostPort", state["ports"]["cadvisorHostPort"]),
        ("demoService.monitoringPort", state["demoService"]["monitoringPort"]),
        ("dockerStatsExporter.maxWorkers", state["dockerStatsExporter"]["maxWorkers"]),
        ("loki.replicationFactor", state["loki"]["replicationFactor"]),
    ]
    for key, value in int_fields:
        if not isinstance(value, int):
            raise ValueError(f"{key} must be an integer")
        if "Port" in key or "monitoringPort" in key:
            if value < 1 or value > 65535:
                raise ValueError(f"{key} must be between 1 and 65535")
        if key == "dockerStatsExporter.maxWorkers" and value < 1:
            raise ValueError("dockerStatsExporter.maxWorkers must be >= 1")
        if key == "loki.replicationFactor" and value < 1:
            raise ValueError("loki.replicationFactor must be >= 1")


def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def render_env(state):
    return "\n".join(
        [
            f"MONITORING_PROJECT={env_value(state['system']['monitoringProject'])}",
            f"STACK_AGENT_ENABLED={str(state['stackAgent']['enabled']).lower()}",
            f"STACK_AGENT_BASE_URL={env_value(state['stackAgent']['baseUrl'])}",
            f"STACK_AGENT_SHARED_TOKEN={env_value(state['stackAgent']['sharedToken'])}",
            f"GRAFANA_ADMIN_USER={env_value(state['grafana']['adminUser'])}",
            f"GRAFANA_ADMIN_PASSWORD={env_value(state['grafana']['adminPassword'])}",
            f"GRAFANA_ALLOW_SIGN_UP={str(state['grafana']['allowSignUp']).lower()}",
            f"APP_ENV={env_value(state['demoService']['appEnv'])}",
            f"GRAFANA_HOST_PORT={state['ports']['grafanaHostPort']}",
            f"DEMO_SERVICE_HOST_PORT={state['ports']['demoServiceHostPort']}",
            f"CONTROL_PLANE_HOST_PORT={state['ports']['controlPlaneHostPort']}",
            f"PROMETHEUS_HOST_PORT={state['ports']['prometheusHostPort']}",
            f"ALERTMANAGER_HOST_PORT={state['ports']['alertmanagerHostPort']}",
            f"LOKI_HOST_PORT={state['ports']['lokiHostPort']}",
            f"CADVISOR_HOST_PORT={state['ports']['cadvisorHostPort']}",
            f"DEMO_SERVICE_LOG_DIR={env_value(state['demoService']['logDir'])}",
            f"DEMO_SERVICE_JAVA_OPTS={env_value(state['demoService']['javaOpts'])}",
            f"DEMO_SERVICE_MONITORING_ENABLED={str(state['demoService']['monitoringEnabled']).lower()}",
            f"DEMO_SERVICE_MONITORING_PORT={state['demoService']['monitoringPort']}",
            f"DEMO_SERVICE_SERVICE_NAME={env_value(state['demoService']['serviceName'])}",
            f"DEMO_SERVICE_METRICS_PATH={env_value(state['demoService']['metricsPath'])}",
            f"DOCKER_STATS_EXPORTER_MAX_WORKERS={state['dockerStatsExporter']['maxWorkers']}",
            f"DOCKER_STATS_EXPORTER_TARGET_PROJECT={env_value(state['dockerStatsExporter']['targetProject'])}",
            f"CADVISOR_DOCKER_ONLY={str(state['cadvisor']['dockerOnly']).lower()}",
            f"CADVISOR_HOUSEKEEPING_INTERVAL={env_value(state['cadvisor']['housekeepingInterval'])}",
        ]
    ) + "\n"


def render_prometheus(state):
    cluster_label = state["prometheus"]["externalLabels"]["cluster"]
    env_label = state["prometheus"]["externalLabels"]["env"]
    refresh_interval = state["prometheus"]["dockerDiscoveryRefreshInterval"]
    return f"""global:
  scrape_interval: {state['prometheus']['scrapeInterval']}
  evaluation_interval: {state['prometheus']['evaluationInterval']}
  external_labels:
    cluster: {cluster_label}
    env: {env_label}

rule_files:
  - /etc/prometheus/rules/*.yml

scrape_configs:
  - job_name: prometheus
    static_configs:
      - targets:
          - prometheus:9090
        labels:
          service: prometheus

  - job_name: cadvisor
    static_configs:
      - targets:
          - cadvisor:8080
        labels:
          service: cadvisor

  - job_name: docker_stats_exporter
    static_configs:
      - targets:
          - docker-stats-exporter:9115
        labels:
          service: docker-stats-exporter

  - job_name: loki
    metrics_path: /metrics
    static_configs:
      - targets:
          - loki:3100
        labels:
          service: loki

  - job_name: control_plane
    metrics_path: /metrics
    static_configs:
      - targets:
          - control-plane:8090
        labels:
          service: control-plane

  - job_name: stack_agent
    metrics_path: /metrics
    static_configs:
      - targets:
          - host.docker.internal:19090
        labels:
          service: stack-agent

  - job_name: applications
    file_sd_configs:
      - files:
          - /etc/prometheus/file_sd/applications-targets.json
        refresh_interval: {refresh_interval}

alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093
"""


def render_alertmanager(state):
    group_by_lines = "\n".join([f"    - {item}" for item in state["alertmanager"]["groupBy"]])
    return f"""global:
  resolve_timeout: {state['alertmanager']['resolveTimeout']}

route:
  receiver: platform-default
  group_by:
{group_by_lines}
  group_wait: {state['alertmanager']['groupWait']}
  group_interval: {state['alertmanager']['groupInterval']}
  repeat_interval: {state['alertmanager']['repeatInterval']}
  routes:
    - receiver: platform-critical
      matchers:
        - severity="critical"

inhibit_rules:
  - source_matchers:
      - severity="critical"
    target_matchers:
      - severity="warning"
    equal:
      - service

receivers:
  - name: platform-default

  - name: platform-critical
"""


def render_loki(state):
    return f"""auth_enabled: {yaml_scalar(state['loki']['authEnabled'])}

server:
  http_listen_port: 3100
  grpc_listen_port: 9096

common:
  instance_addr: 127.0.0.1
  path_prefix: {state['loki']['pathPrefix']}
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: {state['loki']['replicationFactor']}
  ring:
    kvstore:
      store: inmemory

schema_config:
  configs:
    - from: 2024-01-01
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

compactor:
  working_directory: /loki/compactor

ruler:
  alertmanager_url: http://alertmanager:9093

analytics:
  reporting_enabled: {yaml_scalar(state['loki']['reportingEnabled'])}
"""


def render_promtail(state):
    service_name = state["demoService"]["serviceName"]
    environment = state["system"]["environment"]
    return f"""server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: {state['promtail']['positionsFile']}

clients:
  - url: {state['promtail']['clientUrl']}

scrape_configs:
  - job_name: demo-service-filelogs
    static_configs:
      - targets:
          - localhost
        labels:
          job: {service_name}-logs
          app: {service_name}
          env: {environment}
          __path__: {state['promtail']['logPath']}
    pipeline_stages:
      - regex:
          expression: '.*level=\\s*(?P<level>[A-Z]+)\\s+app=(?P<app>[^\\s]+)\\s+traceId=(?P<traceId>[^\\s]+)\\s+spanId=(?P<spanId>[^\\s]+).*'
      - labels:
          level:
          app:
"""


def render_control_center_dashboard(state):
    port = state["ports"]["controlPlaneHostPort"]
    dashboard = {
        "annotations": {
            "list": [
                {
                    "builtIn": 1,
                    "datasource": {"type": "grafana", "uid": "-- Grafana --"},
                    "enable": True,
                    "hide": True,
                    "iconColor": "rgba(0, 211, 255, 1)",
                    "name": "Annotations & Alerts",
                    "type": "dashboard",
                }
            ]
        },
        "editable": True,
        "graphTooltip": 0,
        "id": None,
        "panels": [
            {
                "datasource": {"type": "grafana", "uid": "-- Grafana --"},
                "gridPos": {"h": 12, "w": 24, "x": 0, "y": 0},
                "id": 1,
                "options": {
                    "content": (
                        "# Unified Control Console\n\n"
                        f"[Open Control Plane](http://127.0.0.1:{port}/)\n\n"
                        "Use the control plane to adjust monitoring parameters, regenerate component "
                        "configuration, reload Prometheus, and reconcile the monitoring runtime."
                    ),
                    "mode": "markdown",
                },
                "title": "Control Plane Entry",
                "type": "text",
            }
        ],
        "refresh": "30s",
        "schemaVersion": 39,
        "tags": ["yun-mon", "control-plane"],
        "time": {"from": "now-1h", "to": "now"},
        "title": "Yun-mon Control Center",
        "uid": "yunmon-control-center",
        "version": 2,
    }
    return json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n"


def apply_state(state, update_timestamp=True):
    merged = deep_merge(DEFAULT_STATE, state)
    validate_state(merged)
    if update_timestamp:
        merged["metadata"]["lastAppliedAt"] = timestamp_now()
    save_state(merged)
    write_file(ENV_PATH, render_env(merged))
    write_file(PROMETHEUS_PATH, render_prometheus(merged))
    write_file(PROMETHEUS_FILE_SD_PATH, render_application_targets(merged))
    write_file(METRIC_RULES_PATH, render_metric_catalog_rules(merged))
    write_file(ALERTMANAGER_PATH, render_alertmanager(merged))
    write_file(LOKI_PATH, render_loki(merged))
    write_file(PROMTAIL_PATH, render_promtail(merged))
    write_file(CONTROL_DASHBOARD_PATH, render_control_center_dashboard(merged))
    write_file(METRIC_DASHBOARD_PATH, render_metric_dashboard(merged))
    return merged


class StackAgentClient:
    def __init__(self, base_url, shared_token, timeout=15):
        self.base_url = base_url.rstrip("/")
        self.shared_token = shared_token
        self.timeout = timeout

    def request_json(self, method, path, payload=None):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={
                "Content-Type": "application/json",
                "X-Stack-Agent-Token": self.shared_token,
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Stack agent HTTP {exc.code}: {detail}")
        except URLError as exc:
            raise RuntimeError(f"Stack agent is unreachable: {exc.reason}")


class DockerClient:
    def __init__(self, socket_path, timeout=60):
        self.socket_path = socket_path
        self.timeout = timeout

    def _connect(self):
        if not hasattr(socket, "AF_UNIX"):
            raise RuntimeError("Unix sockets are not supported in this runtime")
        if not Path(self.socket_path).exists():
            raise RuntimeError(f"Docker socket not found: {self.socket_path}")
        connection = http.client.HTTPConnection("localhost", timeout=self.timeout)
        connection.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.sock.settimeout(self.timeout)
        connection.sock.connect(self.socket_path)
        return connection

    def request(self, method, path, body=None, headers=None):
        connection = self._connect()
        try:
            payload = None
            request_headers = {"Host": "docker"}
            if headers:
                request_headers.update(headers)
            if body is not None:
                payload = body.encode("utf-8") if isinstance(body, str) else body
                request_headers["Content-Length"] = str(len(payload))
            connection.request(method, path, body=payload, headers=request_headers)
            response = connection.getresponse()
            data = response.read()
            return response.status, response.getheaders(), data
        finally:
            connection.close()

    def request_json(self, method, path, body=None):
        headers = {}
        payload = body
        if body is not None:
            headers["Content-Type"] = "application/json"
            payload = json.dumps(body)
        status, _, data = self.request(method, path, payload, headers)
        text = data.decode("utf-8") if data else ""
        if status >= 400:
            raise RuntimeError(f"Docker API {method} {path} failed with {status}: {text}")
        return json.loads(text) if text else None

    def list_project_services(self, project_name):
        filters = quote(json.dumps({"label": [f"com.docker.compose.project={project_name}"]}))
        containers = self.request_json("GET", f"/containers/json?all=1&filters={filters}") or []
        services = []
        for container in containers:
            labels = container.get("Labels", {})
            services.append(
                {
                    "id": container.get("Id"),
                    "name": (container.get("Names") or [""])[0].lstrip("/"),
                    "service": labels.get("com.docker.compose.service", ""),
                    "state": container.get("State", "unknown"),
                    "status": container.get("Status", ""),
                    "image": container.get("Image", ""),
                    "ports": format_ports(container.get("Ports")),
                }
            )
        services.sort(key=service_sort_key)
        return services

    def restart_service(self, container_id, timeout=30):
        self.request("POST", f"/containers/{container_id}/restart?t={timeout}")

    def list_running_containers(self):
        containers = self.request_json("GET", "/containers/json?all=0") or []
        results = []
        for container in containers:
            labels = container.get("Labels", {})
            networks = container.get("NetworkSettings", {}).get("Networks", {}) or {}
            network_ips = []
            for network in networks.values():
                ip_address = network.get("IPAddress")
                if ip_address:
                    network_ips.append(ip_address)
            results.append(
                {
                    "id": container.get("Id"),
                    "name": (container.get("Names") or [""])[0].lstrip("/"),
                    "image": container.get("Image", ""),
                    "labels": labels,
                    "rawPorts": container.get("Ports") or [],
                    "ports": format_ports(container.get("Ports")),
                    "networkIps": network_ips,
                    "composeService": labels.get("com.docker.compose.service", ""),
                    "composeProject": labels.get("com.docker.compose.project", ""),
                    "serviceLabel": labels.get("service_name", ""),
                    "monitoringEnabled": str(labels.get("monitoring_enabled", "")).lower() == "true",
                    "monitoringPort": labels.get("monitoring_port"),
                    "metricsPath": labels.get("monitoring_metrics_path"),
                }
            )
        return results


def project_candidates(state):
    candidates = []
    for value in [state["system"]["monitoringProject"], MONITORING_PROJECT, DEFAULT_STATE["system"]["monitoringProject"]]:
        if value and value not in candidates:
            candidates.append(value)
    return candidates


def get_stack_agent_config(state):
    config = state.get("stackAgent", {})
    return {
        "enabled": bool(config.get("enabled", False)),
        "baseUrl": str(config.get("baseUrl", "")).strip(),
        "sharedToken": str(config.get("sharedToken", "")).strip(),
    }


def discover_applications():
    state = load_state()
    defaults = state["applications"]["defaults"]
    overrides = application_items_by_id(state)
    items = []
    seen_app_ids = set()

    if not state["applications"].get("autoDiscoveryEnabled", True):
        for app_id, override in overrides.items():
            item = dict(override)
            item["discoveryType"] = "configured"
            item["autoDiscovered"] = False
            item["containers"] = []
            item["targets"] = []
            items.append(item)
        items.sort(key=application_sort_key)
        return items

    try:
        client = DockerClient(DOCKER_SOCKET)
        containers = client.list_running_containers()
    except Exception:
        containers = []

    grouped = {}
    for container in containers:
        compose_service = container["composeService"]
        if compose_service in INTERNAL_PLATFORM_SERVICES:
            continue
        app_id = (
            container["serviceLabel"]
            or compose_service
            or container["name"]
        )
        app_id = str(app_id).strip()
        if not app_id:
            continue

        group = grouped.setdefault(
            app_id,
            {
                "appId": app_id,
                "displayName": app_id,
                "serviceName": container["serviceLabel"] or compose_service or app_id,
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
                "id": container["id"],
                "name": container["name"],
                "image": container["image"],
                "composeService": compose_service,
                "rawPorts": container["rawPorts"],
                "ports": container["ports"],
                "networkIps": container["networkIps"],
            }
        )
        if container["monitoringPort"]:
            try:
                group["targetPort"] = int(container["monitoringPort"])
                group["hasMonitoringLabels"] = container["monitoringEnabled"]
            except ValueError:
                pass
        if container["metricsPath"]:
            group["metricsPath"] = container["metricsPath"]
        if container["monitoringEnabled"] and group["targetPort"]:
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
                set(
                    target
                    for container in group["containers"]
                    for target in container_scrape_targets(container, group["targetPort"])
                )
            )
        else:
            group["targets"] = []
        items.append(group)
        seen_app_ids.add(app_id)

    for app_id, override in overrides.items():
        if app_id in seen_app_ids:
            continue
        item = dict(override)
        item["discoveryType"] = "configured"
        item["autoDiscovered"] = False
        item["configured"] = True
        item["containers"] = []
        item["targets"] = []
        items.append(item)

    items.sort(key=application_sort_key)
    return items


def render_application_targets(state):
    items = []
    for application in discover_applications():
        if not application.get("enabled"):
            continue
        targets = application.get("targets", [])
        if not targets and application.get("targetPort") and not application.get("autoDiscovered"):
            continue
        if not targets:
            continue
        labels = {
            "service": application.get("serviceName") or application["appId"],
            "app_id": application["appId"],
            "app_display_name": application.get("displayName") or application["appId"],
            "env": application.get("environment") or state["system"]["environment"],
            "__metrics_path__": application.get("metricsPath") or state["applications"]["defaults"]["metricsPath"],
        }
        items.append(
            {
                "targets": sorted(set(targets)),
                "labels": labels,
            }
        )
    return json.dumps(items, indent=2, ensure_ascii=False) + "\n"


def get_runtime_status():
    state = load_state()
    stack_agent = get_stack_agent_config(state)
    runtime = {
        "restartStrategy": "docker-api",
        "stackAgent": {
            "enabled": stack_agent["enabled"],
            "baseUrl": stack_agent["baseUrl"],
            "configured": stack_agent["enabled"] and bool(stack_agent["baseUrl"]) and bool(stack_agent["sharedToken"]),
            "reachable": False,
            "health": None,
            "error": None,
        },
    }

    if not runtime["stackAgent"]["configured"]:
        if stack_agent["enabled"]:
            runtime["stackAgent"]["error"] = "Stack agent is enabled but baseUrl/sharedToken is incomplete."
        return runtime

    try:
        client = StackAgentClient(stack_agent["baseUrl"], stack_agent["sharedToken"], timeout=5)
        health = client.request_json("GET", "/healthz")
        runtime["stackAgent"]["reachable"] = True
        runtime["stackAgent"]["health"] = health
        runtime["restartStrategy"] = "host-agent"
    except Exception as exc:
        runtime["stackAgent"]["error"] = str(exc)

    return runtime


def list_services():
    state = load_state()
    client = DockerClient(DOCKER_SOCKET)
    last_error = None
    fallback = {"project": state["system"]["monitoringProject"], "services": []}
    for candidate in project_candidates(state):
        try:
            services = client.list_project_services(candidate)
            if services:
                return {"project": candidate, "services": services}
            fallback = {"project": candidate, "services": services}
        except Exception as exc:
            last_error = str(exc)
    if last_error:
        raise RuntimeError(last_error)
    return fallback


def reload_prometheus():
    connection = http.client.HTTPConnection("prometheus", 9090, timeout=10)
    try:
        connection.request("POST", "/-/reload")
        response = connection.getresponse()
        body = response.read().decode("utf-8", errors="replace")
        if response.status >= 400:
            bump_metric("prometheus_reload_failures_total")
            raise RuntimeError(f"Prometheus reload failed with {response.status}: {body}")
        bump_metric("prometheus_reload_total")
        return {"status": response.status, "body": body or "Prometheus reloaded successfully"}
    finally:
        connection.close()


def restart_stack(include_control_plane=False):
    state = load_state()
    stack_agent = get_stack_agent_config(state)
    runtime = get_runtime_status()
    if runtime["stackAgent"]["reachable"]:
        client = StackAgentClient(
            runtime["stackAgent"]["baseUrl"],
            stack_agent["sharedToken"],
            timeout=180,
        )
        result = client.request_json(
            "POST",
            "/api/v1/compose/reconcile",
            {
                "build": True,
                "includeControlPlane": include_control_plane,
            },
        )
        bump_metric("stack_restarts_total")
        set_metric("last_successful_restart_timestamp", int(time.time()))
        return {
            "hostAgent": {
                "baseUrl": runtime["stackAgent"]["baseUrl"],
                "health": runtime["stackAgent"]["health"],
            },
            "mode": "host-agent-reconcile",
            "project": state["system"]["monitoringProject"],
            "agentResult": result,
        }

    client = DockerClient(DOCKER_SOCKET)
    service_map = {item["service"]: item for item in list_services()["services"]}
    restarted = []
    errors = []
    targets = list(RESTARTABLE_SERVICES)
    if include_control_plane:
        targets.append("control-plane")

    for service in targets:
        current = service_map.get(service)
        if not current:
            errors.append(f"{service}: not running")
            continue
        try:
            client.restart_service(current["id"])
            restarted.append(service)
        except Exception as exc:
            errors.append(f"{service}: {exc}")

    if errors:
        bump_metric("stack_restart_failures_total")
        raise RuntimeError("Docker API restart was incomplete: " + "; ".join(errors))

    bump_metric("stack_restarts_total")
    set_metric("last_successful_restart_timestamp", int(time.time()))
    time.sleep(2)
    return {
        "mode": "docker-api-restart",
        "project": state["system"]["monitoringProject"],
        "services": restarted,
        "serviceStates": list_services()["services"],
        "runtime": runtime,
        "message": "Running containers were restarted through the Docker API. Host agent reconcile is unavailable, so changes that require container recreation, such as host port bindings or environment variables, still need a host-side docker compose up -d --build.",
    }


def render_metrics():
    metrics = snapshot_metrics()
    uptime = int(time.time() - SERVER_START_TIME)
    lines = [
        "# HELP control_plane_http_requests_total Total HTTP requests served.",
        "# TYPE control_plane_http_requests_total counter",
        f"control_plane_http_requests_total {metrics['http_requests_total']}",
        "# HELP control_plane_config_apply_total Successful config apply operations.",
        "# TYPE control_plane_config_apply_total counter",
        f"control_plane_config_apply_total {metrics['config_apply_total']}",
        "# HELP control_plane_config_apply_failures_total Failed config apply operations.",
        "# TYPE control_plane_config_apply_failures_total counter",
        f"control_plane_config_apply_failures_total {metrics['config_apply_failures_total']}",
        "# HELP control_plane_stack_restarts_total Successful stack restart operations.",
        "# TYPE control_plane_stack_restarts_total counter",
        f"control_plane_stack_restarts_total {metrics['stack_restarts_total']}",
        "# HELP control_plane_stack_restart_failures_total Failed stack restart operations.",
        "# TYPE control_plane_stack_restart_failures_total counter",
        f"control_plane_stack_restart_failures_total {metrics['stack_restart_failures_total']}",
        "# HELP control_plane_prometheus_reload_total Successful Prometheus reload operations.",
        "# TYPE control_plane_prometheus_reload_total counter",
        f"control_plane_prometheus_reload_total {metrics['prometheus_reload_total']}",
        "# HELP control_plane_prometheus_reload_failures_total Failed Prometheus reload operations.",
        "# TYPE control_plane_prometheus_reload_failures_total counter",
        f"control_plane_prometheus_reload_failures_total {metrics['prometheus_reload_failures_total']}",
        "# HELP control_plane_last_successful_apply_timestamp Unix timestamp of the last successful config apply.",
        "# TYPE control_plane_last_successful_apply_timestamp gauge",
        f"control_plane_last_successful_apply_timestamp {metrics['last_successful_apply_timestamp']}",
        "# HELP control_plane_last_successful_restart_timestamp Unix timestamp of the last successful stack restart.",
        "# TYPE control_plane_last_successful_restart_timestamp gauge",
        f"control_plane_last_successful_restart_timestamp {metrics['last_successful_restart_timestamp']}",
        "# HELP control_plane_uptime_seconds Control plane process uptime in seconds.",
        "# TYPE control_plane_uptime_seconds gauge",
        f"control_plane_uptime_seconds {uptime}",
    ]
    return "\n".join(lines) + "\n"


class Handler(BaseHTTPRequestHandler):
    server_version = "YunMonControlPlane/0.1"

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {self.address_string()} {fmt % args}")

    def _json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _text(self, payload, content_type="text/plain; charset=utf-8", status=200):
        body = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _serve_static(self, path):
        relative = path.removeprefix("/static/").strip()
        static_root = STATIC_DIR.resolve()
        target = (STATIC_DIR / relative).resolve()
        if static_root not in target.parents and target != static_root:
            self.send_error(404)
            return
        if not target.exists() or not target.is_file():
            self.send_error(404)
            return
        content_type, _ = mimetypes.guess_type(str(target))
        self._text(
            target.read_text(encoding="utf-8"),
            content_type=(content_type or "text/plain") + "; charset=utf-8",
        )

    def do_GET(self):
        bump_metric("http_requests_total")
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/":
                index_path = STATIC_DIR / "index.html"
                self._text(index_path.read_text(encoding="utf-8"), "text/html; charset=utf-8")
                return
            if parsed.path.startswith("/static/"):
                self._serve_static(parsed.path)
                return
            if parsed.path == "/healthz":
                health = {
                    "status": "ok",
                    "timestamp": timestamp_now(),
                    "stateFile": str(STATE_PATH),
                    "dockerSocketPresent": Path(DOCKER_SOCKET).exists(),
                }
                self._json(health)
                return
            if parsed.path == "/metrics":
                self._text(render_metrics(), "text/plain; version=0.0.4; charset=utf-8")
                return
            if parsed.path == "/api/v1/config":
                self._json({"ok": True, "config": load_state()})
                return
            if parsed.path == "/api/v1/system/services":
                services = list_services()
                self._json({"ok": True, **services})
                return
            if parsed.path == "/api/v1/applications/discovery":
                self._json({"ok": True, "applications": discover_applications()})
                return
            if parsed.path == "/api/v1/metrics/catalog":
                self._json({"ok": True, **build_metric_catalog_view(load_state())})
                return
            if parsed.path == "/api/v1/metrics/live":
                state = load_state()
                self._json({"ok": True, "metrics": filtered_live_metric_names(state)})
                return
            if parsed.path == "/api/v1/system/runtime":
                self._json({"ok": True, "runtime": get_runtime_status()})
                return
            self.send_error(404)
        except Exception as exc:
            self._json({"ok": False, "error": str(exc)}, status=500)

    def do_PUT(self):
        bump_metric("http_requests_total")
        parsed = urlparse(self.path)
        if parsed.path != "/api/v1/config":
            self.send_error(404)
            return
        try:
            body = self._read_json_body()
            config = body.get("config", body)
            applied = apply_state(config)
            set_metric("last_successful_apply_timestamp", int(time.time()))
            bump_metric("config_apply_total")
            reload_result = reload_prometheus()
            runtime = get_runtime_status()
            message = (
                "Configuration rendered successfully. Prometheus was hot reloaded. "
                "Use the runtime restart action to apply file-based changes."
            )
            if runtime["stackAgent"]["reachable"]:
                message += " Stack-agent reconcile is available for rebuild-required changes."
            else:
                message += (
                    " Host port and environment variable changes still require a host-side "
                    "docker compose up -d --build because stack-agent reconcile is unavailable."
                )
            self._json(
                {
                    "ok": True,
                    "config": applied,
                    "prometheusReload": reload_result,
                    "message": message,
                }
            )
        except Exception as exc:
            bump_metric("config_apply_failures_total")
            self._json({"ok": False, "error": str(exc)}, status=400)

    def do_POST(self):
        bump_metric("http_requests_total")
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/v1/config/apply":
                body = self._read_json_body()
                config = body.get("config", load_state())
                applied = apply_state(config)
                set_metric("last_successful_apply_timestamp", int(time.time()))
                bump_metric("config_apply_total")
                reload_result = reload_prometheus()
                runtime = get_runtime_status()
                message = "Configuration applied and Prometheus reloaded."
                if runtime["stackAgent"]["reachable"]:
                    message += " Stack-agent reconcile is available for rebuild-required changes."
                else:
                    message += (
                        " Host port and environment variable changes still require a host-side "
                        "docker compose up -d --build because stack-agent reconcile is unavailable."
                    )
                self._json(
                    {
                        "ok": True,
                        "config": applied,
                        "prometheusReload": reload_result,
                        "message": message,
                    }
                )
                return
            if parsed.path == "/api/v1/system/prometheus/reload":
                result = reload_prometheus()
                self._json({"ok": True, "result": result})
                return
            if parsed.path == "/api/v1/system/restart":
                body = self._read_json_body()
                include_control_plane = bool(body.get("includeControlPlane", False))
                result = restart_stack(include_control_plane=include_control_plane)
                message = "Monitoring runtime restart finished through the Docker API."
                if result.get("mode") in {"host-agent-reconcile", "docker-compose-reconcile"}:
                    message = "Monitoring runtime reconcile finished through the host stack-agent."
                elif result.get("mode") == "docker-api-restart":
                    message += (
                        " Control plane restart is skipped by default to keep the console available; "
                        "host port and environment variable changes still require a host-side "
                        "docker compose up -d --build."
                    )
                self._json(
                    {
                        "ok": True,
                        "result": result,
                        "message": message,
                    }
                )
                return
            self.send_error(404)
        except Exception as exc:
            if parsed.path == "/api/v1/system/prometheus/reload":
                bump_metric("prometheus_reload_failures_total")
            elif parsed.path == "/api/v1/system/restart":
                bump_metric("stack_restart_failures_total")
            self._json({"ok": False, "error": str(exc)}, status=500)


def main():
    ensure_state_file()
    apply_state(load_state(), update_timestamp=False)
    server = ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), Handler)
    print(f"Yun-mon control plane listening on 0.0.0.0:{HTTP_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()

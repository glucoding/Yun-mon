"""渲染 `.env` 文件(供 docker-compose 读取)。"""

from __future__ import annotations

from typing import Any


def _quote_env_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = "" if value is None else str(value)
    if not text:
        return '""'
    needs_quote = any(ch in text for ch in ' "\'#:\n\r\t')
    if needs_quote:
        escaped = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{escaped}"'
    return text


def render_env(state: dict[str, Any]) -> str:
    pairs: list[tuple[str, Any]] = [
        ("MONITORING_PROJECT", state["system"]["monitoringProject"]),
        ("STACK_AGENT_ENABLED", state["stackAgent"]["enabled"]),
        ("STACK_AGENT_BASE_URL", state["stackAgent"]["baseUrl"]),
        ("STACK_AGENT_SHARED_TOKEN", state["stackAgent"]["sharedToken"]),
        ("GRAFANA_ADMIN_USER", state["grafana"]["adminUser"]),
        ("GRAFANA_ADMIN_PASSWORD", state["grafana"]["adminPassword"]),
        ("GRAFANA_ALLOW_SIGN_UP", state["grafana"]["allowSignUp"]),
        ("APP_ENV", state["demoService"]["appEnv"]),
        ("GRAFANA_HOST_PORT", state["ports"]["grafanaHostPort"]),
        ("DEMO_SERVICE_HOST_PORT", state["ports"]["demoServiceHostPort"]),
        ("CONTROL_PLANE_HOST_PORT", state["ports"]["controlPlaneHostPort"]),
        ("PROMETHEUS_HOST_PORT", state["ports"]["prometheusHostPort"]),
        ("ALERTMANAGER_HOST_PORT", state["ports"]["alertmanagerHostPort"]),
        ("LOKI_HOST_PORT", state["ports"]["lokiHostPort"]),
        ("CADVISOR_HOST_PORT", state["ports"]["cadvisorHostPort"]),
        ("OTEL_OTLP_HTTP_PORT", state["ports"]["otelCollectorOtlpHttpPort"]),
        ("OTEL_OTLP_GRPC_PORT", state["ports"]["otelCollectorOtlpGrpcPort"]),
        ("DEMO_SERVICE_LOG_DIR", state["demoService"]["logDir"]),
        ("DEMO_SERVICE_JAVA_OPTS", state["demoService"]["javaOpts"]),
        ("DEMO_SERVICE_MONITORING_ENABLED", state["demoService"]["monitoringEnabled"]),
        ("DEMO_SERVICE_MONITORING_PORT", state["demoService"]["monitoringPort"]),
        ("DEMO_SERVICE_SERVICE_NAME", state["demoService"]["serviceName"]),
        ("DEMO_SERVICE_METRICS_PATH", state["demoService"]["metricsPath"]),
        ("CADVISOR_DOCKER_ONLY", state["cadvisor"]["dockerOnly"]),
        ("CADVISOR_HOUSEKEEPING_INTERVAL", state["cadvisor"]["housekeepingInterval"]),
        ("OTEL_COLLECTOR_ENABLED", state["otelCollector"]["enabled"]),
    ]
    return "\n".join(f"{key}={_quote_env_value(value)}" for key, value in pairs) + "\n"

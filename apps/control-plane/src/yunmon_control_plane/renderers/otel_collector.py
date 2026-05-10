"""渲染 OpenTelemetry Collector 配置(P2-6)。"""

from __future__ import annotations

from typing import Any

from ._yaml import dump_yaml


def render_otel_collector(state: dict[str, Any]) -> str:
    otel = state.get("otelCollector", {}) or {}
    exporters_cfg = otel.get("exporters", {}) or {}
    enable_logging = bool(exporters_cfg.get("logging", True))
    otlp_endpoint = str(exporters_cfg.get("otlpHttpEndpoint", "")).strip()

    exporters: dict[str, Any] = {}
    if enable_logging:
        exporters["debug"] = {"verbosity": "basic"}
    if otlp_endpoint:
        exporters["otlphttp"] = {"endpoint": otlp_endpoint}
    exporters["prometheus"] = {"endpoint": "0.0.0.0:8889"}

    if not exporters:
        exporters["debug"] = {"verbosity": "basic"}

    pipeline_exporters = list(exporters.keys())

    config = {
        "receivers": {
            "otlp": {
                "protocols": {
                    "grpc": {"endpoint": "0.0.0.0:4317"},
                    "http": {"endpoint": "0.0.0.0:4318"},
                }
            }
        },
        "processors": {
            "batch": {"timeout": "5s"},
            "memory_limiter": {"check_interval": "1s", "limit_percentage": 75, "spike_limit_percentage": 25},
        },
        "exporters": exporters,
        "service": {
            "pipelines": {
                "traces": {"receivers": ["otlp"], "processors": ["memory_limiter", "batch"], "exporters": [e for e in pipeline_exporters if e != "prometheus"] or ["debug"]},
                "metrics": {"receivers": ["otlp"], "processors": ["memory_limiter", "batch"], "exporters": pipeline_exporters},
                "logs": {"receivers": ["otlp"], "processors": ["memory_limiter", "batch"], "exporters": [e for e in pipeline_exporters if e != "prometheus"] or ["debug"]},
            },
            "telemetry": {"logs": {"level": "info"}},
        },
    }
    return dump_yaml(config)

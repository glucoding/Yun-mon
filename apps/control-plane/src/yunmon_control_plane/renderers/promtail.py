"""渲染 Promtail 配置。"""

from __future__ import annotations

from typing import Any

from ._yaml import dump_yaml


def render_promtail(state: dict[str, Any]) -> str:
    promtail = state["promtail"]
    service_name = state["demoService"]["serviceName"]
    environment = state["system"]["environment"]
    config = {
        "server": {"http_listen_port": 9080, "grpc_listen_port": 0},
        "positions": {"filename": promtail["positionsFile"]},
        "clients": [{"url": promtail["clientUrl"]}],
        "scrape_configs": [
            {
                "job_name": "demo-service-filelogs",
                "static_configs": [
                    {
                        "targets": ["localhost"],
                        "labels": {
                            "job": f"{service_name}-logs",
                            "app": service_name,
                            "env": environment,
                            "__path__": promtail["logPath"],
                        },
                    }
                ],
                "pipeline_stages": [
                    {
                        "regex": {
                            "expression": (
                                r".*level=\s*(?P<level>[A-Z]+)\s+app=(?P<app>[^\s]+)\s+"
                                r"traceId=(?P<traceId>[^\s]+)\s+spanId=(?P<spanId>[^\s]+).*"
                            )
                        }
                    },
                    {"labels": {"level": None, "app": None}},
                ],
            }
        ],
    }
    return dump_yaml(config)

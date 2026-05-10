"""渲染 Loki 配置。"""

from __future__ import annotations

from typing import Any

from ._yaml import dump_yaml


def render_loki(state: dict[str, Any]) -> str:
    loki = state["loki"]
    config = {
        "auth_enabled": loki["authEnabled"],
        "server": {"http_listen_port": 3100, "grpc_listen_port": 9096},
        "common": {
            "instance_addr": "127.0.0.1",
            "path_prefix": loki["pathPrefix"],
            "storage": {
                "filesystem": {
                    "chunks_directory": "/loki/chunks",
                    "rules_directory": "/loki/rules",
                }
            },
            "replication_factor": loki["replicationFactor"],
            "ring": {"kvstore": {"store": "inmemory"}},
        },
        "schema_config": {
            "configs": [
                {
                    "from": "2024-01-01",
                    "store": "tsdb",
                    "object_store": "filesystem",
                    "schema": "v13",
                    "index": {"prefix": "index_", "period": "24h"},
                }
            ]
        },
        "compactor": {"working_directory": "/loki/compactor"},
        "ruler": {"alertmanager_url": "http://alertmanager:9093"},
        "analytics": {"reporting_enabled": loki["reportingEnabled"]},
    }
    return dump_yaml(config)

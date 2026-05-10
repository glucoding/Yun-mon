"""Prometheus HTTP API 客户端。"""

from __future__ import annotations

from typing import Any

import httpx


class PrometheusClient:
    def __init__(self, base_url: str = "http://prometheus:9090", *, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def reload(self) -> dict[str, Any]:
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            response = client.post("/-/reload")
            if response.status_code >= 400:
                raise RuntimeError(f"Prometheus reload 失败 {response.status_code}: {response.text}")
            return {"status": response.status_code, "body": response.text or "Prometheus reloaded"}

    def label_values(self, label: str = "__name__") -> list[str]:
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            response = client.get(f"/api/v1/label/{label}/values")
            response.raise_for_status()
            payload = response.json()
            return sorted(payload.get("data", []))

    def metric_metadata(self) -> dict[str, list[dict[str, Any]]]:
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            response = client.get("/api/v1/metadata")
            response.raise_for_status()
            payload = response.json()
            return payload.get("data", {}) or {}

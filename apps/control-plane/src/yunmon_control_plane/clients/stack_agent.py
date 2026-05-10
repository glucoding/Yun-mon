"""stack-agent HTTP 客户端(P1-6 用 httpx)。"""

from __future__ import annotations

from typing import Any

import httpx


class StackAgentClient:
    def __init__(self, base_url: str, shared_token: str, *, timeout: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.shared_token = shared_token
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-Stack-Agent-Token": self.shared_token,
        }

    def _client(self, *, timeout: float | None = None) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=timeout or self.timeout)

    def healthz(self) -> dict[str, Any]:
        with self._client(timeout=5.0) as client:
            response = client.get("/healthz")
            response.raise_for_status()
            return response.json()

    def reconcile(self, *, build: bool = True, include_control_plane: bool = False, services: list[str] | None = None, timeout: float = 1800.0) -> dict[str, Any]:
        payload = {"build": build, "includeControlPlane": include_control_plane}
        if services is not None:
            payload["services"] = services
        with self._client(timeout=timeout) as client:
            response = client.post("/api/v1/compose/reconcile", json=payload, headers=self._headers())
            if response.status_code >= 400:
                raise httpx.HTTPStatusError(
                    f"stack-agent {response.status_code}: {response.text}",
                    request=response.request,
                    response=response,
                )
            return response.json()

    def status(self) -> dict[str, Any]:
        with self._client() as client:
            response = client.get("/api/v1/compose/status", headers=self._headers())
            response.raise_for_status()
            return response.json()

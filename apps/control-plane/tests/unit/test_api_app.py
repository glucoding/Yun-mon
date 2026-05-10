"""控制面 FastAPI 应用的契约测试。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from yunmon_control_plane.api import create_app
from yunmon_control_plane.config import Settings, reset_settings_cache


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    (tmp_path / "infra" / "control-plane").mkdir(parents=True, exist_ok=True)
    (tmp_path / "infra" / "prometheus" / "rules").mkdir(parents=True, exist_ok=True)
    (tmp_path / "infra" / "prometheus" / "file_sd").mkdir(parents=True, exist_ok=True)
    (tmp_path / "infra" / "alertmanager").mkdir(parents=True, exist_ok=True)
    (tmp_path / "infra" / "loki").mkdir(parents=True, exist_ok=True)
    (tmp_path / "infra" / "promtail").mkdir(parents=True, exist_ok=True)
    (tmp_path / "infra" / "grafana" / "dashboards").mkdir(parents=True, exist_ok=True)
    (tmp_path / "infra" / "otel-collector").mkdir(parents=True, exist_ok=True)
    return tmp_path


class _FakeDocker:
    def list_running_containers(self):
        return []

    def list_project_services(self, project: str):  # noqa: ARG002
        return []


@pytest.fixture
def app_client(workspace: Path, monkeypatch):
    monkeypatch.setenv("CONTROL_PLANE_WORKSPACE", str(workspace))
    monkeypatch.setenv("CONTROL_PLANE_AUTH_ENABLED", "false")
    monkeypatch.setenv("CONTROL_PLANE_HTTP_PORT", "8090")
    monkeypatch.setenv("CONTROL_PLANE_OTEL_ENDPOINT", "")
    reset_settings_cache()

    settings = Settings()
    app = create_app(settings=settings)

    fake_docker = _FakeDocker()
    app.state.context.docker = fake_docker
    app.state.context.service.docker = fake_docker

    class _FakePrometheus:
        def reload(self):
            return {"status": 200, "body": "ok"}

        def label_values(self, label="__name__"):  # noqa: ARG002
            return ["http_server_requests_seconds_count", "yunmon_business_orders_processed_total"]

        def metric_metadata(self):
            return {}

    fake_prom = _FakePrometheus()
    app.state.context.prometheus = fake_prom
    app.state.context.service.prometheus = fake_prom

    with TestClient(app) as client:
        yield client, workspace


def test_healthz(app_client):
    client, _ = app_client
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_metrics_endpoint(app_client):
    client, _ = app_client
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "control_plane_http_requests_total" in response.text


def test_get_config_returns_default(app_client):
    client, _ = app_client
    response = client.get("/api/v1/config")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"]
    assert payload["config"]["system"]["monitoringProject"] == "yun-mon"


def test_put_config_validates_and_renders(app_client):
    client, workspace = app_client
    state = client.get("/api/v1/config").json()["config"]
    state["grafana"]["adminPassword"] = "newPassword12345"
    response = client.put("/api/v1/config", json={"config": state})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ok"]
    assert (workspace / "infra" / "prometheus" / "prometheus.yml").exists()
    assert (workspace / "infra" / "alertmanager" / "alertmanager.yml").exists()


def test_metric_catalog_view_marks_unmanaged(app_client):
    client, _ = app_client
    response = client.get("/api/v1/metrics/catalog")
    assert response.status_code == 200
    payload = response.json()
    live = set(payload["liveMetrics"])
    assert "http_server_requests_seconds_count" in live


def test_audit_snapshot_lifecycle(app_client):
    client, _ = app_client
    state = client.get("/api/v1/config").json()["config"]
    state["grafana"]["adminPassword"] = "anotherSecret123"
    client.put("/api/v1/config", json={"config": state})

    snapshots = client.get("/api/v1/audit/snapshots").json()["snapshots"]
    assert snapshots, "至少应有一份快照"
    detail = client.get(f"/api/v1/audit/snapshots/{snapshots[0]['snapshotId']}")
    assert detail.status_code == 200

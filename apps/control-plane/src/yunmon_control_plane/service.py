"""控制面核心业务逻辑层。

把 desired-state -> 渲染 -> 持久化 -> Prometheus reload -> 审计 这一连串行为收口在这里,
让 API/任务层能尽可能薄。
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .applications import discover_applications
from .audit.snapshot import SnapshotStore
from .catalog import build_metric_catalog_view, normalize_metric_catalog
from .clients.docker_client import DockerError, DockerFacade
from .clients.prometheus import PrometheusClient
from .clients.stack_agent import StackAgentClient
from .config import Settings
from .metrics import (
    config_apply_failures_total,
    config_apply_total,
    discovery_failures_total,
    last_successful_apply_timestamp,
    last_successful_restart_timestamp,
    prometheus_reload_failures_total,
    prometheus_reload_total,
    stack_restart_failures_total,
    stack_restarts_total,
)
from .renderers import (
    render_alertmanager,
    render_application_rules,
    render_application_targets,
    render_control_center_dashboard,
    render_env,
    render_loki,
    render_metric_catalog_rules,
    render_metric_dashboard,
    render_otel_collector,
    render_prometheus,
    render_promtail,
    render_slo_dashboard,
    render_slo_rules,
)
from .runtime import DockerComposeExecutor, ReconcilePlan
from .state import StateStore, YunmonState


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _timestamp_now() -> str:
    return datetime.now(UTC).isoformat()


class ControlPlaneService:
    def __init__(
        self,
        *,
        settings: Settings,
        state_store: StateStore,
        snapshot_store: SnapshotStore,
        docker_facade: DockerFacade,
        prometheus_client: PrometheusClient,
    ) -> None:
        self.settings = settings
        self.state_store = state_store
        self.snapshot_store = snapshot_store
        self.docker = docker_facade
        self.prometheus = prometheus_client

    # ---------- helpers ----------

    def _stack_agent(self) -> StackAgentClient | None:
        state = self.state_store.load_dict()
        cfg = state.get("stackAgent", {}) or {}
        if not cfg.get("enabled"):
            return None
        base_url = (cfg.get("baseUrl") or "").strip()
        token = (cfg.get("sharedToken") or "").strip()
        if not base_url or not token:
            return None
        return StackAgentClient(base_url, token)

    def runtime_executor(self) -> DockerComposeExecutor:
        return DockerComposeExecutor(
            docker_facade=self.docker,
            stack_agent_factory=self._stack_agent,
            prometheus_client=self.prometheus,
            project_name=self.settings.monitoring_project,
        )

    # ---------- 应用配置 ----------

    def apply_state(self, raw_state: dict[str, Any], *, actor: str, summary: str = "") -> dict[str, Any]:
        previous = self.state_store.load_dict()
        merged = self._merge_with_defaults(raw_state)
        validated = YunmonState.model_validate(merged)
        merged = validated.to_dict()
        merged.setdefault("metadata", {})["lastAppliedAt"] = _timestamp_now()

        try:
            self._render_all(merged)
        except Exception:
            config_apply_failures_total.inc()
            raise

        self.state_store.save_dict(merged)
        snapshot_meta = self.snapshot_store.record(
            previous=previous,
            current=merged,
            actor=actor,
            summary=summary or "apply_state",
        )

        config_apply_total.inc()
        last_successful_apply_timestamp.set(time.time())
        return {"state": merged, "snapshot": snapshot_meta}

    def _merge_with_defaults(self, raw_state: dict[str, Any]) -> dict[str, Any]:
        from .catalog.normalize import deep_merge
        from .state.defaults import build_default_state

        merged = deep_merge(build_default_state(generate_token=False), raw_state)
        normalize_metric_catalog(merged)
        return merged

    def _render_all(self, state: dict[str, Any]) -> None:
        cfg = self.settings
        environment = state["system"]["environment"]
        default_metrics_path = state["applications"]["defaults"]["metricsPath"]

        try:
            applications_view = discover_applications(state, self.docker)
        except DockerError as exc:
            discovery_failures_total.inc()
            raise RuntimeError(f"应用发现失败,已保留上一次 SD 文件不动: {exc}") from exc

        _write_file(cfg.env_path, render_env(state))
        _write_file(cfg.prometheus_config_path, render_prometheus(state))
        _write_file(
            cfg.prometheus_file_sd_path,
            render_application_targets(applications_view, default_metrics_path, environment),
        )
        _write_file(cfg.prometheus_metric_rules_path, render_metric_catalog_rules(state))
        _write_file(cfg.prometheus_application_rules_path, render_application_rules(state))
        _write_file(cfg.slo_rules_path, render_slo_rules(state))
        _write_file(cfg.alertmanager_config_path, render_alertmanager(state))
        _write_file(cfg.loki_config_path, render_loki(state))
        _write_file(cfg.promtail_config_path, render_promtail(state))
        _write_file(cfg.control_dashboard_path, render_control_center_dashboard(state))
        _write_file(cfg.metric_dashboard_path, render_metric_dashboard(state))
        _write_file(cfg.slo_dashboard_path, render_slo_dashboard(state))
        if state["otelCollector"]["enabled"]:
            _write_file(cfg.otel_collector_config_path, render_otel_collector(state))

    # ---------- 应用列表/视图 ----------

    def applications_view(self) -> list[dict[str, Any]]:
        state = self.state_store.load_dict()
        try:
            return discover_applications(state, self.docker)
        except DockerError as exc:
            discovery_failures_total.inc()
            raise RuntimeError(str(exc)) from exc

    # ---------- 指标目录 ----------

    def metric_catalog_view(self) -> dict[str, Any]:
        state = self.state_store.load_dict()
        try:
            live_names = self.prometheus.label_values("__name__")
        except Exception:
            live_names = []
        return build_metric_catalog_view(state, live_names)

    def sync_metric_metadata(self) -> dict[str, Any]:
        try:
            metadata = self.prometheus.metric_metadata()
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "metadata": metadata}

    # ---------- 运行时 ----------

    def reload_prometheus(self) -> dict[str, Any]:
        try:
            result = self.prometheus.reload()
            prometheus_reload_total.inc()
            return result
        except Exception:
            prometheus_reload_failures_total.inc()
            raise

    def list_services(self) -> dict[str, Any]:
        executor = self.runtime_executor()
        services = executor.list_services()
        return {
            "project": self.settings.monitoring_project,
            "services": [
                {
                    "name": svc.name,
                    "service": svc.service,
                    "state": svc.state,
                    "status": svc.status,
                    "image": svc.image,
                    "ports": svc.ports,
                }
                for svc in services
            ],
        }

    def runtime_status(self) -> dict[str, Any]:
        return self.runtime_executor().runtime_status()

    def reconcile_stack(self, *, build: bool = True, include_control_plane: bool = False) -> dict[str, Any]:
        executor = self.runtime_executor()
        try:
            result = executor.reconcile(
                ReconcilePlan(services=[], build=build, include_control_plane=include_control_plane)
            )
            stack_restarts_total.inc()
            last_successful_restart_timestamp.set(time.time())
            return {
                "mode": result.mode,
                "project": result.project,
                "services": result.services,
                "runtime": result.runtime,
                "extras": result.extras,
            }
        except Exception:
            stack_restart_failures_total.inc()
            raise

    # ---------- 回滚 ----------

    def rollback_to(self, snapshot_id: str, *, actor: str) -> dict[str, Any]:
        snapshot = self.snapshot_store.get(snapshot_id)
        return self.apply_state(snapshot["state"], actor=actor, summary=f"rollback_to {snapshot_id}")

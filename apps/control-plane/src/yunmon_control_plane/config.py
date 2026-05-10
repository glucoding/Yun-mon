"""控制面运行期全局配置。

所有运行参数集中在本模块，通过环境变量覆盖。这个模块本身不依赖项目其他模块，
保证可以被任何子模块自由 import。
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """控制面进程级配置。"""

    model_config = SettingsConfigDict(
        env_prefix="CONTROL_PLANE_",
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    workspace: Path = Field(default=Path("/workspace"))
    http_host: str = Field(default="0.0.0.0")
    http_port: int = Field(default=8090)
    monitoring_project: str = Field(default="yun-mon", alias="MONITORING_PROJECT")
    docker_socket: str = Field(default="/var/run/docker.sock", alias="DOCKER_SOCKET")

    auth_enabled: bool = Field(default=False)
    jwt_secret: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    jwt_access_ttl_seconds: int = Field(default=900)
    jwt_refresh_ttl_seconds: int = Field(default=7 * 24 * 3600)
    bcrypt_rounds: int = Field(default=12)

    snapshot_keep_count: int = Field(default=50)
    snapshot_keep_days: int = Field(default=90)

    otel_endpoint: str = Field(default="")
    otel_service_name: str = Field(default="yunmon-control-plane")

    container_stats_interval_seconds: float = Field(default=15.0)

    audit_log_path: Path | None = None

    @property
    def state_path(self) -> Path:
        return self.workspace / "infra" / "control-plane" / "desired-state.json"

    @property
    def env_path(self) -> Path:
        return self.workspace / ".env"

    @property
    def prometheus_config_path(self) -> Path:
        return self.workspace / "infra" / "prometheus" / "prometheus.yml"

    @property
    def prometheus_file_sd_path(self) -> Path:
        return self.workspace / "infra" / "prometheus" / "file_sd" / "applications-targets.json"

    @property
    def prometheus_metric_rules_path(self) -> Path:
        return self.workspace / "infra" / "prometheus" / "rules" / "metric-catalog-rules.yml"

    @property
    def prometheus_application_rules_path(self) -> Path:
        return self.workspace / "infra" / "prometheus" / "rules" / "application-rules.yml"

    @property
    def alertmanager_config_path(self) -> Path:
        return self.workspace / "infra" / "alertmanager" / "alertmanager.yml"

    @property
    def loki_config_path(self) -> Path:
        return self.workspace / "infra" / "loki" / "loki-config.yml"

    @property
    def promtail_config_path(self) -> Path:
        return self.workspace / "infra" / "promtail" / "promtail-config.yml"

    @property
    def control_dashboard_path(self) -> Path:
        return self.workspace / "infra" / "grafana" / "dashboards" / "control-center.json"

    @property
    def metric_dashboard_path(self) -> Path:
        return self.workspace / "infra" / "grafana" / "dashboards" / "metric-catalog.json"

    @property
    def slo_dashboard_path(self) -> Path:
        return self.workspace / "infra" / "grafana" / "dashboards" / "slo-overview.json"

    @property
    def slo_rules_path(self) -> Path:
        return self.workspace / "infra" / "prometheus" / "rules" / "slo-rules.yml"

    @property
    def otel_collector_config_path(self) -> Path:
        return self.workspace / "infra" / "otel-collector" / "config.yaml"

    @property
    def snapshots_dir(self) -> Path:
        return self.workspace / "infra" / "control-plane" / "snapshots"

    @property
    def audit_log_dir(self) -> Path:
        return self.workspace / "infra" / "control-plane" / "audit"

    @property
    def accounts_path(self) -> Path:
        return self.workspace / "infra" / "control-plane" / "accounts.json"

    @property
    def web_dist(self) -> Path:
        candidates = [
            Path(__file__).resolve().parents[2] / "web" / "dist",
            self.workspace / "apps" / "control-plane" / "web" / "dist",
            Path("/app/web/dist"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    @property
    def static_legacy(self) -> Path:
        """旧版静态前端目录，作为 web/dist 不存在时的兜底。"""
        candidates = [
            Path(__file__).resolve().parents[2] / "static",
            self.workspace / "apps" / "control-plane" / "static",
            Path("/app/static"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    """测试时清缓存。"""
    get_settings.cache_clear()

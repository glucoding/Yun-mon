"""控制面自身的 Prometheus 指标(P1-4)。"""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, generate_latest

REGISTRY = CollectorRegistry()

http_requests_total = Counter(
    "control_plane_http_requests_total",
    "控制面收到的 HTTP 请求总数",
    ["method", "path", "status"],
    registry=REGISTRY,
)

config_apply_total = Counter(
    "control_plane_config_apply_total",
    "成功的配置下发次数",
    registry=REGISTRY,
)

config_apply_failures_total = Counter(
    "control_plane_config_apply_failures_total",
    "失败的配置下发次数",
    registry=REGISTRY,
)

stack_restarts_total = Counter(
    "control_plane_stack_restarts_total",
    "成功触发的监测栈重启/重建次数",
    registry=REGISTRY,
)

stack_restart_failures_total = Counter(
    "control_plane_stack_restart_failures_total",
    "失败的监测栈重启/重建次数",
    registry=REGISTRY,
)

prometheus_reload_total = Counter(
    "control_plane_prometheus_reload_total",
    "成功的 Prometheus 热重载次数",
    registry=REGISTRY,
)

prometheus_reload_failures_total = Counter(
    "control_plane_prometheus_reload_failures_total",
    "失败的 Prometheus 热重载次数",
    registry=REGISTRY,
)

last_successful_apply_timestamp = Gauge(
    "control_plane_last_successful_apply_timestamp",
    "上次成功配置下发的 Unix 时间戳",
    registry=REGISTRY,
)

last_successful_restart_timestamp = Gauge(
    "control_plane_last_successful_restart_timestamp",
    "上次成功监测栈重启的 Unix 时间戳",
    registry=REGISTRY,
)

discovery_failures_total = Counter(
    "control_plane_discovery_failures_total",
    "应用自动发现失败次数",
    registry=REGISTRY,
)

uptime_seconds = Gauge(
    "control_plane_uptime_seconds",
    "控制面运行秒数",
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# 容器级 stats(替代 cAdvisor 在 Docker Desktop on Windows 上识别失败的场景)
# 这些指标由 ContainerStatsCollector 周期性更新,标签来自 docker SDK 返回的
# 容器属性。"compose_*" 标签直接映射 docker compose 的 service / project 标签,
# 与原 docker-stats-exporter 的语义保持一致,便于 dashboard 平滑迁移。
# ---------------------------------------------------------------------------
CONTAINER_LABELS = ["name", "id", "compose_project", "compose_service", "image"]

container_running = Gauge(
    "yunmon_container_running",
    "容器是否在运行(1=running,0=stopped/exited)",
    CONTAINER_LABELS,
    registry=REGISTRY,
)

container_cpu_seconds_total = Counter(
    "yunmon_container_cpu_seconds_total",
    "容器累计 CPU 占用秒数(全核归一,可用 rate() 计算 ratio)",
    CONTAINER_LABELS,
    registry=REGISTRY,
)

container_memory_working_set_bytes = Gauge(
    "yunmon_container_memory_working_set_bytes",
    "容器工作集内存(working set,与 cgroup 同义)",
    CONTAINER_LABELS,
    registry=REGISTRY,
)

container_memory_limit_bytes = Gauge(
    "yunmon_container_memory_limit_bytes",
    "容器内存上限",
    CONTAINER_LABELS,
    registry=REGISTRY,
)

container_network_receive_bytes_total = Counter(
    "yunmon_container_network_receive_bytes_total",
    "容器累计网络接收字节",
    CONTAINER_LABELS,
    registry=REGISTRY,
)

container_network_transmit_bytes_total = Counter(
    "yunmon_container_network_transmit_bytes_total",
    "容器累计网络发送字节",
    CONTAINER_LABELS,
    registry=REGISTRY,
)

container_block_read_bytes_total = Counter(
    "yunmon_container_block_read_bytes_total",
    "容器累计块设备读取字节",
    CONTAINER_LABELS,
    registry=REGISTRY,
)

container_block_write_bytes_total = Counter(
    "yunmon_container_block_write_bytes_total",
    "容器累计块设备写入字节",
    CONTAINER_LABELS,
    registry=REGISTRY,
)

container_stats_collection_failures_total = Counter(
    "yunmon_container_stats_collection_failures_total",
    "容器 stats 采集失败次数",
    registry=REGISTRY,
)

container_stats_last_success_timestamp = Gauge(
    "yunmon_container_stats_last_success_timestamp",
    "上次成功完成一轮容器 stats 采集的 Unix 时间戳",
    registry=REGISTRY,
)


def render_metrics() -> bytes:
    return generate_latest(REGISTRY)

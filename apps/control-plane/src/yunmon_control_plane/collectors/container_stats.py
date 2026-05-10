"""容器级 docker stats 采集器。

设计目标:
- cAdvisor 在 Docker Desktop on Windows 上因 overlayfs 路径布局问题
  无法识别容器(只能拿到根 cgroup 的指标),为此控制面内置一份基于
  docker SDK 的容器级 stats 采集器,直接消费 `docker stats` API。
- 标签命名沿用 docker-stats-exporter 的 `compose_project` /
  `compose_service`,便于现有 dashboard 与告警规则平滑迁移。
- 仅提供"轻量"指标(CPU 秒数 / 内存工作集 / 网络 / 块设备),不与
  cAdvisor 的 fs / process / cgroup 等深度指标重叠。
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from prometheus_client.metrics import Counter as _Counter

from .. import metrics
from ..clients.docker_client import DockerError, DockerFacade

logger = logging.getLogger(__name__)


def _label_values(container: Any, attrs: dict[str, Any]) -> dict[str, str]:
    labels = (attrs.get("Config", {}).get("Labels") or {}) | (attrs.get("Labels") or {})
    image_tags = container.image.tags if (container.image and container.image.tags) else []
    return {
        "name": container.name,
        "id": container.id[:12] if container.id else "",
        "compose_project": labels.get("com.docker.compose.project", ""),
        "compose_service": labels.get("com.docker.compose.service", ""),
        "image": image_tags[0] if image_tags else (attrs.get("Config", {}).get("Image", "")),
    }


def _calc_cpu_seconds(stats: dict[str, Any]) -> float:
    """从 docker stats API 返回值中提取累计 CPU 秒数。

    docker 返回的 `cpu_usage.total_usage` 单位是纳秒,我们换算成秒后作为
    Counter 的累计值,prometheus 端用 rate() 即得 per-CPU ratio。
    """

    total_ns = stats.get("cpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0)
    try:
        return float(total_ns) / 1_000_000_000.0
    except (TypeError, ValueError):
        return 0.0


def _calc_memory(stats: dict[str, Any]) -> tuple[float, float]:
    mem_stats = stats.get("memory_stats", {}) or {}
    usage = float(mem_stats.get("usage", 0) or 0)
    cache = 0.0
    detail = mem_stats.get("stats", {}) or {}
    # cgroup v1 用 total_inactive_file,v2 用 inactive_file
    if "total_inactive_file" in detail:
        cache = float(detail.get("total_inactive_file") or 0)
    elif "inactive_file" in detail:
        cache = float(detail.get("inactive_file") or 0)
    working_set = max(0.0, usage - cache)
    limit = float(mem_stats.get("limit", 0) or 0)
    return working_set, limit


def _calc_network(stats: dict[str, Any]) -> tuple[float, float]:
    rx = 0.0
    tx = 0.0
    for entry in (stats.get("networks") or {}).values():
        rx += float(entry.get("rx_bytes", 0) or 0)
        tx += float(entry.get("tx_bytes", 0) or 0)
    return rx, tx


def _calc_blkio(stats: dict[str, Any]) -> tuple[float, float]:
    read_bytes = 0.0
    write_bytes = 0.0
    blk = stats.get("blkio_stats", {}) or {}
    for entry in blk.get("io_service_bytes_recursive") or []:
        op = (entry.get("op") or "").lower()
        value = float(entry.get("value", 0) or 0)
        if op == "read":
            read_bytes += value
        elif op == "write":
            write_bytes += value
    return read_bytes, write_bytes


class ContainerStatsCollector:
    """周期性轮询 docker stats 并把结果写入 prometheus_client 指标。"""

    def __init__(
        self,
        docker_facade: DockerFacade,
        interval_seconds: float = 15.0,
    ) -> None:
        self._docker = docker_facade
        self._interval = max(2.0, float(interval_seconds))
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        # 记录每个容器上一轮的累计值,确保 Counter 单调递增。
        self._last_cpu: dict[str, float] = {}
        self._last_rx: dict[str, float] = {}
        self._last_tx: dict[str, float] = {}
        self._last_block_read: dict[str, float] = {}
        self._last_block_write: dict[str, float] = {}

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="container-stats-collector")
        logger.info("container stats collector 已启动,采样间隔 %.1fs", self._interval)

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except (asyncio.CancelledError, Exception):
            pass
        self._task = None

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                await asyncio.to_thread(self._collect_once)
                metrics.container_stats_last_success_timestamp.set(time.time())
            except Exception as exc:
                logger.warning("container stats 采集失败: %s", exc)
                metrics.container_stats_collection_failures_total.inc()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._interval)
            except TimeoutError:
                pass

    def _collect_once(self) -> None:
        try:
            client = self._docker.client
        except DockerError as exc:
            raise RuntimeError(f"docker SDK 不可用: {exc}") from exc

        containers = client.containers.list(all=True)
        seen_keys: set[tuple[str, ...]] = set()

        for container in containers:
            attrs = container.attrs or {}
            label_kwargs = _label_values(container, attrs)
            label_key = tuple(label_kwargs[k] for k in metrics.CONTAINER_LABELS)
            seen_keys.add(label_key)

            running = 1.0 if (container.status == "running") else 0.0
            metrics.container_running.labels(**label_kwargs).set(running)

            if running == 0.0:
                # 非运行容器不取 stats,只更新存活标记,避免 docker SDK 抛异常
                continue

            try:
                stats = container.stats(stream=False)
            except Exception as exc:
                logger.debug("容器 %s 取 stats 失败: %s", container.name, exc)
                continue

            cpu_seconds = _calc_cpu_seconds(stats)
            working_set, limit = _calc_memory(stats)
            rx, tx = _calc_network(stats)
            block_read, block_write = _calc_blkio(stats)

            metrics.container_memory_working_set_bytes.labels(**label_kwargs).set(working_set)
            metrics.container_memory_limit_bytes.labels(**label_kwargs).set(limit)

            self._increment(metrics.container_cpu_seconds_total, label_kwargs, label_key, self._last_cpu, cpu_seconds)
            self._increment(metrics.container_network_receive_bytes_total, label_kwargs, label_key, self._last_rx, rx)
            self._increment(
                metrics.container_network_transmit_bytes_total, label_kwargs, label_key, self._last_tx, tx
            )
            self._increment(
                metrics.container_block_read_bytes_total,
                label_kwargs,
                label_key,
                self._last_block_read,
                block_read,
            )
            self._increment(
                metrics.container_block_write_bytes_total,
                label_kwargs,
                label_key,
                self._last_block_write,
                block_write,
            )

        self._purge_disappeared(seen_keys)

    def _increment(
        self,
        counter: _Counter,
        label_kwargs: dict[str, str],
        label_key: tuple[str, ...],
        cache: dict[str, float],
        current_total: float,
    ) -> None:
        cache_key = "|".join(label_key)
        previous = cache.get(cache_key)
        cache[cache_key] = current_total
        if previous is None:
            return
        delta = current_total - previous
        # docker 重启/计数器回绕时,采用当前总值作为新基线,避免 Counter 倒退。
        if delta < 0:
            return
        if delta > 0:
            counter.labels(**label_kwargs).inc(delta)

    def _purge_disappeared(self, seen_keys: set[tuple[str, ...]]) -> None:
        # 容器消失时清理 Gauge 上的旧标签组合,避免假阳性"running=1"。
        # Counter 的历史值由 prometheus 自身保留 staleness,不需主动清。
        for gauge in (
            metrics.container_running,
            metrics.container_memory_working_set_bytes,
            metrics.container_memory_limit_bytes,
        ):
            stale_labels: list[tuple[str, ...]] = []
            for label_combo in list(gauge._metrics.keys()):
                if label_combo not in seen_keys:
                    stale_labels.append(label_combo)
            for combo in stale_labels:
                try:
                    gauge.remove(*combo)
                except KeyError:
                    pass

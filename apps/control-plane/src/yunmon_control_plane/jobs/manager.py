"""一个进程内、线程池版的任务管理器。

KISS:不引入 Celery / Dramatiq 等外部依赖,先用 threading + queue 满足 P2-3。
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class JobStatus(StrEnum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


@dataclass
class Job:
    id: str
    name: str
    status: JobStatus = JobStatus.pending
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    progress: int = 0
    log: list[str] = field(default_factory=list)
    result: Any | None = None
    error: str | None = None

    def append_log(self, message: str) -> None:
        self.log.append(f"[{datetime.now(UTC).isoformat()}] {message}")
        if len(self.log) > 500:
            self.log = self.log[-500:]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "createdAt": self.created_at.isoformat(),
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "finishedAt": self.finished_at.isoformat() if self.finished_at else None,
            "progress": self.progress,
            "log": list(self.log),
            "result": self.result,
            "error": self.error,
        }


JobFunc = Callable[["JobContext"], Any]


class JobContext:
    """传给 job 函数的上下文,可写日志/进度。"""

    def __init__(self, job: Job, manager: JobManager) -> None:
        self._job = job
        self._manager = manager

    def log(self, message: str) -> None:
        with self._manager._lock:
            self._job.append_log(message)

    def progress(self, value: int) -> None:
        with self._manager._lock:
            self._job.progress = max(0, min(100, value))


class JobManager:
    def __init__(self, max_workers: int = 4) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="yunmon-job")
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def submit(self, name: str, fn: JobFunc) -> Job:
        job = Job(id=uuid.uuid4().hex, name=name)
        with self._lock:
            self._jobs[job.id] = job
        ctx = JobContext(job, self)

        def _run() -> None:
            with self._lock:
                job.status = JobStatus.running
                job.started_at = datetime.now(UTC)
                job.append_log(f"job 启动: {name}")
            try:
                result = fn(ctx)
                with self._lock:
                    job.status = JobStatus.succeeded
                    job.result = result
                    job.progress = 100
                    job.append_log("job 成功")
            except Exception as exc:
                with self._lock:
                    job.status = JobStatus.failed
                    job.error = str(exc)
                    job.append_log(f"job 失败: {exc}")
            finally:
                with self._lock:
                    job.finished_at = datetime.now(UTC)

        self._executor.submit(_run)
        return job

    def get(self, job_id: str) -> Job:
        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(f"job {job_id} 不存在")
            return self._jobs[job_id]

    def list(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())

    async def stream(self, job_id: str):
        """yield 任务进度事件,直到任务结束(供 SSE)。"""
        last_log_index = 0
        last_status: str | None = None
        last_progress = -1
        while True:
            job = self.get(job_id)
            with self._lock:
                logs_snapshot = list(job.log[last_log_index:])
                last_log_index = len(job.log)
                progress = job.progress
                status = job.status.value
                error = job.error
                result = job.result

            for log_line in logs_snapshot:
                yield {"event": "log", "data": log_line}
            if progress != last_progress:
                yield {"event": "progress", "data": progress}
                last_progress = progress
            if status != last_status:
                yield {"event": "status", "data": status}
                last_status = status

            if status in {"succeeded", "failed"}:
                yield {
                    "event": "end",
                    "data": {"status": status, "error": error, "result": result},
                }
                return

            await asyncio.sleep(0.5)

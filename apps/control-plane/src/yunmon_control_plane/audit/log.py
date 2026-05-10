"""审计日志(P3-2)。"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class AuditLogger:
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self._lock = threading.Lock()

    def write(
        self,
        *,
        actor: str,
        ip: str,
        user_agent: str,
        action: str,
        target: str = "",
        status: str = "ok",
        error: str | None = None,
        latency_ms: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        record = {
            "ts": datetime.now(UTC).isoformat(),
            "actor": actor,
            "ip": ip,
            "ua": user_agent,
            "action": action,
            "target": target,
            "status": status,
            "error": error,
            "latencyMs": latency_ms,
            "extra": extra or {},
        }
        line = json.dumps(record, ensure_ascii=False) + "\n"
        with self._lock:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as fp:
                fp.write(line)

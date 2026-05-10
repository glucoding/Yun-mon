"""配置变更快照存储(P2-1)。"""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import jsonpatch


def _new_snapshot_id() -> str:
    """ULID-like:13 位毫秒时间戳 + 16 位 hex 随机。"""
    millis = int(time.time() * 1000)
    return f"{millis:013d}-{uuid.uuid4().hex[:16]}"


class SnapshotStore:
    def __init__(self, directory: Path, *, keep_count: int = 50, keep_days: int = 90) -> None:
        self.directory = directory
        self.keep_count = keep_count
        self.keep_days = keep_days

    def _ensure_dir(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)

    def list_snapshots(self) -> list[dict[str, Any]]:
        self._ensure_dir()
        snapshots = []
        for path in sorted(self.directory.glob("*.json"), reverse=True):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            snapshots.append(
                {
                    "snapshotId": payload.get("snapshotId", path.stem),
                    "schemaVersion": payload.get("schemaVersion"),
                    "appliedAt": payload.get("appliedAt"),
                    "actor": payload.get("actor", "unknown"),
                    "summary": payload.get("summary", ""),
                    "diffOpsCount": len(payload.get("diff") or []),
                }
            )
        return snapshots

    def get(self, snapshot_id: str) -> dict[str, Any]:
        path = self.directory / f"{snapshot_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"快照不存在: {snapshot_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def record(
        self,
        *,
        previous: dict[str, Any] | None,
        current: dict[str, Any],
        actor: str,
        summary: str = "",
    ) -> dict[str, Any]:
        self._ensure_dir()
        diff = jsonpatch.make_patch(previous or {}, current).patch if previous is not None else []
        snapshot = {
            "snapshotId": _new_snapshot_id(),
            "schemaVersion": current.get("metadata", {}).get("schemaVersion"),
            "appliedAt": datetime.now(UTC).isoformat(),
            "actor": actor,
            "summary": summary,
            "diff": diff,
            "state": current,
        }
        path = self.directory / f"{snapshot['snapshotId']}.json"
        path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self._evict()
        return {
            key: snapshot[key]
            for key in ("snapshotId", "appliedAt", "actor", "summary", "diff")
        }

    def _evict(self) -> None:
        files = sorted(self.directory.glob("*.json"), reverse=True)
        cutoff = datetime.now(UTC) - timedelta(days=self.keep_days)
        for index, path in enumerate(files):
            if index >= self.keep_count:
                path.unlink(missing_ok=True)
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                applied_at_str = payload.get("appliedAt")
                if applied_at_str:
                    applied_at = datetime.fromisoformat(applied_at_str)
                    if applied_at < cutoff:
                        path.unlink(missing_ok=True)
            except Exception:
                continue

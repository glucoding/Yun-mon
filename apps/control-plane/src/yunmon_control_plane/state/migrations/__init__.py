"""desired-state schema 版本化迁移(P3-7)。

每个迁移函数接受旧版 dict 返回新版 dict,函数顺序按版本号升序。
新增迁移时只需要在 `_MIGRATIONS` 里登记。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .v1_to_v2 import upgrade_v1_to_v2

Migration = Callable[[dict[str, Any]], dict[str, Any]]

_MIGRATIONS: list[tuple[int, Migration]] = [
    (1, upgrade_v1_to_v2),
]


def latest_schema_version() -> int:
    return max(target for _, target in _migrations_with_target()) if _MIGRATIONS else 1


def _migrations_with_target() -> list[tuple[int, int]]:
    return [(source, source + 1) for source, _ in _MIGRATIONS]


def migrate_to_latest(state: dict[str, Any]) -> tuple[dict[str, Any], list[tuple[int, int]]]:
    """按版本顺序顺次升级,返回 (新 state, 已应用迁移列表)。"""
    metadata = state.setdefault("metadata", {})
    current = int(metadata.get("schemaVersion") or 1)
    applied: list[tuple[int, int]] = []
    new_state = state
    for source, fn in _MIGRATIONS:
        if current == source:
            new_state = fn(new_state)
            metadata = new_state.setdefault("metadata", {})
            current = source + 1
            metadata["schemaVersion"] = current
            applied.append((source, current))
    return new_state, applied


__all__ = ["latest_schema_version", "migrate_to_latest"]

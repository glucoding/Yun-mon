"""desired-state 持久层。"""

from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Any

from ..catalog.normalize import deep_merge, normalize_metric_catalog
from .defaults import build_default_state
from .migrations import migrate_to_latest
from .schema import YunmonState


class StateStore:
    """读写 desired-state.json,内部维护规范化和默认值合并。"""

    def __init__(self, path: Path) -> None:
        self.path = path

    # ---------- 读取 ----------

    def load_dict(self) -> dict[str, Any]:
        if not self.path.exists():
            self.ensure()
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        migrated, _ = migrate_to_latest(raw)
        merged = deep_merge(build_default_state(generate_token=False), migrated)
        normalize_metric_catalog(merged)
        return merged

    def load_validated(self) -> YunmonState:
        return YunmonState.model_validate(self.load_dict())

    # ---------- 写入 ----------

    def save_dict(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(state, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def ensure(self) -> dict[str, Any]:
        """首次运行时落盘默认 state(P0-5: 自动生成 stack-agent token)。"""
        if self.path.exists():
            existing = json.loads(self.path.read_text(encoding="utf-8"))
            if not existing.get("stackAgent", {}).get("sharedToken"):
                existing.setdefault("stackAgent", {})["sharedToken"] = secrets.token_urlsafe(32)
                self.save_dict(existing)
            return existing
        default = build_default_state(generate_token=True)
        self.save_dict(default)
        return default

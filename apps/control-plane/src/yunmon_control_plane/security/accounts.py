"""本地账户存储(JSON 文件,P3 起步)。"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import bcrypt

DEFAULT_ROLES: dict[str, list[str]] = {
    "admin": [
        "config:read",
        "config:write",
        "system:restart",
        "audit:read",
        "audit:rollback",
        "users:manage",
    ],
    "operator": ["config:read", "system:restart", "audit:read"],
    "viewer": ["config:read", "audit:read"],
}


@dataclass
class User:
    username: str
    password_hash: str
    roles: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    enabled: bool = True

    def has_permission(self, permission: str) -> bool:
        for role in self.roles:
            if permission in DEFAULT_ROLES.get(role, []):
                return True
        return False


class AccountStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def _load(self) -> dict[str, User]:
        if not self.path.exists():
            return {}
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return {entry["username"]: User(**entry) for entry in raw.get("users", [])}

    def _persist(self, users: dict[str, User]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"users": [asdict(user) for user in users.values()]}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def list_users(self) -> list[User]:
        with self._lock:
            return list(self._load().values())

    def get(self, username: str) -> User | None:
        with self._lock:
            return self._load().get(username)

    def create(self, *, username: str, password: str, roles: list[str], rounds: int = 12) -> User:
        with self._lock:
            users = self._load()
            if username in users:
                raise ValueError(f"用户已存在: {username}")
            user = User(
                username=username,
                password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=rounds)).decode(),
                roles=list(roles),
            )
            users[username] = user
            self._persist(users)
            return user

    def verify(self, username: str, password: str) -> User | None:
        user = self.get(username)
        if user is None or not user.enabled:
            return None
        if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            return None
        return user

    def ensure_admin(self, *, default_password: str = "admin123456", rounds: int = 12) -> User:
        with self._lock:
            users = self._load()
            if "admin" in users:
                return users["admin"]
            user = User(
                username="admin",
                password_hash=bcrypt.hashpw(default_password.encode(), bcrypt.gensalt(rounds=rounds)).decode(),
                roles=["admin"],
            )
            users["admin"] = user
            self._persist(users)
            return user

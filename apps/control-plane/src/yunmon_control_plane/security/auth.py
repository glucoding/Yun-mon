"""JWT 认证服务(P3-1)。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from .accounts import AccountStore, User


@dataclass
class JWTBundle:
    access_token: str
    refresh_token: str
    expires_in: int


class AuthService:
    def __init__(
        self,
        store: AccountStore,
        *,
        secret: str,
        access_ttl: int = 900,
        refresh_ttl: int = 7 * 24 * 3600,
        issuer: str = "yunmon-control-plane",
    ) -> None:
        self.store = store
        self.secret = secret
        self.access_ttl = access_ttl
        self.refresh_ttl = refresh_ttl
        self.issuer = issuer

    def login(self, username: str, password: str) -> JWTBundle | None:
        user = self.store.verify(username, password)
        if user is None:
            return None
        return self._issue_bundle(user)

    def refresh(self, refresh_token: str) -> JWTBundle | None:
        try:
            payload = jwt.decode(refresh_token, self.secret, algorithms=["HS256"], issuer=self.issuer)
        except jwt.PyJWTError:
            return None
        if payload.get("type") != "refresh":
            return None
        user = self.store.get(payload["sub"])
        if user is None or not user.enabled:
            return None
        return self._issue_bundle(user)

    def verify_access(self, token: str) -> User | None:
        try:
            payload = jwt.decode(token, self.secret, algorithms=["HS256"], issuer=self.issuer)
        except jwt.PyJWTError:
            return None
        if payload.get("type") != "access":
            return None
        return self.store.get(payload["sub"])

    def _issue_bundle(self, user: User) -> JWTBundle:
        access = self._encode(user, "access", self.access_ttl)
        refresh = self._encode(user, "refresh", self.refresh_ttl)
        return JWTBundle(access_token=access, refresh_token=refresh, expires_in=self.access_ttl)

    def _encode(self, user: User, token_type: str, ttl: int) -> str:
        now = datetime.now(UTC)
        payload: dict[str, Any] = {
            "sub": user.username,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=ttl)).timestamp()),
            "iss": self.issuer,
            "type": token_type,
            "roles": user.roles,
        }
        return jwt.encode(payload, self.secret, algorithm="HS256")

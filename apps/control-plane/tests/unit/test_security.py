from pathlib import Path

from yunmon_control_plane.security.accounts import AccountStore
from yunmon_control_plane.security.auth import AuthService


def test_account_store_create_and_verify(tmp_path: Path):
    store = AccountStore(tmp_path / "accounts.json")
    store.create(username="admin", password="pa55word!", roles=["admin"], rounds=4)
    user = store.verify("admin", "pa55word!")
    assert user is not None
    assert user.has_permission("config:write")
    assert store.verify("admin", "wrong") is None


def test_jwt_login_refresh(tmp_path: Path):
    store = AccountStore(tmp_path / "accounts.json")
    store.create(username="admin", password="pa55word!", roles=["admin"], rounds=4)
    auth = AuthService(store, secret="x" * 32, access_ttl=60, refresh_ttl=300)
    bundle = auth.login("admin", "pa55word!")
    assert bundle is not None
    user = auth.verify_access(bundle.access_token)
    assert user is not None and user.username == "admin"

    refreshed = auth.refresh(bundle.refresh_token)
    assert refreshed is not None
    user_after = auth.verify_access(refreshed.access_token)
    assert user_after is not None and user_after.username == "admin"


def test_jwt_invalid_token(tmp_path: Path):
    store = AccountStore(tmp_path / "accounts.json")
    auth = AuthService(store, secret="x" * 32)
    assert auth.verify_access("garbage") is None
    assert auth.refresh("garbage") is None

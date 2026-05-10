from pathlib import Path

from yunmon_control_plane.state.store import StateStore


def test_state_store_ensures_token(tmp_path: Path):
    path = tmp_path / "desired-state.json"
    store = StateStore(path)
    state = store.ensure()
    assert state["stackAgent"]["sharedToken"], "首次启动必须自动生成 token"
    assert len(state["stackAgent"]["sharedToken"]) >= 16


def test_state_store_ensure_keeps_existing_token(tmp_path: Path):
    path = tmp_path / "desired-state.json"
    store = StateStore(path)
    initial = store.ensure()
    initial_token = initial["stackAgent"]["sharedToken"]
    again = store.ensure()
    assert again["stackAgent"]["sharedToken"] == initial_token


def test_state_store_load_validated(tmp_path: Path):
    path = tmp_path / "desired-state.json"
    store = StateStore(path)
    store.ensure()
    state = store.load_validated()
    assert state.system.monitoringProject == "yun-mon"

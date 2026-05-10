import time
from pathlib import Path

from yunmon_control_plane.audit.snapshot import SnapshotStore


def test_snapshot_records_diff(tmp_path: Path):
    store = SnapshotStore(tmp_path / "snap")
    previous = {"a": 1, "b": {"c": 2}}
    current = {"a": 1, "b": {"c": 3, "d": 4}}
    meta = store.record(previous=previous, current=current, actor="tester", summary="apply")
    assert meta["snapshotId"]
    snapshots = store.list_snapshots()
    assert len(snapshots) == 1
    detail = store.get(meta["snapshotId"])
    assert detail["state"] == current
    assert any(op for op in detail["diff"] if op.get("path", "").startswith("/b"))


def test_snapshot_keep_count(tmp_path: Path):
    store = SnapshotStore(tmp_path / "snap", keep_count=3, keep_days=365)
    for i in range(5):
        store.record(previous={"x": i}, current={"x": i + 1}, actor="t")
        time.sleep(0.005)
    assert len(store.list_snapshots()) == 3

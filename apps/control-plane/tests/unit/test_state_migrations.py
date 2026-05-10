from yunmon_control_plane.state.migrations import migrate_to_latest


def test_migration_v1_to_v2_adds_new_fields():
    legacy = {
        "metadata": {"schemaVersion": 1, "lastAppliedAt": None},
        "system": {"clusterName": "yun-mon-local"},
        "ports": {},
        "dockerStatsExporter": {"maxWorkers": 8, "targetProject": "yun-mon"},
    }
    new_state, applied = migrate_to_latest(legacy)
    assert applied == [(1, 2)]
    assert new_state["metadata"]["schemaVersion"] == 2
    assert "clusters" in new_state and new_state["clusters"]
    assert "alertReceivers" in new_state
    assert "otelCollector" in new_state
    assert "slos" in new_state
    assert "dockerStatsExporter" not in new_state
    assert new_state["ports"]["otelCollectorOtlpHttpPort"] == 4318


def test_migration_idempotent_for_v2():
    state = {"metadata": {"schemaVersion": 2}, "clusters": [{"id": "default"}]}
    new_state, applied = migrate_to_latest(state)
    assert applied == []
    assert new_state["metadata"]["schemaVersion"] == 2

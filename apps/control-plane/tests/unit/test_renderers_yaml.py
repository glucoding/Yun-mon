import yaml

from yunmon_control_plane.renderers.alertmanager import render_alertmanager
from yunmon_control_plane.renderers.loki import render_loki
from yunmon_control_plane.renderers.prometheus import (
    render_application_targets,
    render_prometheus,
)
from yunmon_control_plane.renderers.promtail import render_promtail
from yunmon_control_plane.renderers.rules import (
    render_application_rules,
    render_metric_catalog_rules,
    render_slo_rules,
)
from yunmon_control_plane.state.defaults import build_default_state


def _state():
    state = build_default_state(generate_token=False)
    state["stackAgent"]["sharedToken"] = "x" * 32
    return state


def test_render_prometheus_yaml_is_valid():
    parsed = yaml.safe_load(render_prometheus(_state()))
    job_names = [job["job_name"] for job in parsed["scrape_configs"]]
    assert "applications" in job_names
    assert "control_plane" in job_names
    assert "cadvisor" in job_names
    assert parsed["alerting"]["alertmanagers"]


def test_render_alertmanager_default_receivers():
    parsed = yaml.safe_load(render_alertmanager(_state()))
    receiver_names = [r["name"] for r in parsed["receivers"]]
    assert "platform-default" in receiver_names
    assert "platform-critical" in receiver_names


def test_render_loki_yaml_is_valid():
    parsed = yaml.safe_load(render_loki(_state()))
    assert parsed["server"]["http_listen_port"] == 3100
    assert parsed["common"]["replication_factor"] == 1


def test_render_promtail_yaml_is_valid():
    parsed = yaml.safe_load(render_promtail(_state()))
    assert len(parsed["scrape_configs"]) == 1
    assert parsed["scrape_configs"][0]["job_name"] == "demo-service-filelogs"


def test_render_application_rules_contains_alerts():
    parsed = yaml.safe_load(render_application_rules(_state()))
    alerts = {rule["alert"] for group in parsed["groups"] for rule in group["rules"] if "alert" in rule}
    assert {"ApplicationInstanceDown", "HighHttp5xxErrorRate", "ContainerHighMemoryUsage"} <= alerts


def test_render_metric_catalog_rules_managed_only():
    parsed = yaml.safe_load(render_metric_catalog_rules(_state()))
    groups = parsed["groups"]
    assert groups, "至少应该有一个 group"
    for group in groups:
        for rule in group["rules"]:
            assert rule["expr"], "managed recording rule 必须带 expr"


def test_render_slo_rules_empty_when_no_slo():
    parsed = yaml.safe_load(render_slo_rules(_state()))
    assert parsed["groups"][0]["rules"] == []


def test_render_slo_rules_with_definition():
    state = _state()
    state["slos"] = [
        {
            "id": "demo-availability",
            "service": "demo-service",
            "objective": 0.99,
            "sliExpression": 'sum(rate(http_server_requests_seconds_count{job="applications",status!~"5.."}[5m])) / sum(rate(http_server_requests_seconds_count{job="applications"}[5m]))',
            "description": "demo 可用性 99% SLO",
        }
    ]
    parsed = yaml.safe_load(render_slo_rules(state))
    alerts = [rule["alert"] for rule in parsed["groups"][0]["rules"]]
    assert any(name.startswith("SLOBurn_demo-availability_") for name in alerts)
    assert len(alerts) == 3  # 1h / 6h / 24h


def test_render_application_targets_filters_disabled():
    apps = [
        {"appId": "a", "enabled": True, "targets": ["10.0.0.1:8080"], "metricsPath": "/m", "environment": "x"},
        {"appId": "b", "enabled": False, "targets": ["10.0.0.2:8080"]},
        {"appId": "c", "enabled": True, "targets": []},
    ]
    output = render_application_targets(apps, "/actuator/prometheus", "local")
    import json

    parsed = json.loads(output)
    assert len(parsed) == 1
    assert parsed[0]["labels"]["app_id"] == "a"

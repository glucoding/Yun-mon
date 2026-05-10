from yunmon_control_plane.renderers.env import _quote_env_value, render_env
from yunmon_control_plane.state.defaults import build_default_state


def test_render_env_contains_required_keys():
    state = build_default_state(generate_token=False)
    state["stackAgent"]["sharedToken"] = "x" * 32
    output = render_env(state)
    for key in (
        "MONITORING_PROJECT=",
        "STACK_AGENT_ENABLED=",
        "STACK_AGENT_BASE_URL=",
        "STACK_AGENT_SHARED_TOKEN=",
        "GRAFANA_HOST_PORT=",
        "DEMO_SERVICE_METRICS_PATH=",
        "OTEL_OTLP_HTTP_PORT=",
    ):
        assert key in output


def test_quote_env_value_handles_special_chars():
    assert _quote_env_value(True) == "true"
    assert _quote_env_value(False) == "false"
    assert _quote_env_value(123) == "123"
    assert _quote_env_value("plain") == "plain"
    assert _quote_env_value("with space") == '"with space"'
    assert _quote_env_value('"quoted"') == r'"\"quoted\""'
    assert _quote_env_value("") == '""'
    assert _quote_env_value("a:b") == '"a:b"'

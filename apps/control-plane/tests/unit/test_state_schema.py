import pytest
from pydantic import ValidationError

from yunmon_control_plane.state.defaults import build_default_state
from yunmon_control_plane.state.schema import YunmonState


def test_default_state_validates():
    state = build_default_state(generate_token=False)
    state["stackAgent"]["sharedToken"] = "x" * 32
    YunmonState.model_validate(state)


def test_token_min_length_enforced():
    state = build_default_state(generate_token=False)
    state["stackAgent"]["sharedToken"] = "short"
    with pytest.raises(ValidationError):
        YunmonState.model_validate(state)


def test_unknown_metric_category_rejected():
    state = build_default_state(generate_token=False)
    state["stackAgent"]["sharedToken"] = "x" * 32
    state["metricCatalog"]["items"][0]["category"] = "unknown-cat"
    with pytest.raises(ValidationError):
        YunmonState.model_validate(state)


def test_managed_recording_rule_requires_expression():
    state = build_default_state(generate_token=False)
    state["stackAgent"]["sharedToken"] = "x" * 32
    for item in state["metricCatalog"]["items"]:
        if item["ruleMode"] == "managed":
            item["expression"] = ""
            with pytest.raises(ValidationError):
                YunmonState.model_validate(state)
            break


def test_application_unique_app_id():
    state = build_default_state(generate_token=False)
    state["stackAgent"]["sharedToken"] = "x" * 32
    state["applications"]["items"].append(
        {
            "appId": "demo-service",
            "enabled": False,
            "metricsPath": "/m",
            "environment": "local",
        }
    )
    with pytest.raises(ValidationError):
        YunmonState.model_validate(state)

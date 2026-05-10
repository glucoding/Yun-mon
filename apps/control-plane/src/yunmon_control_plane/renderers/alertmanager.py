"""渲染 Alertmanager 配置。

P2-5：根据 desired-state 中的 alertReceivers 自动生成 receiver 块。
"""

from __future__ import annotations

from typing import Any

from ._yaml import dump_yaml

_KIND_TO_BLOCK: dict[str, str] = {
    "webhook": "webhook_configs",
    "email": "email_configs",
    "wework": "wechat_configs",
    "dingtalk": "webhook_configs",
    "feishu": "webhook_configs",
}


def _render_receiver(receiver: dict[str, Any]) -> dict[str, Any]:
    name = receiver["name"]
    kind = receiver.get("kind", "webhook")
    config = receiver.get("config") or {}
    block = _KIND_TO_BLOCK.get(kind, "webhook_configs")

    if kind == "webhook":
        entry = {"url": config.get("url", ""), "send_resolved": True}
    elif kind == "email":
        entry = {
            "to": config.get("to", ""),
            "from": config.get("from", ""),
            "smarthost": config.get("smarthost", ""),
            "auth_username": config.get("authUsername", ""),
            "auth_password": config.get("authPassword", ""),
            "send_resolved": True,
        }
    elif kind == "wework":
        entry = {
            "corp_id": config.get("corpId", ""),
            "agent_id": config.get("agentId", ""),
            "api_secret": config.get("apiSecret", ""),
            "to_party": config.get("toParty", ""),
            "send_resolved": True,
        }
    elif kind == "dingtalk":
        entry = {"url": config.get("url", ""), "send_resolved": True}
    elif kind == "feishu":
        entry = {"url": config.get("url", ""), "send_resolved": True}
    else:
        entry = {"url": config.get("url", "")}

    return {"name": name, block: [entry]}


def render_alertmanager(state: dict[str, Any]) -> str:
    am = state["alertmanager"]
    receivers = state.get("alertReceivers") or []

    enabled_receivers = [r for r in receivers if r.get("enabled")]
    placeholder_default = {
        "name": "platform-default",
        "kind": "webhook",
        "config": {"url": "http://127.0.0.1:9999/placeholder"},
    }
    placeholder_critical = {
        "name": "platform-critical",
        "kind": "webhook",
        "config": {"url": "http://127.0.0.1:9999/placeholder"},
    }
    receiver_definitions: list[dict[str, Any]] = []
    if not any(r["name"] == "platform-default" for r in enabled_receivers):
        receiver_definitions.append(_render_receiver(placeholder_default))
    if not any(r["name"] == "platform-critical" for r in enabled_receivers):
        receiver_definitions.append(_render_receiver(placeholder_critical))
    receiver_definitions.extend(_render_receiver(r) for r in enabled_receivers)

    routes = []
    for receiver in enabled_receivers:
        matchers = []
        for matcher in receiver.get("matchers", []):
            for key, value in matcher.items():
                if value:
                    matchers.append(f'{key}="{value}"')
        if matchers:
            routes.append({"receiver": receiver["name"], "matchers": matchers})
    if not any(r["receiver"] == "platform-critical" for r in routes):
        routes.append({"receiver": "platform-critical", "matchers": ['severity="critical"']})

    config = {
        "global": {"resolve_timeout": am["resolveTimeout"]},
        "route": {
            "receiver": "platform-default",
            "group_by": list(am["groupBy"]),
            "group_wait": am["groupWait"],
            "group_interval": am["groupInterval"],
            "repeat_interval": am["repeatInterval"],
            "routes": routes,
        },
        "inhibit_rules": [
            {
                "source_matchers": ['severity="critical"'],
                "target_matchers": ['severity="warning"'],
                "equal": ["service"],
            }
        ],
        "receivers": receiver_definitions,
    }
    return dump_yaml(config)

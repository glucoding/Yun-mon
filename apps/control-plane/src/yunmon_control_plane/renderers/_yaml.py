"""YAML 渲染统一入口(P1-3 替代手写字符串拼接)。"""

from __future__ import annotations

from typing import Any

import yaml


def dump_yaml(data: Any) -> str:
    """渲染为 YAML 文本,允许中文,保持字段顺序。"""
    return yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=200,
    )

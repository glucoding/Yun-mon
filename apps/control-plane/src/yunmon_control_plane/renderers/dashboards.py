"""Grafana 仪表盘渲染。"""

from __future__ import annotations

import json
from typing import Any


def _annotations_block() -> dict[str, Any]:
    return {
        "list": [
            {
                "builtIn": 1,
                "datasource": {"type": "grafana", "uid": "-- Grafana --"},
                "enable": True,
                "hide": True,
                "iconColor": "rgba(0, 211, 255, 1)",
                "name": "Annotations & Alerts",
                "type": "dashboard",
            }
        ]
    }


def render_control_center_dashboard(state: dict[str, Any]) -> str:
    port = state["ports"]["controlPlaneHostPort"]
    dashboard = {
        "annotations": _annotations_block(),
        "editable": True,
        "graphTooltip": 0,
        "id": None,
        "panels": [
            {
                "datasource": {"type": "grafana", "uid": "-- Grafana --"},
                "gridPos": {"h": 12, "w": 24, "x": 0, "y": 0},
                "id": 1,
                "options": {
                    "content": (
                        "# 统一控制台\n\n"
                        f"[打开 Yun-mon 控制台](http://127.0.0.1:{port}/)\n\n"
                        "在控制台调整监测参数、自动渲染组件配置、热重载 Prometheus、回滚配置或触发监测运行时重建。"
                    ),
                    "mode": "markdown",
                },
                "title": "Control Plane Entry",
                "type": "text",
            }
        ],
        "refresh": "30s",
        "schemaVersion": 39,
        "tags": ["yun-mon", "control-plane"],
        "time": {"from": "now-1h", "to": "now"},
        "title": "Yun-mon Control Center",
        "uid": "yunmon-control-center",
        "version": 2,
    }
    return json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n"


def _dashboard_panel_type(metric: dict[str, Any]) -> str:
    panel_type = metric.get("visualization", {}).get("panelType", "stat")
    return panel_type if panel_type in {"timeseries", "stat", "gauge"} else "stat"


def render_metric_dashboard(state: dict[str, Any]) -> str:
    catalog = state["metricCatalog"]
    category_order = [item["id"] for item in catalog["categories"]]
    category_lookup = {item["id"]: item for item in catalog["categories"]}

    visible = [
        item
        for item in catalog["items"]
        if item.get("enabled") and item.get("visualization", {}).get("showOnDashboard", False)
    ]
    visible.sort(
        key=lambda metric: (
            category_order.index(metric.get("category"))
            if metric.get("category") in category_order
            else len(category_order),
            metric.get("displayName", ""),
        )
    )

    panels = []
    y_position = 0
    panel_id = 1
    row_used_width = 0

    for metric in visible:
        panel_type = _dashboard_panel_type(metric)
        if panel_type == "timeseries":
            width, height = 12, 9
        else:
            width, height = 8, 8

        if row_used_width + width > 24:
            y_position += height
            row_used_width = 0

        x_position = row_used_width
        row_used_width += width

        viz = metric["visualization"]

        # catalog 中的 `colorMode` 表达的是 stat/gauge 面板的"颜色应用模式"
        # (Grafana 合法值: value / background / value_and_name / none),用于 panel.options.colorMode。
        # 它与 fieldConfig.defaults.color.mode (调色板模式: thresholds / palette-classic / fixed / ...)
        # 是两个完全不同的字段,共用同一字段名是历史遗留,这里显式区分:
        #   - stat/gauge 面板: 调色板用 `thresholds`(因为它们是单值面板,颜色应跟着阈值跑)
        #   - timeseries: 调色板用 `palette-classic`
        valid_field_color_modes = {
            "fixed",
            "shades",
            "thresholds",
            "palette-classic",
            "palette-classic-by-name",
            "continuous-GrYlRd",
            "continuous-RdYlGr",
            "continuous-BlYlRd",
            "continuous-YlRd",
            "continuous-BlPu",
            "continuous-YlBl",
            "continuous-blues",
            "continuous-reds",
            "continuous-greens",
            "continuous-purples",
        }
        explicit_field_color_mode = viz.get("fieldColorMode")
        if explicit_field_color_mode in valid_field_color_modes:
            field_color_mode = explicit_field_color_mode
        elif panel_type in {"stat", "gauge"}:
            field_color_mode = "thresholds"
        else:
            field_color_mode = "palette-classic"

        field_config = {
            "defaults": {
                "unit": viz.get("unit") or metric.get("unit") or "short",
                "decimals": viz.get("decimals", 0),
                "color": {"mode": field_color_mode},
            },
            "overrides": [],
        }
        if panel_type in {"stat", "gauge"}:
            field_config["defaults"]["thresholds"] = {
                "mode": "absolute",
                "steps": [
                    {"color": "green", "value": None},
                    {"color": "orange", "value": 0.7 if metric.get("unit") == "percentunit" else None},
                ],
            }

        panel = {
            "datasource": {"type": "prometheus", "uid": "prometheus"},
            "fieldConfig": field_config,
            "gridPos": {"h": height, "w": width, "x": x_position, "y": y_position},
            "id": panel_id,
            "targets": [
                {
                    "expr": metric["metricName"],
                    "legendFormat": metric["displayName"],
                    "refId": "A",
                }
            ],
            "title": (
                f"{metric['displayName']} · "
                f"{category_lookup.get(metric['category'], {}).get('name', metric['category'])}"
            ),
            "type": panel_type,
        }
        if panel_type == "timeseries":
            panel["options"] = {
                "legend": {"displayMode": "table", "placement": "bottom"},
                "tooltip": {"mode": "single"},
            }
        elif panel_type == "stat":
            valid_stat_color_modes = {"value", "background", "background_solid", "value_and_name", "none"}
            stat_color_mode = viz.get("colorMode") if viz.get("colorMode") in valid_stat_color_modes else "value"
            panel["options"] = {
                "reduceOptions": {"values": False, "calcs": ["lastNotNull"], "fields": ""},
                "orientation": "auto",
                "textMode": "auto",
                "colorMode": stat_color_mode,
                "graphMode": "area",
                "justifyMode": "auto",
            }
        else:
            panel["options"] = {
                "reduceOptions": {"values": False, "calcs": ["lastNotNull"], "fields": ""},
                "showThresholdLabels": False,
                "showThresholdMarkers": True,
            }
        panels.append(panel)
        panel_id += 1

    dashboard = {
        "annotations": _annotations_block(),
        "editable": True,
        "graphTooltip": 0,
        "id": None,
        "panels": panels,
        "refresh": "30s",
        "schemaVersion": 39,
        "tags": ["yun-mon", "metric-catalog"],
        "time": {"from": "now-1h", "to": "now"},
        "title": "Yun-mon Metric Catalog",
        "uid": "yunmon-metric-catalog",
        "version": 1,
    }
    return json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n"


def render_slo_dashboard(state: dict[str, Any]) -> str:
    """P3-4：SLO 概览仪表盘。"""
    slos = state.get("slos") or []
    panels = []
    y_position = 0
    panel_id = 1

    if not slos:
        panels.append(
            {
                "datasource": {"type": "grafana", "uid": "-- Grafana --"},
                "gridPos": {"h": 6, "w": 24, "x": 0, "y": 0},
                "id": panel_id,
                "options": {
                    "content": (
                        "# SLO 概览\n\n当前未配置任何 SLO。"
                        "请在控制台 `平台配置 → SLO` 面板中创建 SLO 定义后,"
                        "本仪表盘将自动展示错误预算燃烧率与剩余预算。"
                    ),
                    "mode": "markdown",
                },
                "title": "SLO 概览",
                "type": "text",
            }
        )

    for slo in slos:
        slo_id = slo["id"]
        objective = float(slo["objective"])
        sli = slo["sliExpression"]

        panels.append(
            {
                "datasource": {"type": "prometheus", "uid": "prometheus"},
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": y_position},
                "id": panel_id,
                "targets": [{"expr": sli, "legendFormat": slo["service"], "refId": "A"}],
                "title": f"{slo_id} · 当前 SLI",
                "type": "timeseries",
                "fieldConfig": {
                    "defaults": {"unit": "percentunit", "decimals": 4, "color": {"mode": "thresholds"}},
                    "overrides": [],
                },
                "options": {"legend": {"displayMode": "table", "placement": "bottom"}},
            }
        )
        panel_id += 1
        panels.append(
            {
                "datasource": {"type": "prometheus", "uid": "prometheus"},
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": y_position},
                "id": panel_id,
                "targets": [
                    {
                        "expr": f"({sli}) - {objective}",
                        "legendFormat": "剩余预算",
                        "refId": "A",
                    }
                ],
                "title": f"{slo_id} · 错误预算余量(目标 {objective:.4f})",
                "type": "stat",
                "fieldConfig": {
                    "defaults": {
                        "unit": "percentunit",
                        "decimals": 4,
                        "color": {"mode": "thresholds"},
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "red", "value": None},
                                {"color": "orange", "value": 0},
                                {"color": "green", "value": 0.001},
                            ],
                        },
                    },
                    "overrides": [],
                },
                "options": {
                    "reduceOptions": {"values": False, "calcs": ["lastNotNull"], "fields": ""},
                    "colorMode": "background",
                    "graphMode": "none",
                    "textMode": "auto",
                },
            }
        )
        panel_id += 1
        y_position += 8

    dashboard = {
        "annotations": _annotations_block(),
        "editable": True,
        "graphTooltip": 0,
        "id": None,
        "panels": panels,
        "refresh": "30s",
        "schemaVersion": 39,
        "tags": ["yun-mon", "slo"],
        "time": {"from": "now-7d", "to": "now"},
        "title": "Yun-mon SLO Overview",
        "uid": "yunmon-slo-overview",
        "version": 1,
    }
    return json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n"

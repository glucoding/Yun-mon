"""渲染 Prometheus 规则文件:
- application-rules.yml(基础告警 + golden signals recording)
- metric-catalog-rules.yml(用户托管的 recording rules)
- slo-rules.yml(P3-4 multi-window multi-burn-rate 告警)
"""

from __future__ import annotations

from typing import Any

from ._yaml import dump_yaml


def render_application_rules(state: dict[str, Any]) -> str:
    """golden signals + 基础告警(替换原 docker-stats-exporter 指标为 cAdvisor 等价物)。"""
    config = {
        "groups": [
            {
                "name": "golden_signals_recording",
                "interval": "30s",
                "rules": [
                    {
                        "record": "service:http_requests:rate1m",
                        "expr": (
                            'sum by (service, status) '
                            '(rate(http_server_requests_seconds_count{job="applications"}[1m]))'
                        ),
                    },
                    {
                        "record": "service:http_errors:ratio5m",
                        "expr": (
                            'sum by (service) (rate(http_server_requests_seconds_count'
                            '{job="applications",status=~"5.."}[5m]))\n'
                            '/\nclamp_min(sum by (service) (rate(http_server_requests_seconds_count'
                            '{job="applications"}[5m])), 0.001)\n'
                        ),
                    },
                    {
                        "record": "service:http_latency:p95_5m",
                        "expr": (
                            "histogram_quantile(\n  0.95,\n  sum by (service, le) (rate("
                            'http_server_requests_seconds_bucket{job="applications"}[5m]))\n)\n'
                        ),
                    },
                ],
            },
            {
                "name": "alerting_rules",
                "interval": "30s",
                "rules": [
                    {
                        "alert": "ApplicationInstanceDown",
                        "expr": 'up{job="applications"} == 0',
                        "for": "2m",
                        "labels": {"severity": "critical"},
                        "annotations": {
                            "summary": "应用实例不可用",
                            "description": "服务 {{ $labels.service }} 已连续 2 分钟采集失败。",
                        },
                    },
                    {
                        "alert": "HighHttp5xxErrorRate",
                        "expr": "service:http_errors:ratio5m > 0.05",
                        "for": "5m",
                        "labels": {"severity": "warning"},
                        "annotations": {
                            "summary": "应用 5xx 错误率过高",
                            "description": "服务 {{ $labels.service }} 最近 5 分钟 5xx 错误率超过 5%。",
                        },
                    },
                    {
                        "alert": "HighHttpP95Latency",
                        "expr": "service:http_latency:p95_5m > 0.8",
                        "for": "5m",
                        "labels": {"severity": "warning"},
                        "annotations": {
                            "summary": "应用 P95 延迟过高",
                            "description": "服务 {{ $labels.service }} 最近 5 分钟 P95 延迟超过 800ms。",
                        },
                    },
                    {
                        "alert": "HighBusinessQueueDepth",
                        "expr": 'yunmon_business_queue_depth{job="applications"} > 50',
                        "for": "3m",
                        "labels": {"severity": "warning"},
                        "annotations": {
                            "summary": "业务队列积压",
                            "description": "服务 {{ $labels.service }} 队列深度超过 50。",
                        },
                    },
                    {
                        "alert": "ContainerHighMemoryUsage",
                        "expr": (
                            'container_memory_working_set_bytes{name=~".+",image!=""} / 1024 / 1024 > 512'
                        ),
                        "for": "5m",
                        "labels": {"severity": "warning"},
                        "annotations": {
                            "summary": "容器内存使用偏高",
                            "description": "容器 {{ $labels.name }} 内存工作集持续超过 512MB。",
                        },
                    },
                    {
                        "alert": "ContainerHighCpuUsage",
                        "expr": (
                            'avg_over_time(rate(container_cpu_usage_seconds_total'
                            '{name=~".+",image!=""}[5m])[5m:30s]) > 0.8'
                        ),
                        "for": "5m",
                        "labels": {"severity": "warning"},
                        "annotations": {
                            "summary": "容器 CPU 使用率偏高",
                            "description": "容器 {{ $labels.name }} 最近 5 分钟 CPU 使用率超过 80%。",
                        },
                    },
                ],
            },
        ]
    }
    return dump_yaml(config)


def render_metric_catalog_rules(state: dict[str, Any]) -> str:
    catalog = state.get("metricCatalog", {})
    items = catalog.get("items", [])
    managed = [
        item
        for item in items
        if item.get("enabled")
        and item.get("sourceType") == "recording_rule"
        and item.get("ruleMode") == "managed"
    ]
    category_groups: dict[str, list[dict[str, Any]]] = {}
    for item in managed:
        category_groups.setdefault(item["category"], []).append(item)

    if not category_groups:
        return dump_yaml(
            {
                "groups": [
                    {"name": "metric_catalog_managed", "interval": "30s", "rules": []}
                ]
            }
        )

    groups = []
    for category in (entry["id"] for entry in catalog["categories"]):
        category_items = category_groups.get(category) or []
        if not category_items:
            continue
        groups.append(
            {
                "name": f"metric_catalog_{category}",
                "interval": "30s",
                "rules": [
                    {
                        "record": item["metricName"],
                        "expr": item["expression"],
                        "labels": {
                            "metric_catalog_id": item["metricId"],
                            "metric_category": item["category"],
                        },
                    }
                    for item in category_items
                ],
            }
        )
    return dump_yaml({"groups": groups})


def render_slo_rules(state: dict[str, Any]) -> str:
    """SLO multi-window multi-burn-rate 告警(P3-4)。

    参考 Google SRE Workbook:
        - 1h 窗口,burn rate > 14.4
        - 6h 窗口,burn rate > 6
        - 24h 窗口,burn rate > 3
    """
    slos = state.get("slos") or []
    if not slos:
        return dump_yaml({"groups": [{"name": "slo_rules", "interval": "30s", "rules": []}]})

    rules = []
    for slo in slos:
        slo_id = slo["id"]
        objective = float(slo["objective"])
        budget_consumption = 1 - objective
        sli = slo["sliExpression"]
        for window, burn, severity in (("1h", 14.4, "critical"), ("6h", 6, "warning"), ("24h", 3, "warning")):
            rules.append(
                {
                    "alert": f"SLOBurn_{slo_id}_{window}",
                    "expr": f"(1 - ({sli})) > {round(burn * budget_consumption, 6)}",
                    "for": "5m",
                    "labels": {"severity": severity, "slo": slo_id, "window": window},
                    "annotations": {
                        "summary": f"SLO {slo_id} 在 {window} 窗口内错误预算燃烧速率过快",
                        "description": (
                            f"服务 {{ $labels.service }} 在 {window} 窗口内已超过 burn rate {burn} 阈值。"
                        ),
                    },
                }
            )
    return dump_yaml({"groups": [{"name": "slo_rules", "interval": "30s", "rules": rules}]})

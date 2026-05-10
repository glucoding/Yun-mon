"""指标目录的官方初始集合。

P0-1：本模块是 `CANONICAL_METRIC_CATALOG` 在整个项目中唯一的定义点。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

CANONICAL_METRIC_CATALOG: dict[str, Any] = {
    "categories": [
        {
            "id": "basic",
            "name": "基础指标",
            "description": "直接来源于应用、容器或平台采集链路的原始指标。",
        },
        {
            "id": "business",
            "name": "业务指标",
            "description": "反映业务应用运行效果、处理结果和排队状态的专属指标目录。",
        },
        {
            "id": "composite",
            "name": "组合指标",
            "description": "通过多个基础指标或记录规则组合而成的服务级指标。",
        },
        {
            "id": "macro",
            "name": "宏观指标",
            "description": "反映平台整体健康度、规模和治理效果的宏观视角指标。",
        },
    ],
    "items": [
        {
            "metricId": "http_server_requests_total",
            "metricName": "http_server_requests_seconds_count",
            "displayName": "HTTP 请求总数",
            "category": "basic",
            "sourceType": "raw",
            "ruleMode": "external",
            "description": "应用暴露的 HTTP 请求累计计数,可用于计算吞吐率、错误率和延迟指标。",
            "expression": "",
            "derivedFrom": [],
            "unit": "short",
            "enabled": True,
            "visualization": {
                "panelType": "timeseries",
                "unit": "short",
                "decimals": 0,
                "colorMode": "palette-classic",
                "showOnDashboard": False,
            },
        },
        {
            "metricId": "jvm_memory_used_bytes",
            "metricName": "jvm_memory_used_bytes",
            "displayName": "JVM 内存使用量",
            "category": "basic",
            "sourceType": "raw",
            "ruleMode": "external",
            "description": "应用 JVM 当前已使用内存,用于观察堆和非堆资源占用变化。",
            "expression": "",
            "derivedFrom": [],
            "unit": "bytes",
            "enabled": True,
            "visualization": {
                "panelType": "timeseries",
                "unit": "bytes",
                "decimals": 0,
                "colorMode": "palette-classic",
                "showOnDashboard": False,
            },
        },
        {
            "metricId": "process_cpu_usage",
            "metricName": "process_cpu_usage",
            "displayName": "进程 CPU 使用率",
            "category": "basic",
            "sourceType": "raw",
            "ruleMode": "external",
            "description": "应用进程 CPU 使用率,可作为服务负载和性能分析的基线指标。",
            "expression": "",
            "derivedFrom": [],
            "unit": "percentunit",
            "enabled": True,
            "visualization": {
                "panelType": "timeseries",
                "unit": "percentunit",
                "decimals": 3,
                "colorMode": "palette-classic",
                "showOnDashboard": False,
            },
        },
        {
            "metricId": "business_orders_processed_total",
            "metricName": "yunmon_business_orders_processed_total",
            "displayName": "订单处理总数",
            "category": "business",
            "sourceType": "raw",
            "ruleMode": "external",
            "description": "示例业务累计处理成功的订单数量。",
            "expression": "",
            "derivedFrom": [],
            "unit": "short",
            "enabled": True,
            "visualization": {
                "panelType": "stat",
                "unit": "short",
                "decimals": 0,
                "colorMode": "value",
                "showOnDashboard": True,
            },
        },
        {
            "metricId": "business_orders_failed_total",
            "metricName": "yunmon_business_orders_failed_total",
            "displayName": "订单失败总数",
            "category": "business",
            "sourceType": "raw",
            "ruleMode": "external",
            "description": "示例业务累计处理失败的订单数量。",
            "expression": "",
            "derivedFrom": [],
            "unit": "short",
            "enabled": True,
            "visualization": {
                "panelType": "stat",
                "unit": "short",
                "decimals": 0,
                "colorMode": "background",
                "showOnDashboard": True,
            },
        },
        {
            "metricId": "business_queue_depth",
            "metricName": "yunmon_business_queue_depth",
            "displayName": "业务队列深度",
            "category": "business",
            "sourceType": "raw",
            "ruleMode": "external",
            "description": "示例业务当前待处理队列深度。",
            "expression": "",
            "derivedFrom": [],
            "unit": "short",
            "enabled": True,
            "visualization": {
                "panelType": "gauge",
                "unit": "short",
                "decimals": 0,
                "colorMode": "value",
                "showOnDashboard": True,
            },
        },
        {
            "metricId": "business_orders_failure_ratio",
            "metricName": "business:orders:failure_ratio",
            "displayName": "订单失败占比",
            "category": "composite",
            "sourceType": "recording_rule",
            "ruleMode": "managed",
            "description": "由订单成功总数和失败总数组合计算出的业务失败占比。",
            "expression": (
                "yunmon_business_orders_failed_total / clamp_min("
                "yunmon_business_orders_processed_total + yunmon_business_orders_failed_total, 1)"
            ),
            "derivedFrom": [
                "yunmon_business_orders_failed_total",
                "yunmon_business_orders_processed_total",
            ],
            "unit": "percentunit",
            "enabled": True,
            "visualization": {
                "panelType": "gauge",
                "unit": "percentunit",
                "decimals": 3,
                "colorMode": "thresholds",
                "showOnDashboard": True,
            },
        },
        {
            "metricId": "http_requests_rate1m",
            "metricName": "service:http_requests:rate1m",
            "displayName": "HTTP 吞吐率(1m)",
            "category": "composite",
            "sourceType": "recording_rule",
            "ruleMode": "external",
            "description": "按服务聚合的 1 分钟 HTTP 请求速率。",
            "expression": (
                'sum by (service, status) (rate(http_server_requests_seconds_count{job="applications"}[1m]))'
            ),
            "derivedFrom": ["http_server_requests_seconds_count"],
            "unit": "reqps",
            "enabled": True,
            "visualization": {
                "panelType": "timeseries",
                "unit": "reqps",
                "decimals": 2,
                "colorMode": "palette-classic",
                "showOnDashboard": True,
            },
        },
        {
            "metricId": "http_errors_ratio5m",
            "metricName": "service:http_errors:ratio5m",
            "displayName": "HTTP 5xx 错误率(5m)",
            "category": "composite",
            "sourceType": "recording_rule",
            "ruleMode": "external",
            "description": "按服务聚合的 5 分钟 HTTP 5xx 错误比例。",
            "expression": (
                'sum by (service) (rate(http_server_requests_seconds_count{job="applications",status=~"5.."}[5m])) '
                '/ clamp_min(sum by (service) (rate(http_server_requests_seconds_count{job="applications"}[5m])), 0.001)'
            ),
            "derivedFrom": ["http_server_requests_seconds_count"],
            "unit": "percentunit",
            "enabled": True,
            "visualization": {
                "panelType": "timeseries",
                "unit": "percentunit",
                "decimals": 3,
                "colorMode": "thresholds",
                "showOnDashboard": True,
            },
        },
        {
            "metricId": "http_latency_p95_5m",
            "metricName": "service:http_latency:p95_5m",
            "displayName": "HTTP P95 延迟(5m)",
            "category": "composite",
            "sourceType": "recording_rule",
            "ruleMode": "external",
            "description": "按服务聚合的 5 分钟 P95 HTTP 延迟。",
            "expression": (
                "histogram_quantile(0.95, sum by (service, le) "
                '(rate(http_server_requests_seconds_bucket{job="applications"}[5m])))'
            ),
            "derivedFrom": ["http_server_requests_seconds_bucket"],
            "unit": "s",
            "enabled": True,
            "visualization": {
                "panelType": "timeseries",
                "unit": "s",
                "decimals": 3,
                "colorMode": "palette-classic",
                "showOnDashboard": True,
            },
        },
        {
            "metricId": "applications_up_total",
            "metricName": "platform:applications:up_total",
            "displayName": "在线应用数",
            "category": "macro",
            "sourceType": "recording_rule",
            "ruleMode": "managed",
            "description": "当前已纳入监管并在线的应用实例总数。",
            "expression": 'sum(up{job="applications"})',
            "derivedFrom": ["up"],
            "unit": "short",
            "enabled": True,
            "visualization": {
                "panelType": "stat",
                "unit": "short",
                "decimals": 0,
                "colorMode": "background",
                "showOnDashboard": True,
            },
        },
        {
            "metricId": "applications_up_ratio",
            "metricName": "platform:applications:up_ratio",
            "displayName": "应用在线率",
            "category": "macro",
            "sourceType": "recording_rule",
            "ruleMode": "managed",
            "description": "当前应用实例的总体在线比例。",
            "expression": (
                'sum(up{job="applications"}) / clamp_min(count(up{job="applications"}), 1)'
            ),
            "derivedFrom": ["up"],
            "unit": "percentunit",
            "enabled": True,
            "visualization": {
                "panelType": "gauge",
                "unit": "percentunit",
                "decimals": 3,
                "colorMode": "thresholds",
                "showOnDashboard": True,
            },
        },
    ],
}

LEGACY_BUSINESS_METRIC_IDS = frozenset(
    {
        "business_orders_processed_total",
        "business_orders_failed_total",
        "business_queue_depth",
    }
)


def canonical_copy() -> dict[str, Any]:
    """返回 canonical 目录的深拷贝,避免被外部代码原地修改。"""
    return deepcopy(CANONICAL_METRIC_CATALOG)

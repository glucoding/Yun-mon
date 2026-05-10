"""指标命名 → 可视化/分类的启发式提示。

P2-8 之后这一层会被 Prometheus `/api/v1/metadata` 返回的真实 HELP/TYPE 取代,
当前先保留作为兜底。所有中文都直接以 UTF-8 字符书写(P0-2)。
"""

from __future__ import annotations

from typing import Any

EXACT_METRIC_HINTS: dict[str, dict[str, Any]] = {
    "http_server_requests_seconds_count": {
        "displayName": "HTTP 请求总数",
        "description": "应用对外提供的 HTTP 请求累计计数,是计算吞吐率、错误率和延迟的基础来源。",
        "category": "basic",
        "unit": "short",
        "panelType": "timeseries",
        "colorMode": "palette-classic",
    },
    "http_server_requests_seconds_bucket": {
        "displayName": "HTTP 延迟桶",
        "description": "用于统计 HTTP 延迟分布的桶型指标,可用来组合 P95/P99 延迟指标。",
        "category": "basic",
        "unit": "short",
        "panelType": "timeseries",
        "colorMode": "palette-classic",
    },
    "jvm_memory_used_bytes": {
        "displayName": "JVM 内存使用量",
        "description": "应用 JVM 当前已使用内存,可用于观察堆和非堆资源占用。",
        "category": "basic",
        "unit": "bytes",
        "panelType": "timeseries",
        "colorMode": "palette-classic",
    },
    "process_cpu_usage": {
        "displayName": "进程 CPU 使用率",
        "description": "当前应用进程的 CPU 使用率,可用于判断服务负载和资源紧张程度。",
        "category": "basic",
        "unit": "percentunit",
        "panelType": "timeseries",
        "colorMode": "palette-classic",
    },
    "up": {
        "displayName": "目标在线状态",
        "description": "Prometheus 对采集目标的存活检测,1 表示可抓取,0 表示不可达。",
        "category": "basic",
        "unit": "short",
        "panelType": "stat",
        "colorMode": "background",
    },
    "yunmon_business_orders_processed_total": {
        "displayName": "订单处理总数",
        "description": "业务应用累计处理成功的订单数量。",
        "category": "business",
        "unit": "short",
        "panelType": "stat",
        "colorMode": "value",
    },
    "yunmon_business_orders_failed_total": {
        "displayName": "订单失败总数",
        "description": "业务应用累计处理失败的订单数量。",
        "category": "business",
        "unit": "short",
        "panelType": "stat",
        "colorMode": "background",
    },
    "yunmon_business_queue_depth": {
        "displayName": "业务队列深度",
        "description": "业务应用当前待处理队列的堆积深度,可用于观察积压情况。",
        "category": "business",
        "unit": "short",
        "panelType": "gauge",
        "colorMode": "value",
    },
}

PREFIX_METRIC_HINTS: list[dict[str, Any]] = [
    {
        "prefix": "service:",
        "displayName": "服务组合指标",
        "description": "按服务维度聚合计算出来的组合指标,可用于服务健康度评估。",
        "category": "composite",
        "unit": "short",
        "panelType": "timeseries",
        "colorMode": "palette-classic",
        "sourceType": "recording_rule",
    },
    {
        "prefix": "platform:",
        "displayName": "平台宏观指标",
        "description": "面向平台整体运行态势的宏观指标,适合用来看整体规模和在线状态。",
        "category": "macro",
        "unit": "short",
        "panelType": "stat",
        "colorMode": "background",
        "sourceType": "recording_rule",
    },
    {
        "prefix": "container_",
        "displayName": "容器运行指标",
        "description": "cAdvisor 采集的容器资源指标,可用于容器 CPU、内存、网络和 IO 监控。",
        "category": "basic",
        "unit": "short",
        "panelType": "timeseries",
        "colorMode": "palette-classic",
        "sourceType": "raw",
    },
    {
        "prefix": "control_plane_",
        "displayName": "控制面运行指标",
        "description": "control-plane 自身暴露的运行指标,可用于观察配置发布和控制台负载状态。",
        "category": "basic",
        "unit": "short",
        "panelType": "timeseries",
        "colorMode": "palette-classic",
        "sourceType": "raw",
    },
    {
        "prefix": "stack_agent_",
        "displayName": "宿主机代理指标",
        "description": "host stack-agent 暴露的宿主机执行指标,可用于观察重建、重启和协调状态。",
        "category": "basic",
        "unit": "short",
        "panelType": "timeseries",
        "colorMode": "palette-classic",
        "sourceType": "raw",
    },
    {
        "prefix": "yunmon_business_",
        "displayName": "业务应用指标",
        "description": "业务应用自定义暴露的监测指标,可体现订单、队列和业务成果等信息。",
        "category": "business",
        "unit": "short",
        "panelType": "stat",
        "colorMode": "value",
        "sourceType": "raw",
    },
]


_DEFAULT_PROFILE: dict[str, Any] = {
    "displayName": "未知指标",
    "description": "这是 Prometheus 已发现的实时指标,当前还未纳入指标目录,建议根据实际业务含义补充名称、作用和可视化方式。",
    "category": "basic",
    "unit": "short",
    "panelType": "timeseries",
    "colorMode": "palette-classic",
    "sourceType": "raw",
}


def humanize_metric_name(metric_name: str) -> str:
    text = str(metric_name or "").replace(":", " ").replace(".", " ").replace("_", " ").strip()
    if not text:
        return "未命名指标"
    tokens = [token for token in text.split() if token]
    if not tokens:
        return "未命名指标"

    upper_keep = {"HTTP", "JVM", "CPU", "IO", "P95", "P99", "5XX"}
    normalized = []
    for token in tokens:
        upper = token.upper()
        if upper in upper_keep:
            normalized.append(upper)
        elif token.isupper():
            normalized.append(token)
        else:
            normalized.append(token.capitalize())
    return " ".join(normalized)


def infer_metric_profile(metric_name: str) -> dict[str, Any]:
    name = str(metric_name or "").strip()
    if name in EXACT_METRIC_HINTS:
        return dict(EXACT_METRIC_HINTS[name])
    for entry in PREFIX_METRIC_HINTS:
        if name.startswith(entry["prefix"]):
            profile = dict(entry)
            profile.pop("prefix", None)
            return profile
    profile = dict(_DEFAULT_PROFILE)
    profile["displayName"] = humanize_metric_name(name)
    return profile

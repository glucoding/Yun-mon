"""指标目录的规范化与展示视图。"""

from __future__ import annotations

import re
from typing import Any

from .canonical import CANONICAL_METRIC_CATALOG, LEGACY_BUSINESS_METRIC_IDS
from .hints import infer_metric_profile


def slugify_metric_id(metric_name: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "_", str(metric_name or "").lower())
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "managed_metric"


def deep_merge(defaults: Any, data: Any) -> Any:
    """以 defaults 为骨架,把 data 中存在的字段合并进去。"""
    if isinstance(defaults, dict):
        result: dict[str, Any] = {}
        data_dict = data if isinstance(data, dict) else {}
        for key, value in defaults.items():
            result[key] = deep_merge(value, data_dict.get(key))
        for key, value in data_dict.items():
            if key not in result:
                result[key] = value
        return result
    return defaults if data is None else data


def build_metric_template(metric_name: str, category_id: str | None = None) -> dict[str, Any]:
    profile = infer_metric_profile(metric_name)
    category = category_id or profile.get("category") or "basic"
    source_type = profile.get("sourceType") or ("recording_rule" if ":" in metric_name else "raw")
    return {
        "metricId": slugify_metric_id(metric_name),
        "metricName": metric_name,
        "displayName": profile["displayName"],
        "category": category,
        "sourceType": source_type,
        "ruleMode": "external",
        "description": profile["description"],
        "expression": "",
        "derivedFrom": [],
        "unit": profile.get("unit", "short"),
        "enabled": True,
        "visualization": {
            "panelType": profile.get("panelType", "timeseries"),
            "unit": profile.get("unit", "short"),
            "decimals": 0,
            "colorMode": profile.get("colorMode", "palette-classic"),
            "showOnDashboard": False,
        },
    }


def normalize_metric_catalog(state: dict[str, Any]) -> dict[str, Any]:
    """按 canonical 模板补齐用户 state,并保留用户增量。"""
    metric_catalog = state.setdefault("metricCatalog", {})
    current_categories = metric_catalog.get("categories", []) or []
    current_items = metric_catalog.get("items", []) or []

    normalized_categories: list[dict[str, Any]] = []
    seen_category_ids: set[str] = set()
    for canonical in CANONICAL_METRIC_CATALOG["categories"]:
        normalized_categories.append(
            {
                "id": canonical["id"],
                "name": canonical["name"],
                "description": canonical["description"],
            }
        )
        seen_category_ids.add(canonical["id"])
    for category in current_categories:
        if not isinstance(category, dict):
            continue
        category_id = str(category.get("id", "")).strip()
        if not category_id or category_id in seen_category_ids:
            continue
        normalized_categories.append(
            {
                "id": category_id,
                "name": str(category.get("name", "")).strip() or category_id,
                "description": str(category.get("description", "")).strip(),
            }
        )
        seen_category_ids.add(category_id)
    metric_catalog["categories"] = normalized_categories

    current_item_map = {
        item.get("metricId"): item
        for item in current_items
        if isinstance(item, dict) and str(item.get("metricId", "")).strip()
    }
    normalized_items: list[dict[str, Any]] = []
    seen_metric_ids: set[str] = set()
    for canonical in CANONICAL_METRIC_CATALOG["items"]:
        current = current_item_map.get(canonical["metricId"], {})
        merged = deep_merge(canonical, current)
        if (
            canonical["metricId"] in LEGACY_BUSINESS_METRIC_IDS
            and str(current.get("category", "")).strip() in {"", "basic"}
        ):
            merged["category"] = "business"
        merged["displayName"] = canonical["displayName"]
        merged["description"] = canonical["description"]
        if not isinstance(merged.get("visualization"), dict):
            merged["visualization"] = dict(canonical["visualization"])
        normalized_items.append(merged)
        seen_metric_ids.add(canonical["metricId"])
    for item in current_items:
        if not isinstance(item, dict):
            continue
        metric_id = str(item.get("metricId", "")).strip()
        if not metric_id or metric_id in seen_metric_ids:
            continue
        normalized_items.append(item)
        seen_metric_ids.add(metric_id)
    metric_catalog["items"] = normalized_items
    return state


def metric_sort_key(metric: dict[str, Any], category_order: list[str]) -> tuple[int, str]:
    category = metric.get("category")
    index = category_order.index(category) if category in category_order else len(category_order)
    return index, str(metric.get("displayName", ""))


def build_metric_catalog_view(state: dict[str, Any], live_names: list[str]) -> dict[str, Any]:
    """组合用户 state 与实时指标列表,生成给前端展示的视图。"""
    live_set = set(live_names)
    catalog = state.get("metricCatalog", {})
    categories = catalog.get("categories", [])
    items_raw = catalog.get("items", [])
    category_order = [item["id"] for item in categories]
    category_lookup = {item["id"]: item for item in categories}

    items: list[dict[str, Any]] = []
    for metric in sorted(items_raw, key=lambda item: metric_sort_key(item, category_order)):
        view = dict(metric)
        view["live"] = metric["metricName"] in live_set
        view["purpose"] = metric.get("description", "")
        view["categoryName"] = category_lookup.get(
            metric.get("category"), {"name": metric.get("category", "")}
        ).get("name", metric.get("category", ""))
        items.append(view)

    catalog_names = {metric["metricName"] for metric in items_raw}
    unmanaged: list[dict[str, Any]] = []
    for name in sorted(live_set - catalog_names):
        template = build_metric_template(name)
        profile = infer_metric_profile(name)
        suggested_category = profile.get("category", "basic")
        unmanaged.append(
            {
                **template,
                "metricName": name,
                "live": True,
                "purpose": profile["description"],
                "recommendedCategory": suggested_category,
                "recommendedCategoryName": category_lookup.get(
                    suggested_category, {"name": suggested_category}
                ).get("name", suggested_category),
                "suggestedItem": template,
            }
        )

    return {
        "categories": categories,
        "items": items,
        "liveMetrics": sorted(live_set),
        "unmanagedLiveMetrics": unmanaged,
    }

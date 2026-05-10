from yunmon_control_plane.catalog.canonical import CANONICAL_METRIC_CATALOG
from yunmon_control_plane.catalog.hints import infer_metric_profile
from yunmon_control_plane.catalog.normalize import (
    build_metric_catalog_view,
    normalize_metric_catalog,
    slugify_metric_id,
)


def test_canonical_categories_unique():
    ids = [c["id"] for c in CANONICAL_METRIC_CATALOG["categories"]]
    assert len(ids) == len(set(ids)), "canonical categories 必须 id 唯一"


def test_canonical_items_unique():
    metric_ids = [item["metricId"] for item in CANONICAL_METRIC_CATALOG["items"]]
    metric_names = [item["metricName"] for item in CANONICAL_METRIC_CATALOG["items"]]
    assert len(set(metric_ids)) == len(metric_ids)
    assert len(set(metric_names)) == len(metric_names)


def test_business_category_present():
    cat_ids = {c["id"] for c in CANONICAL_METRIC_CATALOG["categories"]}
    assert "business" in cat_ids


def test_slugify_metric_id_handles_specials():
    assert slugify_metric_id("service:http_requests:rate1m") == "service_http_requests_rate1m"
    assert slugify_metric_id("a__b!!c") == "a_b_c"
    assert slugify_metric_id("") == "managed_metric"


def test_infer_metric_profile_known():
    profile = infer_metric_profile("yunmon_business_orders_processed_total")
    assert profile["category"] == "business"


def test_infer_metric_profile_prefix_fallback():
    profile = infer_metric_profile("service:custom_thing")
    assert profile["category"] == "composite"


def test_normalize_metric_catalog_keeps_user_extension():
    state = {
        "metricCatalog": {
            "categories": [
                {"id": "custom", "name": "自定义", "description": ""},
            ],
            "items": [
                {
                    "metricId": "user-defined",
                    "metricName": "user_defined_metric",
                    "displayName": "用户自定义",
                    "category": "custom",
                    "sourceType": "raw",
                    "ruleMode": "external",
                    "description": "用户自定义指标",
                    "unit": "short",
                    "enabled": True,
                    "visualization": {
                        "panelType": "stat",
                        "unit": "short",
                        "decimals": 0,
                        "colorMode": "value",
                        "showOnDashboard": False,
                    },
                }
            ],
        }
    }
    normalize_metric_catalog(state)
    cat_ids = [c["id"] for c in state["metricCatalog"]["categories"]]
    assert "basic" in cat_ids
    assert "business" in cat_ids
    assert "custom" in cat_ids
    metric_ids = [item["metricId"] for item in state["metricCatalog"]["items"]]
    assert "user-defined" in metric_ids
    assert "http_server_requests_total" in metric_ids


def test_build_metric_catalog_view_marks_live():
    state = {
        "metricCatalog": {
            "categories": [{"id": "basic", "name": "基础指标", "description": ""}],
            "items": [
                {
                    "metricId": "x",
                    "metricName": "x_metric",
                    "displayName": "X",
                    "category": "basic",
                    "sourceType": "raw",
                    "ruleMode": "external",
                    "description": "x",
                    "unit": "short",
                    "enabled": True,
                    "visualization": {
                        "panelType": "stat",
                        "unit": "short",
                        "decimals": 0,
                        "colorMode": "value",
                        "showOnDashboard": False,
                    },
                }
            ],
        }
    }
    view = build_metric_catalog_view(state, ["x_metric", "y_metric"])
    items = {item["metricName"]: item for item in view["items"]}
    assert items["x_metric"]["live"] is True
    unmanaged_names = [item["metricName"] for item in view["unmanagedLiveMetrics"]]
    assert "y_metric" in unmanaged_names

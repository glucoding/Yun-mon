"""把 desired-state 渲染为各组件配置文件的渲染器。"""

from .alertmanager import render_alertmanager
from .dashboards import render_control_center_dashboard, render_metric_dashboard, render_slo_dashboard
from .env import render_env
from .loki import render_loki
from .otel_collector import render_otel_collector
from .prometheus import render_application_targets, render_prometheus
from .promtail import render_promtail
from .rules import render_application_rules, render_metric_catalog_rules, render_slo_rules

__all__ = [
    "render_alertmanager",
    "render_application_rules",
    "render_application_targets",
    "render_control_center_dashboard",
    "render_env",
    "render_loki",
    "render_metric_catalog_rules",
    "render_metric_dashboard",
    "render_otel_collector",
    "render_prometheus",
    "render_promtail",
    "render_slo_dashboard",
    "render_slo_rules",
]

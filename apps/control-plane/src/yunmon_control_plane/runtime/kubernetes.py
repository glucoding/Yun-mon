"""KubernetesExecutor 占位实现(P3 阶段补齐)。"""

from __future__ import annotations

from typing import Any

from .executor import ReconcilePlan, ReconcileResult, ServiceState


class KubernetesExecutor:
    """占位:声明式 RuntimeExecutor 协议在 K8s 模式下的钩子。

    后续应使用 kubernetes Python SDK 调用 `apps/v1` Deployment 滚动重启,
    或者直接 helm upgrade。当前抛 NotImplementedError 让上层透出明确错误。
    """

    def list_services(self) -> list[ServiceState]:
        raise NotImplementedError("KubernetesExecutor.list_services 尚未实现,请使用 docker-compose 模式")

    def reconcile(self, plan: ReconcilePlan) -> ReconcileResult:
        raise NotImplementedError("KubernetesExecutor.reconcile 尚未实现")

    def restart_services(self, services: list[str]) -> ReconcileResult:
        raise NotImplementedError("KubernetesExecutor.restart_services 尚未实现")

    def reload_prometheus(self) -> dict[str, Any]:
        raise NotImplementedError("KubernetesExecutor.reload_prometheus 尚未实现")

    def runtime_status(self) -> dict[str, Any]:
        return {"restartStrategy": "kubernetes", "available": False, "reason": "未实现"}

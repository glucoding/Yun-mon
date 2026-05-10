# Yun-mon Helm Chart

将 Yun-mon 部署到 Kubernetes 的骨架 Chart。

> **状态**:占位骨架 (P3-6)。`KubernetesExecutor` 尚未实现完整 reconcile,先用于本地评审/测试。

## 依赖

- `kube-prometheus-stack`（运营商风格的 Prometheus + Alertmanager + Grafana）
- `loki`、`promtail`

## 使用

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm dependency update deploy/helm/yun-mon

helm install yun-mon deploy/helm/yun-mon \
  --namespace yun-mon --create-namespace \
  -f deploy/helm/yun-mon/values.yaml
```

## 与 desired-state.json 的关系

- `system / clusters / controlPlane / demoService / stackAgent` 字段语义与 control-plane 模式一致。
- 后续 control-plane 会提供工具:把 desired-state.json 自动渲染为 values.yaml,实现"声明式 → Helm 部署"。

## 待办

- 在 `KubernetesExecutor` 中实现 `helm upgrade --install` 流程
- ServiceMonitor + PodMonitor 自动渲染
- Grafana 数据源/仪表盘 ConfigMap 自动注入
- RBAC + NetworkPolicy 模板

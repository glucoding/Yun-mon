# Yun-mon

基于《信息系统运维监测项目设计方案》落地的统一监测中台。

> 当前主线版本 0.2.x 已经完成 [`docs/IMPROVEMENT_PLAN.md`](docs/IMPROVEMENT_PLAN.md) 中的 P0–P3 工程化改造,所有后续修改请先阅读这份"宪章"。

## 监测组件

- `Prometheus + Alertmanager + Grafana + Loki + Promtail + cAdvisor` 监测栈
- 可选 `OpenTelemetry Collector`(`compose --profile otel`)
- 一个接入 `Spring Boot Actuator + Micrometer + Prometheus` 的示例业务服务
- Grafana 数据源 / 控制中心 / 指标目录 / SLO 概览仪表盘
- `control-plane`(FastAPI + Pydantic v2 + prometheus_client + docker SDK)
- `stack-agent`(宿主机受控代理,触发 `docker compose up -d --build`)

## 目录结构

- `compose.yaml`:整套监测平台的编排入口
- `infra/`:Prometheus、Alertmanager、Loki、Promtail、Grafana、OTel 配置(由 control-plane 自动渲染)
- `infra/control-plane/desired-state.json`:统一参数模型(单一事实源)
- `infra/control-plane/snapshots/`:配置变更审计快照(P2-1)
- `apps/demo-service/`:被监测的示例 Spring Boot 服务,含 MockMvc 集成测试
- `apps/control-plane/`:控制面 Python 项目(模块化拆分,见 [README](apps/control-plane/README.md))
- `apps/control-plane/web/`:Vue 3 + TypeScript + Vite 前端工程
- `apps/stack-agent/`:宿主机执行代理
- `deploy/helm/yun-mon/`:Kubernetes 部署 Helm Chart 骨架(P3-6)
- `.github/workflows/`:GitHub Actions CI / Release(P3-5)
- `docs/IMPROVEMENT_PLAN.md`:整体改造路线
- `docs/stack-agent.md`:stack-agent 设计与启停说明
- `docs/CHANGELOG.md`:变更记录

## 快速开始

```powershell
# 1. 准备环境文件(token 留空,首次启动 control-plane 会自动生成)
copy .env.example .env

# 2. 拉镜像
powershell -ExecutionPolicy Bypass -File .\scripts\pull-components.ps1

# 3. 启动监测栈
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1

# 4.(可选) 启动宿主机 stack-agent,以解锁端口/镜像类闭环
powershell -ExecutionPolicy Bypass -File .\scripts\start-stack-agent.ps1
```

## 默认访问入口

- Grafana:`http://127.0.0.1:13000`
- Prometheus:`http://127.0.0.1:9090`
- Alertmanager:`http://127.0.0.1:9093`
- Loki:`http://127.0.0.1:3100`
- cAdvisor:`http://127.0.0.1:8081`
- Demo Service:`http://127.0.0.1:18080`
- Control Plane:`http://127.0.0.1:18090`(`/docs` 自动生成 OpenAPI)
- OTel Collector(profile=otel):`http://127.0.0.1:4318`

## 控制台能力

控制台 0.2.x 提供:

1. 基于 desired-state 的声明式参数管理(Pydantic v2 校验)
2. 渲染 `.env`、Prometheus / Alertmanager / Loki / Promtail / Grafana / OTel Collector 配置
3. 应用自动发现:基于 Docker label 收集纳管目标
4. 指标目录 + Live 指标对比 + 从 Prometheus metadata 同步元数据
5. 配置变更审计(P2-1):RFC6902 JSON Patch + 操作者 + 时间,默认保留 50 份/90 天
6. 一键回滚到任意历史快照(P2-2)
7. 任务化 reconcile(P2-3):`/api/v1/system/restart` 返回 `jobId`,可经 SSE 流式查询进度
8. RuntimeExecutor 抽象(P2-4):DockerCompose 实现 / Kubernetes 占位
9. AlertReceiver 抽象(P2-5):Webhook / Email / 企业微信 / 钉钉 / 飞书
10. 自身 OpenTelemetry 自动埋点(P2-7,需配置 `CONTROL_PLANE_OTEL_ENDPOINT`)
11. 本地账号 + JWT RBAC(P3-1,默认关闭,可通过 `CONTROL_PLANE_AUTH_ENABLED=true` 启用)
12. 审计日志(P3-2):每个写动作落 `infra/control-plane/audit/audit.log.jsonl`
13. 多集群一等公民(P3-3 起步):`clusters` 字段已纳入 schema,前端提供切换器
14. SLO + multi-window multi-burn-rate 告警模板(P3-4)
15. desired-state schema 版本化迁移(P3-7,当前 v1 → v2)

## 边界与后续

- KubernetesExecutor 仅占位,完整实现见 [`docs/IMPROVEMENT_PLAN.md`](docs/IMPROVEMENT_PLAN.md) `P3-6`
- 跨集群联邦/Thanos 在路线图中
- 接收器/通知策略前端 panel 仍需细化
- OAuth/OIDC、SSO 集成在 P3 后续阶段补齐

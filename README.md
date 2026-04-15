# Yun-mon

基于设计方案落地的运维监测平台基础框架，当前版本包含：

- `Prometheus + Alertmanager + Grafana + Loki + Promtail + cAdvisor` 监控栈
- `docker-stats-exporter` 用于 Docker Desktop 下的容器服务资源指标补采
- 一个接入 `Spring Boot Actuator + Micrometer + Prometheus` 的示例服务
- 预置的告警规则、Grafana 数据源与基础仪表盘
- PowerShell 启动、停止、拉取组件、构建示例服务脚本

## 目录结构

- `compose.yaml`：整体编排入口
- `infra/`：监控组件配置、规则、仪表盘 provisioning
- `apps/demo-service/`：被监控的 Spring Boot 示例服务
- `docs/system-plan.md`：按设计方案整理的系统规划与落地路线
- `scripts/`：运维与启动脚本

## 快速开始

1. 复制 `.env.example` 为 `.env`，按需调整 Grafana 账号密码。
2. 运行 `powershell -ExecutionPolicy Bypass -File .\scripts\pull-components.ps1`
3. 运行 `powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1`

启动后默认入口：

- Grafana: `http://localhost:13000`
- Prometheus: `http://localhost:9090`
- Alertmanager: `http://localhost:9093`
- Loki: `http://localhost:3100`
- Demo Service: `http://localhost:18080`
- Demo Metrics: `http://localhost:18080/actuator/prometheus`

如果本机端口有冲突，可在 `.env` 中覆盖：

- `GRAFANA_HOST_PORT`
- `DEMO_SERVICE_HOST_PORT`

## 当前落地范围

这个基础框架优先实现了设计方案中的五层骨架：

- 被监控对象层：`demo-service`
- 数据采集层：Prometheus、Promtail、cAdvisor
- 数据存储与处理层：Prometheus TSDB、Loki
- 告警管理层：Alertmanager
- 可视化与分析层：Grafana

## 后续建议

- 接入真实业务系统并统一采集标签规范
- 引入 OpenTelemetry Collector 与 Trace 后端
- 将 Alertmanager 接入企业微信、邮件或 Webhook
- 为更多服务补充业务指标和 SLO 告警

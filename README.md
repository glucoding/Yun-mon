# Yun-mon

Yun-mon 是基于《信息系统运维监测项目设计方案》落地的第一版监测平台基础框架，当前仓库已经包含：

- `Prometheus + Alertmanager + Grafana + Loki + Promtail + cAdvisor` 监测栈
- `docker-stats-exporter`，用于补充 Docker Desktop / Docker 环境下的容器资源指标
- 一个接入 `Spring Boot Actuator + Micrometer + Prometheus` 的示例业务服务
- Grafana 数据源、基础仪表盘和容器总览仪表盘
- 控制面服务 `control-plane`，用于统一管理参数、生成配置、查看服务状态和执行运行时重载
- PowerShell 启动、停止、拉取组件脚本

## 目录结构

- `compose.yaml`：整套监测平台的编排入口
- `infra/`：Prometheus、Alertmanager、Loki、Promtail、Grafana 等基础配置
- `infra/control-plane/desired-state.json`：统一参数模型的单一事实源
- `apps/demo-service/`：被监测的示例 Spring Boot 服务
- `apps/control-plane/`：统一控制台后端与前端
- `apps/stack-agent/`：宿主机执行代理，用于触发真正的 `docker compose up -d --build`
- `docs/system-plan.md`：系统规划与演进方向
- `docs/stack-agent.md`：stack-agent 设计与启停说明
- `scripts/`：运维与启动脚本

## 快速开始

1. 复制 `.env.example` 为 `.env`
2. 按需修改默认端口和 Grafana 管理员账号
3. 运行 `powershell -ExecutionPolicy Bypass -File .\scripts\pull-components.ps1`
4. 运行 `powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1`

## 默认访问入口

- Grafana：`http://127.0.0.1:13000`
- Prometheus：`http://127.0.0.1:9090`
- Alertmanager：`http://127.0.0.1:9093`
- Loki：`http://127.0.0.1:3100`
- Demo Service：`http://127.0.0.1:18080`
- Control Plane：`http://127.0.0.1:18090`

## 统一控制台能力

当前 `control-plane` 已经提供以下能力：

- 基于 `infra/control-plane/desired-state.json` 维护统一参数模型
- 统一生成 `.env`、Prometheus、Alertmanager、Loki、Promtail 和 Grafana 控制台入口配置
- 自动发现当前 Docker 环境中的应用，并按应用维度维护监管配置
- 为每个应用统一配置是否纳管、采集端口、指标路径、显示名称与环境标签
- 热重载 Prometheus 配置
- 查询当前监测栈服务运行状态
- 在 `stack-agent` 可用时，通过宿主机执行代理对监测栈执行真正的 `docker compose up -d --build`
- 在 `stack-agent` 不可用时，回退到 Docker API 对当前运行容器执行受控重启

当前实现边界：

- 当 `stack-agent` 已启动并可达时，端口、环境变量与镜像构建类变更也可从控制台闭环
- 当 `stack-agent` 未启动时，控制台会自动回退到容器级重启，此时宿主机端口、环境变量与镜像构建类变更仍需宿主机手动执行 `docker compose up -d --build`
- 当前“应用自动发现”优先面向 Docker 运行中的容器；若应用没有暴露可抓取的指标端口，仍需要在控制台补充采集端口后才能真正纳管

Grafana 中也会 provision 一个 `Yun-mon Control Center` 仪表盘，作为统一控制台入口。

## 启动宿主机 Stack Agent

Windows：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-stack-agent.ps1
```

Ubuntu：

```bash
./scripts/start-stack-agent.sh
```

更多说明见 [stack-agent.md](/E:/Yun-mon/docs/stack-agent.md)。

## 当前边界

这一版仍然是通用监测产品的基础骨架，不是最终形态。当前重点是：

- 先把 Docker 模式的单节点基础能力跑通
- 建立统一参数模型和控制面雏形
- 为后续 Ubuntu 云节点部署和 Kubernetes 模式扩展预留结构

后续建议重点推进：

- 控制面参数模型继续抽象为 Docker / Kubernetes 双运行模式
- 引入权限控制、配置审计和回滚记录
- 将告警接收器、通知策略和多环境模板继续产品化
- 接入 OpenTelemetry Collector，补齐 Trace 与统一语义模型

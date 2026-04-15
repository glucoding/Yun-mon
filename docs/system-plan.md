# 信息系统运维监测平台规划

## 1. 建设目标

根据《信息系统运维监测项目设计方案》，本项目的基础框架按以下目标落地：

- 建立面向容器化应用的统一监测底座
- 实现指标、日志、告警、可视化四类能力的最小闭环
- 为后续接入真实业务系统预留统一标签、规则、仪表盘和部署规范
- 采用容器化编排，降低安装、迁移和扩展成本

## 2. 本次落地范围

### 2.1 被监控对象层

- `demo-service` 作为示例业务服务
- 暴露 `/actuator/prometheus`、`/actuator/health` 指标与健康接口
- 输出带 `traceId`、`spanId` 的结构化日志样式

### 2.2 数据采集层

- `Prometheus` 负责采集应用指标与容器指标
- `cAdvisor` 负责采集容器资源指标
- `Promtail` 负责采集应用日志并推送到 `Loki`
- 通过 `docker_sd_configs` 实现容器级自动发现

### 2.3 数据存储与处理层

- `Prometheus TSDB` 存储时序指标
- `Loki` 存储与检索日志
- `Recording Rules` 预聚合核心 Golden Signals 指标

### 2.4 告警管理层

- `Alertmanager` 提供分组、抑制与后续通知扩展点
- 初始阶段内置实例不可达、高错误率、高延迟、队列积压等规则

### 2.5 可视化与分析层

- `Grafana` 统一接入 Prometheus、Loki、Alertmanager
- 预置三类仪表盘：
  - API Golden Signals
  - 容器资源监控
  - 应用日志检索

## 3. 技术架构映射

设计方案中的关键技术点与当前骨架映射如下：

- Prometheus：指标采集、规则计算、告警触发
- Alertmanager：告警分组与抑制
- Loki：轻量日志聚合
- Promtail：日志采集代理
- Grafana：统一观测门户
- cAdvisor：容器资源指标
- Spring Boot + Micrometer：业务与应用层指标输出

## 4. 指标体系规划

### 4.1 基础资源指标

- CPU 使用率与节流
- 内存工作集与异常分配
- 网络收发吞吐
- 文件系统读写吞吐

### 4.2 应用层指标

- HTTP 请求速率
- HTTP 5xx 错误率
- P95 延迟
- JVM 内存与线程
- 自定义业务队列深度
- 自定义业务处理计数与耗时

### 4.3 日志规划

- 应用日志统一输出到共享日志卷
- 日志中保留 `traceId`、`spanId` 字段
- 后续可扩展为 JSON 日志与 Trace 链路联动

## 5. 建议的下一阶段任务

### 第一阶段

- 将真实业务服务按同样规范接入 compose 网络
- 为每个服务定义统一标签：`service_name`、`monitoring_enabled`

### 第二阶段

- 引入 OpenTelemetry Collector
- 对接 Trace 后端并在 Grafana 中实现 Trace 跳转
- 增加数据库、中间件、主机节点采集

### 第三阶段

- 建立 SLO/SLA 仪表盘
- 对接企业微信、短信、邮件等告警通道
- 将配置纳入 CI/CD 和环境分层管理


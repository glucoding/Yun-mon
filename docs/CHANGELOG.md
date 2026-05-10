# Changelog

## 0.2.0 — Unreleased

### P0:清算技术债

- `P0-1` `CANONICAL_METRIC_CATALOG` 统一收口到 `apps/control-plane/src/yunmon_control_plane/catalog/canonical.py`,删除原 `server.py` 中重复定义。
- `P0-2` 新代码全部使用 UTF-8 中文,`\u` 转义彻底淘汰。
- `P0-3` 经核查 `.env` / `logs/` / `test-results/` / `target/` 已被 `.gitignore` 拦截,仅余 `.env.example` 跟踪;`.env.example` 已清空 token 默认值。
- `P0-4` `stack-agent` 默认绑定 `127.0.0.1`,启动脚本默认值同步,文档强调跨主机使用条件。
- `P0-5` `STACK_AGENT_SHARED_TOKEN` 由 control-plane 首次启动 `secrets.token_urlsafe(32)` 自动生成;启动脚本要求 token 长度 ≥16 否则拒绝启动。
- `P0-6` Docker 自动发现失败抛错,`applications-targets.json` 不再被静默清空,新增 `control_plane_discovery_failures_total` 指标。

### P1:工程化基础

- `P1-1` 用 FastAPI 项目结构替换 2360 行的 `server.py`,新模块见 `apps/control-plane/src/yunmon_control_plane/`。
- `P1-2` 引入 FastAPI + Pydantic v2 + Pydantic Settings,自动生成 OpenAPI(`/docs`)。
- `P1-3` 全部 YAML 渲染改用 `PyYAML`,删除手写转义。
- `P1-4` `/metrics` 改用 `prometheus_client`。
- `P1-5` Docker 客户端改用 `docker` 官方 SDK,`docker_client.py` 替代裸 socket。
- `P1-6` `stack-agent` 客户端改用 `httpx`。
- `P1-7` 删除 `infra/docker-stats-exporter/`(与 cAdvisor 重叠);告警规则改写为 cAdvisor 等价表达式。
- `P1-8` 新增 `apps/control-plane/tests/unit/` 共 43 条 pytest 用例,行覆盖率 74%(超过 70% 目标)。
- `P1-9` `apps/demo-service/src/test/.../SimulationControllerIT.java` 增加 MockMvc 集成测试,顺手修复 `simulate` 方法中 `queueDepth` 双重扣减的逻辑 bug。
- `P1-10` 控制台前端切到 Vue 3 + TypeScript + Vite + Pinia + Vue Router,目录 `apps/control-plane/web/`,旧 `static/` 仍作为 fallback。

### P2:平台化能力

- `P2-1` 配置变更审计:`infra/control-plane/snapshots/`,RFC6902 JSON Patch + 操作者 + 时间,默认保留 50 份 / 90 天。
- `P2-2` 一键回滚:`POST /api/v1/audit/snapshots/{id}/rollback`,前端 Audit panel 直接触发。
- `P2-3` reconcile 任务化:`POST /api/v1/system/restart` 返回 `jobId`,新增 `/api/v1/jobs/{id}` 与 `/jobs/{id}/stream` (SSE)。
- `P2-4` `RuntimeExecutor` 抽象:`DockerComposeExecutor` 实现 + `KubernetesExecutor` 占位。
- `P2-5` `AlertReceiver` 抽象:driver 覆盖 webhook / email / wework / dingtalk / feishu;Alertmanager 配置自动渲染。
- `P2-6` `compose.yaml` 新增 `otel-collector` 服务(profile=otel),配置由 control-plane 渲染。
- `P2-7` 在 `CONTROL_PLANE_OTEL_ENDPOINT` 配置时自动启用 `opentelemetry-instrumentation-fastapi`。
- `P2-8` 新增 `/api/v1/metrics/catalog/sync` 接口拉取 Prometheus `/api/v1/metadata`,前端"指标目录" panel 提供同步按钮。

### P3:产品化与多场景

- `P3-1` 本地账号 + JWT RBAC(`bcrypt` + `PyJWT`),默认关闭,通过 `CONTROL_PLANE_AUTH_ENABLED=true` 启用。
- `P3-2` 审计日志中间件:每次写操作落 `infra/control-plane/audit/audit.log.jsonl`,包含 actor / IP / UA / 状态码 / 错误类型 / 延迟。
- `P3-3` `clusters` 进入 desired-state 并由 v1→v2 迁移自动补齐;前端提供集群切换器。
- `P3-4` 新增 `slos` 字段、`slo-rules.yml`(multi-window multi-burn-rate)与 `slo-overview.json` 仪表盘。
- `P3-5` 新增 `.github/workflows/ci.yml`(Python + Java + Vue 三套 lint/test/build)与 `release.yml`(GHCR 镜像推送)。
- `P3-6` 新增 `deploy/helm/yun-mon/` Helm Chart 骨架(依赖 `kube-prometheus-stack` / `loki` / `promtail`)。
- `P3-7` 新增 `state/migrations/` 版本化迁移框架,`v1_to_v2.py` 实现首条迁移链路。

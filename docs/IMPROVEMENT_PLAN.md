# Yun-mon 改造路线（P0–P3）

> 本文档是 Yun-mon 项目从「脚手架」演进到「可投产监测中台」的完整改造蓝图。所有后续的 AI/人类 agent 在改代码前都应先读这份文档，并在落地完成后回写 `状态/验收` 字段。

## 0. 总体原则

1. **声明式优先**：所有平台行为都应来自 `desired-state.json`（或其继任者），不要把可配置参数硬编码到具体组件配置。
2. **单一职责**：单文件 ≤ 500 行，单模块只承担一个职责。任何接近这一边界的文件必须立刻拆分。
3. **利用生态**：能用 PyPI/Maven 标准库解决的，绝不自己手写（HTTP server、YAML、JSON-Schema、Prometheus exposition、Docker socket、OAuth/JWT 等）。
4. **可测试**：所有渲染/校验/规范化等纯函数必须有单元测试；HTTP 层有契约/集成测试。
5. **安全默认**：默认监听 `127.0.0.1`、默认密钥随机生成、敏感字段不入库不入仓库。
6. **可观测自身**：control-plane / stack-agent 自身的关键操作必须可观测（指标 + 日志 + Trace）。
7. **可回滚**：任何一次配置下发都要有 diff、有版本号、可一键回到任意历史快照。
8. **响应中文**：所有面向最终用户的文案保持中文；代码注释只解释非显然意图，不做白描。

## 1. 路线总览

| 优先级 | 主题            | 价值                       | 估时（人日）|
| ------ | --------------- | -------------------------- | ----------- |
| P0     | 清算技术债       | 消除已知 bug / 安全裸奔     | 1           |
| P1     | 工程化基础       | 拆分、引入框架、补测试      | 5–8         |
| P2     | 平台化能力       | 审计/任务化/抽象层/OTel     | 8–12        |
| P3     | 产品化与多场景   | RBAC/多集群/SLO/Helm/CI     | 15+         |

---

## 2. P0 — 清算技术债（必须立刻完成）

### P0-1 删除重复的 `CANONICAL_METRIC_CATALOG`

**现状**：`apps/control-plane/server.py` 里 `CANONICAL_METRIC_CATALOG` 被定义两次（约 342 行 与 661 行），后者覆盖前者，且两份内容不一致（第二份多了 `business` 分类）。

**做法**：保留第二份（含 `business` 分类的"完整版"），删掉第一份；同时把 `DEFAULT_STATE["metricCatalog"] = ...` 重新赋值的语句保留一处。

**验收**：`grep -c "CANONICAL_METRIC_CATALOG = {" server.py` 应为 1。

---

### P0-2 把 `\u` 转义中文还原为正常 UTF-8

**现状**：`server.py` 第 530 行起的 `EXACT_METRIC_HINTS`、`PREFIX_METRIC_HINTS`、第 999 行 description 等大段中文用 `\u4e0a\u6587` 写法，可读性极差。

**做法**：用脚本一次性还原（`json.loads('"...."')` 即可解码）。后续禁止再以转义形式写中文。

**验收**：源文件用任何编辑器打开，中文显示正常；`rg "\\\\u[0-9a-f]{4}" apps/control-plane/server.py` 无业务字段命中。

---

### P0-3 真正从 git 中移除被 ignore 但仍被跟踪的文件

**现状**：`.gitignore` 已写明 `.env`、`logs/`、`test-results/`、`target/` 等，但仓库里这些文件仍处于 tracked 状态（`Length=854` 的 `.env` 即在仓库内）。

**做法**：

```bash
git rm --cached -r .env logs test-results .codex-temp
git rm --cached apps/demo-service/target -r 2>/dev/null || true
git commit -m "chore: stop tracking generated/runtime files"
```

并把当前 `.env` 中真实使用的 token / 密码视为已经泄露，全部轮换。

**验收**：`git ls-files | rg "^(\.env|logs/|test-results/|.*/target/)"` 无输出。

---

### P0-4 stack-agent 默认绑定 127.0.0.1

**现状**：`apps/stack-agent/agent.py` 中 `HTTP_HOST` 默认 `0.0.0.0`，`scripts/start-stack-agent.ps1` 也写的是 `0.0.0.0`。

**做法**：
- 默认值改为 `127.0.0.1`
- control-plane 用 `host.docker.internal:19090` 走 Docker 的 host-gateway 仍可访问
- 文档增加一节"什么时候才允许绑 0.0.0.0"，并要求叠加 mTLS / 反向代理

**验收**：`agent.py` 默认 host 为 `127.0.0.1`，启动脚本不显式覆盖；`docs/stack-agent.md` 含安全章节。

---

### P0-5 移除已知默认 token

**现状**：`STACK_AGENT_SHARED_TOKEN=yunmon-local-agent-token` 同时出现在 `.env`、`.env.example`、`DEFAULT_STATE["stackAgent"]["sharedToken"]`。

**做法**：
- `DEFAULT_STATE` 里把 token 字段设为空，并在 `validate_state` 中要求长度 ≥ 32 字符
- 首次启动若发现为空，调 `secrets.token_urlsafe(32)` 自动生成并写回 `desired-state.json`
- `.env.example` 的 token 字段留空，加注释说明会自动生成

**验收**：删掉本地 `.env` 后启动，新 `.env` 里的 token 是高熵随机字符串。

---

### P0-6 Docker 失败不再静默清空 SD

**现状**：`server.py::discover_applications` 中 `except Exception: containers = []`，最终生成空 `applications-targets.json`，Prometheus 静默清空所有应用抓取目标。

**做法**：
- `discover_applications` 失败时抛出异常
- `render_application_targets` 在拿不到容器列表时**保留上一次 SD 文件不动**，并把错误写入控制台错误日志 + 一个 gauge 指标 `control_plane_discovery_failures_total`
- 仅在用户显式调用 `apply` 且能成功列出容器时才覆写 SD 文件

**验收**：临时停掉 Docker，触发一次 reconcile，`applications-targets.json` 不被改动，`/api/v1/system/runtime` 返回 `discoveryError` 字段。

---

## 3. P1 — 工程化基础

### P1-1 拆分 `server.py` 到模块

**目标结构**：

```
apps/control-plane/
  pyproject.toml
  Dockerfile
  src/yunmon_control_plane/
    __init__.py
    config.py             # 环境变量与全局配置
    state/
      __init__.py
      defaults.py         # DEFAULT_STATE
      schema.py           # Pydantic 模型 + JSONSchema
      store.py            # load/save/normalize
      migrations/         # v1 → v2 迁移函数（占位）
    catalog/
      __init__.py
      canonical.py        # CANONICAL_METRIC_CATALOG
      hints.py            # EXACT_METRIC_HINTS / PREFIX_METRIC_HINTS
      sync.py             # 从 Prometheus metadata 回填
    renderers/
      env.py
      prometheus.py
      alertmanager.py
      loki.py
      promtail.py
      dashboards.py
      rules.py
    clients/
      docker_client.py    # 封装 docker SDK
      stack_agent.py      # 用 httpx 实现
      prometheus.py       # 封装 reload/metadata
    runtime/
      executor.py         # RuntimeExecutor 抽象基类
      compose.py          # DockerComposeExecutor
      kubernetes.py       # 占位
    audit/
      __init__.py
      log.py              # 审计日志
      snapshot.py         # 配置快照与回滚
    jobs/
      __init__.py
      manager.py          # 任务队列与 job-id 管理
    api/
      __init__.py
      app.py              # FastAPI 应用工厂
      v1/
        config.py
        system.py
        applications.py
        metrics.py
        auth.py           # P3 RBAC
        jobs.py
    metrics.py            # prometheus_client 指标定义
    main.py               # uvicorn 入口
  tests/
    unit/
    integration/
```

每个文件保持 ≤ 500 行；`server.py` 完成迁移后删除。

---

### P1-2 切到 FastAPI + Pydantic v2

**依赖**：

```
fastapi>=0.115
uvicorn[standard]>=0.32
pydantic>=2.9
pydantic-settings>=2.5
```

**要点**：
- 用 Pydantic 模型替代 `validate_state` 手写校验
- 路由按版本前缀（`/api/v1`）分组
- 所有响应使用 `BaseModel`，自动生成 OpenAPI（`/docs` / `/redoc`）
- 静态前端用 `StaticFiles` 挂载

---

### P1-3 用 PyYAML 渲染 YAML

**依赖**：`PyYAML>=6.0`

**做法**：
- `renderers/prometheus.py` 等改为先组装 dict，最后 `yaml.safe_dump(..., sort_keys=False, allow_unicode=True)`
- 删除 `yaml_scalar` 等手写转义函数

---

### P1-4 用 `prometheus_client` 暴露 /metrics

**依赖**：`prometheus-client>=0.21`

**做法**：
- 用 `Counter` / `Gauge` / `Histogram` 重新声明所有指标
- `/metrics` 路由直接返回 `generate_latest()`

---

### P1-5 用 Docker 官方 SDK

**依赖**：`docker>=7.1`

**做法**：
- `clients/docker_client.py` 用 `docker.DockerClient(base_url=...)` 重写
- 删掉手写的 chunked 解析与 socket 拼接

---

### P1-6 用 httpx 实现 stack-agent client

**依赖**：`httpx>=0.27`

**做法**：用 `httpx.Client` 替换 `urllib.request`，并支持 `verify=` / `cert=` 字段为 P2 mTLS 做准备。

---

### P1-7 移除 docker-stats-exporter

**结论**：与 cAdvisor 严重重叠，删除。

**做法**：
- 从 `compose.yaml` 删除 service
- 把 `application-rules.yml` 中依赖 `docker_container_*` 指标的告警改写到等价的 cAdvisor 指标（如 `container_memory_working_set_bytes`、`rate(container_cpu_usage_seconds_total[5m])`）
- `infra/docker-stats-exporter/` 整目录删除
- `desired-state.json` 中 `dockerStatsExporter` 字段保留一个版本作为 deprecated 警告，下个 schema 版本里彻底移除

---

### P1-8 控制面单测

**依赖**：`pytest`、`pytest-asyncio`、`httpx`（用于 TestClient）

**最少要覆盖**：
- `renderers.env.render_env` 各分支（含特殊字符）
- `renderers.prometheus.render_prometheus`
- `renderers.alertmanager.render_alertmanager`
- `renderers.loki.render_loki`
- `renderers.promtail.render_promtail`
- `renderers.rules.render_metric_catalog_rules`
- `state.schema.YunmonState` 各类非法输入
- `catalog.normalize.normalize_metric_catalog` 多种历史 state 兼容
- `clients.docker_client` 用 mock 验证查询参数
- API：`GET /api/v1/config`、`PUT /api/v1/config`、`POST /api/v1/system/restart` 各 1 条 happy path + 1 条错误

**目标**：行覆盖率 ≥ 70%。

---

### P1-9 demo-service 集成测试

**做法**：在 `apps/demo-service/src/test/java` 下加 `SimulationControllerIT`：

- `MockMvc` 验证 `/api/demo/hello`、`/healthz`、`/simulate`（成功 + 失败）
- 验证 `/actuator/prometheus` 暴露 `yunmon_business_orders_processed_total` 等指标

---

### P1-10 前端用 Vue 3 + TS + Vite 重写

**结构**：

```
apps/control-plane/web/
  package.json
  vite.config.ts
  index.html
  src/
    main.ts
    App.vue
    api/                  # 自动生成 OpenAPI client
    stores/               # Pinia
    components/
      common/
      panels/
        OverviewPanel.vue
        SystemPanel.vue
        PortsPanel.vue
        GrafanaPanel.vue
        PrometheusPanel.vue
        AlertmanagerPanel.vue
        LokiPanel.vue
        PromtailPanel.vue
        StackAgentPanel.vue
        ApplicationDefaultsPanel.vue
        ApplicationsPanel.vue
        MetricOverviewPanel.vue
        MetricCatalogPanel.vue
        MetricVisualizationPanel.vue
    composables/
    styles/
```

- 使用现有 `styles.css` 视觉语言（保留色板与布局），用 CSS 模块或 BEM 维护
- Pinia store 单一数据源；表单走"草稿态"+"已下发态"两份
- 构建产物输出到 `dist/`，control-plane 通过 FastAPI `StaticFiles` 服务

---

## 4. P2 — 平台化能力

### P2-1 配置变更审计

**模型**：

```python
class ConfigSnapshot(BaseModel):
    snapshotId: str          # ULID
    schemaVersion: int
    appliedAt: datetime
    actor: str               # 来自 JWT (P3)；P2 阶段先填 ip:ua
    diff: dict               # 与上一份的 JSON Patch (RFC 6902)
    state: dict              # 完整快照
```

**存储**：`infra/control-plane/snapshots/` 下按时间排序的 JSONL；保留最近 50 份 + 最近 90 天，可配置。

---

### P2-2 一键回滚

- `GET /api/v1/audit/snapshots` 列出快照
- `POST /api/v1/audit/snapshots/{id}/rollback` 回滚到指定快照（仍走 `apply_state` 全链路）
- 前端"运行总览"面板增加"最近变更"卡片，可一键 diff & 回滚

---

### P2-3 reconcile 任务化

- 控制面收到 `restart` 请求时，立刻返回 `{ jobId }`
- 实际工作放到后台线程池
- `GET /api/v1/jobs/{id}` 返回 `status / progress / log_tail`
- 前端用 SSE (`text/event-stream`) 流式订阅
- stack-agent 同步改为支持长连接 SSE 输出 docker compose 进度

---

### P2-4 RuntimeExecutor 抽象

```python
class RuntimeExecutor(Protocol):
    def list_services(self) -> list[ServiceState]: ...
    def reconcile(self, plan: ReconcilePlan) -> ReconcileResult: ...
    def restart(self, services: list[str]) -> ReconcileResult: ...
    def reload_prometheus(self) -> None: ...

class DockerComposeExecutor(RuntimeExecutor): ...
class KubernetesExecutor(RuntimeExecutor):
    """占位实现，抛 NotImplementedError；P3 阶段补齐"""
```

`server.py` 中所有"调用 docker / stack-agent"的代码都通过 `RuntimeExecutor` 间接调用。

---

### P2-5 AlertReceiver 抽象

- desired-state 增加 `alertReceivers: list[AlertReceiver]`
- `AlertReceiver` 子类：`WebhookReceiver` / `EmailReceiver` / `WeworkReceiver` / `DingTalkReceiver` / `FeishuReceiver`
- 渲染 `alertmanager.yml` 时根据 `kind` 选择 receiver 模板
- 前端"告警接收器"面板支持新增/编辑/测试发送

---

### P2-6 OpenTelemetry Collector 接入

- `compose.yaml` 增加 `otel-collector` 服务（`otel/opentelemetry-collector-contrib`）
- `demo-service` `application.yml` 增加 `management.otlp.tracing.endpoint`
- `control-plane` 增加 OTel SDK
- 渲染 collector 配置文件 `infra/otel-collector/config.yaml`，从 desired-state 生成
- 前端"平台配置 → OpenTelemetry"新增面板

---

### P2-7 control-plane 自身 Trace

- 用 `opentelemetry-instrumentation-fastapi` 自动埋点
- 关键操作 `apply_state` / `restart_stack` / `reload_prometheus` 手工 span，attributes 含 `actor`、`diffSummary`、`durationMs`

---

### P2-8 指标目录自动同步

- 用 Prometheus `/api/v1/metadata` 批量拉取 HELP/TYPE
- 删除 `EXACT_METRIC_HINTS` / `PREFIX_METRIC_HINTS` 中的中文 hint，仅保留"中文释义"作为人工补充字段
- 控制台允许将"未纳管 live metric"一键纳入指定分类

---

## 5. P3 — 产品化与多场景

### P3-1 RBAC（本地账号 + JWT，预留 OIDC）

**模型**：

```python
class User(BaseModel):
    username: str
    passwordHash: str       # bcrypt
    roles: list[str]
    createdAt: datetime
    enabled: bool

class Role(BaseModel):
    name: str
    permissions: list[str]  # e.g. config:read, config:write, system:restart, audit:read
```

**接口**：
- `POST /api/v1/auth/login` 返回 access token (15min) + refresh token (7d)
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- 所有 `/api/v1/*` 路由通过 FastAPI 依赖注入校验权限

**预留 OIDC**：`AUTH_PROVIDER=oidc` 时切换到 `authlib` + 标准授权码流程。

---

### P3-2 审计日志

- 每次写操作记录：`actor / ip / ua / route / payloadHash / status / latencyMs / errorType`
- 落 `infra/control-plane/audit/audit.log.jsonl`，并通过 Promtail 采到 Loki
- 控制台"运行总览"提供查询入口（按时间/操作者/动作）

---

### P3-3 多集群一等公民

- `desired-state` 顶层引入 `clusters: list[Cluster]`
- 每个 `Cluster` 含独立的 `prometheus / loki / alertmanager / applications`
- Prometheus 联邦或 Thanos sidecar 二选一（先做联邦，文档化 Thanos 升级路径）
- Grafana 数据源按 cluster 分组
- 前端顶部增加"集群切换器"

---

### P3-4 SLO 仪表盘 + Multi-burn-rate 告警

- desired-state 新增 `slos: list[SLO]`，每个含 `service / objective / window`
- 自动渲染 multi-window multi-burn-rate 告警规则（参考 Google SRE Workbook：1h/5m, 6h/30m）
- 自动渲染 SLO Grafana 仪表盘（错误预算燃尽率 + 剩余预算 + 历史 SLI）

---

### P3-5 GitHub Actions CI

`.github/workflows/`:
- `ci.yml`：lint + pytest（control-plane）+ Maven test（demo-service）+ docker buildx 构建
- `release.yml`：tag 时构建并 push 镜像到 GHCR；附加 SBOM
- `web.yml`：前端 `pnpm test` + `pnpm build` + 上传 dist artifact

---

### P3-6 Helm Chart 骨架

`deploy/helm/yun-mon/`:
- `Chart.yaml` / `values.yaml` / `templates/`
- 内置 sub-charts：`kube-prometheus-stack`、`loki`、`promtail`、`grafana`
- `values.yaml` 默认值与 desired-state.json 一一对应
- 文档说明如何用 control-plane 把 Compose 模式 desired-state 自动转换为 Helm values

---

### P3-7 Schema 版本化迁移

- `state/migrations/` 下每个文件实现 `def upgrade(state: dict) -> dict`
- 加载 `desired-state.json` 时按 `metadata.schemaVersion` 顺序执行所有 upgrade
- 每次升级前自动写一份"升级前快照"到审计存储
- 提供 CLI：`python -m yunmon_control_plane.tools.migrate --check` / `--apply`

---

## 6. 验收清单

每条 P0–P3 任务完成时，必须满足：

- [ ] 代码通过 `ruff` / `black` / `mypy --strict` / `eslint` 检查
- [ ] 受影响模块测试覆盖率不下降
- [ ] `docker compose up -d --build` 启动后能访问 Grafana、Prometheus、Control Plane 主页
- [ ] 在 `docs/CHANGELOG.md` 增加一条对应变更记录
- [ ] 在本文档对应小节末尾标注 `状态: ✅ done / 🟡 partial / ⏳ pending`、`完成日期`、`PR/Commit`

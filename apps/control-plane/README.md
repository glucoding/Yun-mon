# Yun-mon Control Plane

声明式控制面：以 `infra/control-plane/desired-state.json` 为单一事实源，渲染并下发 Prometheus、Alertmanager、Loki、Promtail、Grafana 仪表盘等组件配置，并通过 host stack-agent 触发 `docker compose` 重建闭环。

## 模块结构

详见 [`docs/IMPROVEMENT_PLAN.md`](../../docs/IMPROVEMENT_PLAN.md) `P1-1` 节。

## 本地开发

```bash
cd apps/control-plane
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e .[dev]
pytest
ruff check src tests
mypy src
```

## 启动

```bash
python -m yunmon_control_plane.main
```

环境变量：

| 变量                            | 默认                            | 说明                          |
| ------------------------------- | ------------------------------- | ----------------------------- |
| `CONTROL_PLANE_WORKSPACE`       | `/workspace`                    | 仓库根路径                    |
| `CONTROL_PLANE_HTTP_PORT`       | `8090`                          | HTTP 端口                     |
| `MONITORING_PROJECT`            | `yun-mon`                       | Compose 项目名                |
| `DOCKER_SOCKET`                 | `/var/run/docker.sock`          | Docker UDS                    |
| `CONTROL_PLANE_AUTH_ENABLED`    | `false`                         | 是否启用 RBAC（P3）           |
| `CONTROL_PLANE_JWT_SECRET`      | 自动生成                        | JWT 签名密钥                  |
| `CONTROL_PLANE_OTEL_ENDPOINT`   | （空）                          | OTLP HTTP endpoint            |

## API 概览

- `GET /healthz` 健康检查
- `GET /metrics` Prometheus 指标
- `GET /api/v1/config` 当前 desired-state
- `PUT /api/v1/config` 应用 desired-state（dry-run 校验 + diff + 渲染 + reload）
- `POST /api/v1/config/apply` 同 PUT 的别名
- `GET /api/v1/audit/snapshots` 审计快照列表
- `POST /api/v1/audit/snapshots/{id}/rollback` 回滚到指定快照
- `GET /api/v1/system/services` Compose 项目下容器列表
- `GET /api/v1/system/runtime` stack-agent 可达性
- `POST /api/v1/system/restart` 触发 reconcile（返回 jobId）
- `GET /api/v1/jobs/{id}` 查询任务状态
- `GET /api/v1/jobs/{id}/stream` SSE 进度
- `GET /api/v1/applications/discovery` 应用自动发现结果
- `GET /api/v1/metrics/catalog` 指标目录视图
- `POST /api/v1/metrics/catalog/sync` 从 Prometheus metadata 同步
- `POST /api/v1/auth/login` / `/refresh` / `/logout`（启用 RBAC 时）

# Stack Agent

`stack-agent` 是运行在宿主机上的轻量执行代理，用来弥补容器内 `control-plane` 无法可靠触发宿主机 `docker compose up -d --build` 的问题。

## 作用

- 接收来自 `control-plane` 的受控重建请求
- 在宿主机执行 `docker compose up -d --build`
- 返回构建 / 重建结果与 `docker compose ps` 状态
- 为控制面提供统一的“重建闭环”能力

## 接口

- `GET /healthz`：健康检查与最近一次执行摘要
- `GET /metrics`：Prometheus 指标
- `GET /api/v1/compose/status`：当前 `docker compose ps` 输出
- `POST /api/v1/compose/reconcile`：执行 `docker compose up -d --build`

## 鉴权

当前版本使用共享令牌：

- Header：`X-Stack-Agent-Token`
- 配置项：`STACK_AGENT_SHARED_TOKEN`

后续建议演进为：

- mTLS
- 本机 Unix socket / named pipe
- 或最少配合反向代理与防火墙收口

## Windows 启动

在仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-stack-agent.ps1
```

停止：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop-stack-agent.ps1
```

## Ubuntu 启动

交互式启动：

```bash
./scripts/start-stack-agent.sh
```

停止：

```bash
./scripts/stop-stack-agent.sh
```

systemd 模板文件：

- [yunmon-stack-agent.service](/E:/Yun-mon/deploy/ubuntu/yunmon-stack-agent.service)

## 当前实现边界

- `stack-agent` 当前主要面向 Docker 模式
- 对 Kubernetes 模式，后续应替换为 `helm upgrade` / `kubectl apply` / Operator 驱动的发布适配层

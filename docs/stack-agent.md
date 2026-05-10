# Stack Agent

`stack-agent` 是运行在宿主机上的轻量执行代理,弥补容器内 `control-plane` 无法可靠触发 `docker compose up -d --build` 的问题。

## 作用

- 接收来自 `control-plane` 的受控重建请求
- 在宿主机执行 `docker compose up -d --build`
- 返回构建 / 重建结果与 `docker compose ps` 状态
- 为控制面提供统一的"重建闭环"能力

## 接口

- `GET /healthz`：健康检查与最近一次执行摘要
- `GET /metrics`：Prometheus 指标
- `GET /api/v1/compose/status`:当前 `docker compose ps` 输出
- `POST /api/v1/compose/reconcile`:执行 `docker compose up -d --build`

## 安全模型(P0-4 / P0-5)

- **必须配置共享 token**:`STACK_AGENT_SHARED_TOKEN` 长度 >=16,首次启动若未提供进程退出码 2。
- **默认仅监听 127.0.0.1**:启动脚本默认 `STACK_AGENT_HTTP_HOST=127.0.0.1`,容器内 `control-plane` 在此模式下访问不到 stack-agent,会自动回退到 `docker-api restart` 模式。
- **启用容器闭环时**:必须显式 `STACK_AGENT_HTTP_HOST=0.0.0.0`,并叠加以下任一管控:
  1. 主机防火墙屏蔽 19090 端口对外
  2. 反向代理(nginx / Caddy)做 mTLS / IP allowlist
  3. 在 docker bridge 内部 IP 上单独绑定(如 `172.17.0.1`),不暴露到外部网卡
- **token 由 control-plane 自动生成**:首次启动 `secrets.token_urlsafe(32)`,落入 `infra/control-plane/desired-state.json` 的 `stackAgent.sharedToken`,并随 `apply_state` 写入 `.env`。
- **token 轮换**:在控制台 `Host Stack Agent` 面板编辑后保存,即可生成新 token,并通过 `apply` + 重启 stack-agent 完成轮换。

## 后续演进

- mTLS:计划在 P3 阶段引入。
- 本机 Unix socket / named pipe:更优的本机闭环方案,相对 mTLS 实现成本更低。

## Windows 启动

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-stack-agent.ps1
```

## Ubuntu 启动

```bash
./scripts/start-stack-agent.sh
```

systemd 模板：[deploy/ubuntu/yunmon-stack-agent.service](../deploy/ubuntu/yunmon-stack-agent.service)。

## 边界

- 当前主要面向 Docker 模式
- Kubernetes 模式应替换为 `helm upgrade` / `kubectl apply` / Operator 驱动的发布适配层(P3 完成)

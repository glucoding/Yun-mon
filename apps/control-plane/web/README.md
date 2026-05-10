# Yun-mon 控制台前端

Vue 3 + TypeScript + Vite + Pinia + Vue Router。视觉/信息架构延续之前的 Vanilla JS 控制台。

## 开发

```bash
pnpm install
pnpm dev      # 默认 5173,代理 /api 到 http://127.0.0.1:18090
```

## 构建

```bash
pnpm build
```

构建产物输出到 `dist/`,FastAPI 启动时会自动 mount 这一目录;若 `dist/` 不存在则回退到 `apps/control-plane/static/`(老版 Vanilla 前端)。

## 工程结构

```
src/
  main.ts            # 入口
  App.vue            # 应用 shell + 侧边栏 + 集群切换
  router.ts
  api/client.ts      # fetch 封装,自动注入 Authorization
  stores/config.ts   # Pinia store:desired-state 草稿与已下发对比
  views/             # 一个路由对应一个 panel
  styles/global.css  # 暗色主题
```

## 后续

- Panel 进一步拆细（端口、Grafana、Prometheus、Alertmanager、Loki、Promtail、Stack-agent、SLO、用户管理）
- OpenAPI 自动生成 TS client
- 主题切换、国际化

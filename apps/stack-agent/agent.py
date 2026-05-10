"""Yun-mon 宿主机 stack-agent。

P0-4：默认绑定 127.0.0.1,跨主机使用必须显式提升 STACK_AGENT_HTTP_HOST。
P0-5：必须显式提供 STACK_AGENT_SHARED_TOKEN,且最少 16 字符,否则拒绝启动。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

WORKSPACE = Path(
    os.environ.get(
        "STACK_AGENT_WORKSPACE",
        Path(__file__).resolve().parents[2],
    )
)
HTTP_HOST = os.environ.get("STACK_AGENT_HTTP_HOST", "127.0.0.1").strip() or "127.0.0.1"
HTTP_PORT = int(os.environ.get("STACK_AGENT_HTTP_PORT", "19090"))
SHARED_TOKEN = os.environ.get("STACK_AGENT_SHARED_TOKEN", "").strip()
COMPOSE_PATH = WORKSPACE / "compose.yaml"
ENV_PATH = WORKSPACE / ".env"
SERVER_START_TIME = time.time()
RECONCILE_SERVICES = [
    "cadvisor",
    "demo-service",
    "promtail",
    "loki",
    "alertmanager",
    "prometheus",
    "grafana",
]
METRICS_LOCK = threading.Lock()
METRICS = {
    "http_requests_total": 0,
    "compose_reconcile_total": 0,
    "compose_reconcile_failures_total": 0,
    "last_successful_reconcile_timestamp": 0,
}
LAST_ACTION_LOCK = threading.Lock()
LAST_ACTION = {
    "status": "idle",
    "timestamp": None,
    "summary": "尚未执行任何 compose 动作",
}


def timestamp_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def bump_metric(key: str, delta: int = 1) -> None:
    with METRICS_LOCK:
        METRICS[key] = METRICS.get(key, 0) + delta


def set_metric(key: str, value: int) -> None:
    with METRICS_LOCK:
        METRICS[key] = value


def snapshot_metrics() -> dict:
    with METRICS_LOCK:
        return dict(METRICS)


def set_last_action(status: str, summary: str, details=None) -> None:
    with LAST_ACTION_LOCK:
        LAST_ACTION["status"] = status
        LAST_ACTION["timestamp"] = timestamp_now()
        LAST_ACTION["summary"] = summary
        LAST_ACTION["details"] = details


def get_last_action() -> dict:
    with LAST_ACTION_LOCK:
        return dict(LAST_ACTION)


def docker_compose_base() -> list[str]:
    command = ["docker", "compose"]
    if ENV_PATH.exists():
        command.extend(["--env-file", str(ENV_PATH)])
    command.extend(["-f", str(COMPOSE_PATH)])
    return command


def decode_output(raw: bytes | None) -> str:
    if raw is None:
        return ""
    for encoding in ("utf-8", "gbk", "utf-16"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def run_compose(args: list[str], timeout: int = 1800) -> dict:
    environment = os.environ.copy()
    environment["DOCKER_BUILDKIT"] = "0"
    environment["COMPOSE_DOCKER_CLI_BUILD"] = "0"
    command = docker_compose_base() + list(args)
    result = subprocess.run(
        command,
        cwd=str(WORKSPACE),
        capture_output=True,
        text=False,
        timeout=timeout,
        check=False,
        env=environment,
    )
    return {
        "command": " ".join(command),
        "returncode": result.returncode,
        "stdout": decode_output(result.stdout).strip(),
        "stderr": decode_output(result.stderr).strip(),
    }


def compose_status() -> dict:
    return run_compose(["ps"], timeout=60)


def reconcile_runtime(
    *, include_control_plane: bool = False, build: bool = True, services: list[str] | None = None
) -> dict:
    target_services = list(services or RECONCILE_SERVICES)
    if include_control_plane and "control-plane" not in target_services:
        target_services.append("control-plane")

    build_result = None
    if build:
        build_result = run_compose(["build"] + target_services)
        if build_result["returncode"] != 0:
            payload = {
                "project": WORKSPACE.name,
                "mode": "docker-compose-reconcile",
                "services": target_services,
                "build": build_result,
                "status": compose_status(),
            }
            bump_metric("compose_reconcile_failures_total")
            set_last_action("failed", "docker compose build 失败", payload)
            raise RuntimeError(json.dumps(payload, ensure_ascii=False))

    up_result = run_compose(["up", "-d", "--no-deps"] + target_services)
    status = compose_status()
    payload = {
        "project": WORKSPACE.name,
        "mode": "docker-compose-reconcile",
        "services": target_services,
        "build": build_result,
        "result": up_result,
        "status": status,
    }
    if up_result["returncode"] != 0:
        bump_metric("compose_reconcile_failures_total")
        set_last_action("failed", "docker compose reconcile 失败", payload)
        raise RuntimeError(json.dumps(payload, ensure_ascii=False))

    bump_metric("compose_reconcile_total")
    set_metric("last_successful_reconcile_timestamp", int(time.time()))
    set_last_action("success", "docker compose reconcile 成功", payload)
    return payload


def render_metrics() -> str:
    metrics = snapshot_metrics()
    uptime = int(time.time() - SERVER_START_TIME)
    lines = [
        "# HELP stack_agent_http_requests_total Total HTTP requests served.",
        "# TYPE stack_agent_http_requests_total counter",
        f"stack_agent_http_requests_total {metrics['http_requests_total']}",
        "# HELP stack_agent_compose_reconcile_total Successful docker compose reconcile operations.",
        "# TYPE stack_agent_compose_reconcile_total counter",
        f"stack_agent_compose_reconcile_total {metrics['compose_reconcile_total']}",
        "# HELP stack_agent_compose_reconcile_failures_total Failed docker compose reconcile operations.",
        "# TYPE stack_agent_compose_reconcile_failures_total counter",
        f"stack_agent_compose_reconcile_failures_total {metrics['compose_reconcile_failures_total']}",
        "# HELP stack_agent_last_successful_reconcile_timestamp Unix timestamp of the last successful reconcile.",
        "# TYPE stack_agent_last_successful_reconcile_timestamp gauge",
        f"stack_agent_last_successful_reconcile_timestamp {metrics['last_successful_reconcile_timestamp']}",
        "# HELP stack_agent_uptime_seconds Agent uptime in seconds.",
        "# TYPE stack_agent_uptime_seconds gauge",
        f"stack_agent_uptime_seconds {uptime}",
    ]
    return "\n".join(lines) + "\n"


class Handler(BaseHTTPRequestHandler):
    server_version = "YunMonStackAgent/0.2"

    def log_message(self, fmt, *args):  # noqa: A003
        print(f"[{self.log_date_time_string()}] {self.address_string()} {fmt % args}")

    def _json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _text(self, payload, content_type="text/plain; charset=utf-8", status=200):
        body = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _require_auth(self) -> bool:
        candidate = self.headers.get("X-Stack-Agent-Token", "").strip()
        if not candidate:
            auth_header = self.headers.get("Authorization", "")
            if auth_header.lower().startswith("bearer "):
                candidate = auth_header.split(" ", 1)[1].strip()
        if candidate != SHARED_TOKEN:
            self._json({"ok": False, "error": "stack-agent 鉴权失败"}, status=401)
            return False
        return True

    def do_GET(self):  # noqa: N802
        bump_metric("http_requests_total")
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/healthz":
                self._json(
                    {
                        "ok": True,
                        "status": "ok",
                        "timestamp": timestamp_now(),
                        "workspace": str(WORKSPACE),
                        "composeFile": str(COMPOSE_PATH),
                        "envFileExists": ENV_PATH.exists(),
                        "tokenConfigured": True,
                        "lastAction": get_last_action(),
                    }
                )
                return
            if parsed.path == "/metrics":
                self._text(render_metrics(), "text/plain; version=0.0.4; charset=utf-8")
                return
            if not self._require_auth():
                return
            if parsed.path == "/api/v1/compose/status":
                self._json({"ok": True, "status": compose_status()})
                return
            self.send_error(404)
        except Exception as exc:  # pragma: no cover
            self._json({"ok": False, "error": str(exc)}, status=500)

    def do_POST(self):  # noqa: N802
        bump_metric("http_requests_total")
        parsed = urlparse(self.path)
        if not self._require_auth():
            return
        try:
            if parsed.path == "/api/v1/compose/reconcile":
                body = self._read_json_body()
                payload = reconcile_runtime(
                    include_control_plane=bool(body.get("includeControlPlane", False)),
                    build=bool(body.get("build", True)),
                    services=body.get("services"),
                )
                self._json({"ok": True, **payload})
                return
            self.send_error(404)
        except Exception as exc:
            self._json({"ok": False, "error": str(exc)}, status=500)


def main() -> None:
    if not SHARED_TOKEN or len(SHARED_TOKEN) < 16:
        sys.stderr.write(
            "stack-agent 启动被拒绝:必须通过 STACK_AGENT_SHARED_TOKEN 提供长度 >=16 的共享令牌。\n"
            "请在 desired-state.json 中保存配置并下发,或在启动脚本中显式注入 token。\n"
        )
        sys.exit(2)
    if HTTP_HOST == "0.0.0.0":
        sys.stderr.write(
            "[警告] stack-agent 当前绑定 0.0.0.0,任何能到达本机端口 "
            f"{HTTP_PORT} 的客户端都可凭 token 触发 docker compose。\n"
            "生产环境请仅绑定 127.0.0.1,并通过 mTLS / 反向代理收口。\n"
        )
    server = ThreadingHTTPServer((HTTP_HOST, HTTP_PORT), Handler)
    print(f"Yun-mon stack-agent 监听 {HTTP_HOST}:{HTTP_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()

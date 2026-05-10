#!/usr/bin/env bash
# P0-4：默认仅监听 127.0.0.1,显式 export STACK_AGENT_HTTP_HOST=0.0.0.0 才会暴露到外部网卡。
# P0-5：必须在 .env 中提供 STACK_AGENT_SHARED_TOKEN(>=16 字符),由 control-plane 自动生成。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"
LOG_DIR="${REPO_ROOT}/logs"
PID_FILE="${LOG_DIR}/stack-agent.pid"
STDOUT_LOG="${LOG_DIR}/stack-agent.out.log"
STDERR_LOG="${LOG_DIR}/stack-agent.err.log"

mkdir -p "${LOG_DIR}"

read_env() {
  local key="$1"
  local default_value="$2"
  if [[ -f "${ENV_FILE}" ]]; then
    local line
    line="$(grep -E "^${key}=" "${ENV_FILE}" | head -n 1 || true)"
    if [[ -n "${line}" ]]; then
      echo "${line#*=}" | sed 's/^"//; s/"$//'
      return 0
    fi
  fi
  echo "${default_value}"
}

STACK_AGENT_BASE_URL="$(read_env STACK_AGENT_BASE_URL http://host.docker.internal:19090)"
STACK_AGENT_SHARED_TOKEN="$(read_env STACK_AGENT_SHARED_TOKEN '')"
STACK_AGENT_HTTP_HOST="$(read_env STACK_AGENT_HTTP_HOST 127.0.0.1)"
export STACK_AGENT_BASE_URL

if [[ -z "${STACK_AGENT_SHARED_TOKEN}" || "${#STACK_AGENT_SHARED_TOKEN}" -lt 16 ]]; then
  echo "STACK_AGENT_SHARED_TOKEN 未配置或长度不足 16,请先通过控制台保存配置生成 token。" >&2
  exit 2
fi

STACK_AGENT_HTTP_PORT="$(python3 - <<'PY'
from urllib.parse import urlparse
import os
url = os.environ.get("STACK_AGENT_BASE_URL", "http://host.docker.internal:19090")
parsed = urlparse(url)
print(parsed.port or 19090)
PY
)"

if [[ -f "${PID_FILE}" ]] && kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
  echo "Yun-mon stack-agent is already running with PID $(cat "${PID_FILE}")."
  exit 0
fi

if [[ "${STACK_AGENT_HTTP_HOST}" == "0.0.0.0" ]]; then
  echo "[警告] stack-agent 将绑定 0.0.0.0,请确保已经叠加防火墙或反向代理收口。" >&2
fi

export STACK_AGENT_WORKSPACE="${REPO_ROOT}"
export STACK_AGENT_HTTP_HOST
export STACK_AGENT_HTTP_PORT
export STACK_AGENT_SHARED_TOKEN

nohup python3 "${REPO_ROOT}/apps/stack-agent/agent.py" >"${STDOUT_LOG}" 2>"${STDERR_LOG}" &
echo $! > "${PID_FILE}"

echo "Yun-mon stack-agent started with PID $(cat "${PID_FILE}") on ${STACK_AGENT_HTTP_HOST}:${STACK_AGENT_HTTP_PORT}."

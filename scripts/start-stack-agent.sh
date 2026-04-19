#!/usr/bin/env bash
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
STACK_AGENT_SHARED_TOKEN="$(read_env STACK_AGENT_SHARED_TOKEN yunmon-local-agent-token)"
STACK_AGENT_HTTP_PORT="$(python3 - <<'PY'
from urllib.parse import urlparse
import os
url = os.environ["STACK_AGENT_BASE_URL"]
parsed = urlparse(url)
print(parsed.port or 19090)
PY
)"

if [[ -f "${PID_FILE}" ]] && kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
  echo "Yun-mon stack-agent is already running with PID $(cat "${PID_FILE}")."
  exit 0
fi

export STACK_AGENT_WORKSPACE="${REPO_ROOT}"
export STACK_AGENT_HTTP_HOST="0.0.0.0"
export STACK_AGENT_HTTP_PORT
export STACK_AGENT_SHARED_TOKEN

nohup python3 "${REPO_ROOT}/apps/stack-agent/agent.py" >"${STDOUT_LOG}" 2>"${STDERR_LOG}" &
echo $! > "${PID_FILE}"

echo "Yun-mon stack-agent started with PID $(cat "${PID_FILE}") on port ${STACK_AGENT_HTTP_PORT}."

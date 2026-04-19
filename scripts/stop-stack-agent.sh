#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PID_FILE="${REPO_ROOT}/logs/stack-agent.pid"

if [[ ! -f "${PID_FILE}" ]]; then
  echo "No stack-agent PID file found."
  exit 0
fi

PID="$(cat "${PID_FILE}")"
if kill -0 "${PID}" 2>/dev/null; then
  kill "${PID}"
  echo "Stopped stack-agent process ${PID}."
else
  echo "Stack-agent process was not running."
fi

rm -f "${PID_FILE}"

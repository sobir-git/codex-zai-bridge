#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${REPO_DIR}/.env"
PORT="${CODEX_ZAI_PORT:-}"

if [[ -z "${PORT}" && -f "${ENV_FILE}" ]]; then
  PORT="$(grep -E '^CODEX_ZAI_PORT=' "${ENV_FILE}" | head -n1 | cut -d= -f2-)"
fi

[[ -n "${PORT}" ]] || PORT="18081"

if curl -fsS -H "Authorization: Bearer dummy-key" "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "codex-zai bridge: healthy on 127.0.0.1:${PORT}"
else
  echo "codex-zai bridge: not running"
fi

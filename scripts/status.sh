#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${REPO_DIR}/.env"
LIB_FILE="${REPO_DIR}/scripts/lib.sh"
PROJECT_NAME="${CODEX_ZAI_PROJECT:-codex-zai}"

source "${LIB_FILE}"

export COMPOSE_PROJECT_NAME="${PROJECT_NAME}"
PORT="$(resolve_port)"
if docker compose --env-file "${ENV_FILE}" -f "${REPO_DIR}/docker-compose.yml" ps --format json | grep -q '"State":"running"'; then
  echo "codex-zai bridge container is running"
else
  echo "codex-zai bridge container is not running"
fi

if health_check "${PORT}"; then
  echo "codex-zai bridge: healthy on 127.0.0.1:${PORT}"
else
  echo "codex-zai bridge: unhealthy on 127.0.0.1:${PORT}" >&2
  exit 1
fi

#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${REPO_DIR}/.env"
PROJECT_NAME="${CODEX_ZAI_PROJECT:-codex-zai}"
LIB_FILE="${REPO_DIR}/scripts/lib.sh"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Run install.sh or set up your API key first." >&2
  exit 1
fi

source "${LIB_FILE}"

export COMPOSE_PROJECT_NAME="${PROJECT_NAME}"
docker compose --env-file "${ENV_FILE}" -f "${REPO_DIR}/docker-compose.yml" up -d --build

PORT="$(resolve_port)"
for _ in {1..30}; do
  if health_check "${PORT}"; then
    exit 0
  fi
  sleep 1
done

echo "codex-zai bridge did not become healthy in time." >&2
docker compose --env-file "${ENV_FILE}" -f "${REPO_DIR}/docker-compose.yml" logs --tail=100
exit 1

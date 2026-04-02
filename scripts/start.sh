#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${REPO_DIR}/.env"
PORT="${CODEX_ZAI_PORT:-}"
PROJECT_NAME="${CODEX_ZAI_PROJECT:-codex-zai}"

if [[ -z "${PORT}" && -f "${ENV_FILE}" ]]; then
  PORT="$(grep -E '^CODEX_ZAI_PORT=' "${ENV_FILE}" | head -n1 | cut -d= -f2-)"
fi

[[ -n "${PORT}" ]] || PORT="18081"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Run install.sh or set up your API key first." >&2
  exit 1
fi

export COMPOSE_PROJECT_NAME="${PROJECT_NAME}"
if ! docker image inspect codex-zai-responses-server:latest >/dev/null 2>&1; then
  docker compose --env-file "${ENV_FILE}" -f "${REPO_DIR}/docker-compose.yml" build responses-server >/dev/null
fi
docker compose --env-file "${ENV_FILE}" -f "${REPO_DIR}/docker-compose.yml" up -d

for _ in {1..30}; do
  if curl -fsS -H "Authorization: Bearer dummy-key" "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    exit 0
  fi
  sleep 1
done

echo "codex-zai bridge did not become healthy in time." >&2
docker compose --env-file "${ENV_FILE}" -f "${REPO_DIR}/docker-compose.yml" logs --tail=100
exit 1

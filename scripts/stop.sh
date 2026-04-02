#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${REPO_DIR}/.env"
PROJECT_NAME="${CODEX_ZAI_PROJECT:-codex-zai}"

export COMPOSE_PROJECT_NAME="${PROJECT_NAME}"
docker compose --env-file "${ENV_FILE}" -f "${REPO_DIR}/docker-compose.yml" down >/dev/null

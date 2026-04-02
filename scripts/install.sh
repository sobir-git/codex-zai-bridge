#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="${HOME}/.local/share/codex-zai"
BIN_DIR="${HOME}/.local/bin"
BIN_PATH="${BIN_DIR}/codex-zai"
ENV_FILE="${INSTALL_DIR}/.env"
PROJECT_NAME="${CODEX_ZAI_PROJECT:-codex-zai}"

mkdir -p "${HOME}/.local/share" "${BIN_DIR}"
rm -rf "${INSTALL_DIR}"
cp -R "${REPO_DIR}" "${INSTALL_DIR}"

if [[ ! -f "${ENV_FILE}" ]]; then
  cat > "${ENV_FILE}" <<EOF
ZAI_API_KEY=
CODEX_ZAI_MODEL=glm-5.1
CODEX_ZAI_PORT=18081
EOF
fi

if [[ -f "${HOME}/.claude-zai-api-key" ]]; then
  sed -i "s#^ZAI_API_KEY=.*#ZAI_API_KEY=$(tr -d '\n\r' < "${HOME}/.claude-zai-api-key")#" "${ENV_FILE}"
elif [[ -f "${HOME}/.codex-zai-api-key" ]]; then
  sed -i "s#^ZAI_API_KEY=.*#ZAI_API_KEY=$(tr -d '\n\r' < "${HOME}/.codex-zai-api-key")#" "${ENV_FILE}"
fi

cp "${INSTALL_DIR}/bin/codex-zai" "${BIN_PATH}"
chmod +x "${BIN_PATH}"
chmod +x "${INSTALL_DIR}/scripts/"*.sh

export COMPOSE_PROJECT_NAME="${PROJECT_NAME}"
docker compose --env-file "${ENV_FILE}" -f "${INSTALL_DIR}/docker-compose.yml" build responses-server >/dev/null

cat <<EOF
Installed codex-zai to ${BIN_PATH}
Runtime files live in ${INSTALL_DIR}

Next:
  1. Run: codex-zai auth
  2. Run: codex-zai exec --ephemeral "Reply with exactly one word: ok"

If ${BIN_DIR} is not on your PATH, add it and restart your shell.
EOF

#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${HOME}/.local/share/codex-zai"
BIN_PATH="${HOME}/.local/bin/codex-zai"

if [[ -x "${INSTALL_DIR}/scripts/stop.sh" ]]; then
  "${INSTALL_DIR}/scripts/stop.sh" || true
fi

rm -f "${BIN_PATH}"
rm -rf "${INSTALL_DIR}"

echo "Removed codex-zai."

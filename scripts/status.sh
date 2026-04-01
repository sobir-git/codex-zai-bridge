#!/usr/bin/env bash
set -euo pipefail

PORT="${CODEX_ZAI_PORT:-18081}"

if curl -fsS -H "Authorization: Bearer dummy-key" "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "codex-zai bridge: healthy on 127.0.0.1:${PORT}"
else
  echo "codex-zai bridge: not running"
fi

#!/usr/bin/env bash

resolve_port() {
  local env_file="${1:-${ENV_FILE:-}}"
  local port="${CODEX_ZAI_PORT:-}"
  if [[ -z "${port}" && -f "${env_file}" ]]; then
    port="$(grep -E '^CODEX_ZAI_PORT=' "${env_file}" | head -n1 | cut -d= -f2-)"
  fi
  printf '%s' "${port:-18081}"
}

health_check() {
  local port="$1"
  curl --fail --silent --show-error --connect-timeout 2 --max-time 5 \
    -H "Authorization: Bearer dummy-key" \
    "http://127.0.0.1:${port}/health" >/dev/null 2>&1
}

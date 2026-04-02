#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_FILE="${1:-}"

if [[ -n "${OUTPUT_FILE}" ]]; then
  exec >"${OUTPUT_FILE}"
fi

files=(
  "AGENTS.md"
  "README.md"
  "docs/architecture.md"
  "docker-compose.yml"
  "config/zai-nginx.conf"
  "bin/codex-zai"
  "scripts/install.sh"
  "scripts/lib.sh"
  "scripts/start.sh"
  "scripts/status.sh"
  "scripts/stop.sh"
  "scripts/test.sh"
  "scripts/cat-relevant.sh"
  "adapter/src/open_responses_server/api_controller.py"
  "adapter/tests/test_responses_stream.py"
)

printf '===== GIT STATUS =====\n'
git -C "${REPO_DIR}" status --short

printf '\n===== GIT DIFF STAT =====\n'
git -C "${REPO_DIR}" diff --stat

printf '\n===== GIT DIFF =====\n'
git -C "${REPO_DIR}" diff -- . ':(exclude)adapter/.venv' ':(exclude)adapter/.pytest_cache'

for file in "${files[@]}"; do
  full_path="${REPO_DIR}/${file}"
  if [[ -f "${full_path}" ]]; then
    printf '\n===== %s =====\n' "${file}"
    cat "${full_path}"
  fi
done

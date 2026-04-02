#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 -m pytest "${REPO_DIR}/adapter/tests/test_responses_stream.py"
docker compose -f "${REPO_DIR}/docker-compose.yml" config >/dev/null
docker build -t codex-zai-responses-server:test "${REPO_DIR}/adapter" >/dev/null

echo "Tests passed."

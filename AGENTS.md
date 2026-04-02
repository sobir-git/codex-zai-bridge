# AGENTS.md

## Overview

`codex-zai-bridge` lets current Codex CLI talk to Z.ai GLM coding models without changing the user's normal Codex setup.

The project works by bridging:

`Codex Responses API -> local adapter -> local nginx rewrite -> Z.ai chat/completions`

## Main Areas

- `bin/codex-zai`
  User-facing entrypoint. Keep UX simple and argument forwarding intact.
- `scripts/`
  Install, start, stop, status, uninstall, and verification helpers.
- `docker-compose.yml`
  Local runtime stack definition.
- `config/zai-nginx.conf`
  Rewrites local OpenAI-compatible chat requests to the Z.ai coding endpoint.
- `adapter/src/open_responses_server/`
  Vendored bridge implementation. This is the most fragile area because Codex is strict about Responses streaming behavior.
- `adapter/tests/test_responses_stream.py`
  Regression test for the exact event sequence Codex expects.

## Working Rules

- Default to changing the smallest surface that solves the problem.
- Preserve the normal `codex` command. This repo should only affect `codex-zai`.
- Do not add dependencies casually, especially in the adapter.
- Treat `adapter/src/open_responses_server/` as vendored upstream code with local patches, not as a place for broad refactors.
- Keep Docker exposure local-only. The intended bind is `127.0.0.1`.
- Prefer improving docs and scripts over adding complexity to runtime behavior.

## Testing

Run the packaged verification suite after meaningful changes:

```bash
./scripts/test.sh
```

That currently checks:

- adapter regression test
- Compose config validity
- adapter image buildability

If you change the wrapper, install flow, or runtime startup behavior, also do a smoke test such as:

```bash
./scripts/install.sh
codex-zai doctor
codex-zai status
codex-zai exec --ephemeral --skip-git-repo-check "Reply with exactly one word: ok"
```

For isolated reproduction, prefer:

```bash
HOME=/tmp/codex-zai-test-home CODEX_ZAI_PROJECT=codex-zai-test ./scripts/install.sh
```

## Editing Guidance

- `bin/codex-zai` is the public UX. Be careful with command names and output wording.
- `scripts/install.sh` and `scripts/uninstall.sh` affect user machines. Favor predictable file locations under `~/.local`.
- `scripts/start.sh` and `scripts/status.sh` should keep working even when `CODEX_ZAI_PROJECT` or `CODEX_ZAI_PORT` are customized.
- If you change adapter streaming behavior, update or extend `adapter/tests/test_responses_stream.py` in the same change.
- If you change architecture or user workflow, update `README.md` and `docs/architecture.md`.

## Known Sharp Edges

- Codex currently expects the Responses API, not chat completions.
- Z.ai currently exposes the coding model through `chat/completions`, not native `responses`.
- The adapter compatibility patch is important. Codex may break if the event lifecycle order changes.
- Vendored adapter packaging may emit Docker warnings about secret-like env names. Avoid unnecessary churn there unless you are intentionally addressing packaging.

## Release Notes

Before publishing:

```bash
./scripts/test.sh
git status --short
```

If the repo behavior changed in a user-visible way, update:

- `README.md`
- `docs/architecture.md`
- release notes

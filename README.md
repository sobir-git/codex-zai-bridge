# codex-zai

Run current Codex CLI against Z.ai GLM models without touching your normal Codex config.

`codex-zai` starts a small local bridge on `127.0.0.1` that:

- accepts the OpenAI Responses API that Codex requires
- rewrites upstream calls to Z.ai's `chat/completions` coding endpoint
- keeps your default `codex` command unchanged

## Why this exists

Current Codex custom providers expect a Responses API backend.

Z.ai's public OpenAI-compatible coding API is exposed through `chat/completions`, not `responses`.

So the missing piece is a local bridge:

`Codex -> Responses API bridge -> Z.ai chat/completions`

This repo packages that bridge into a simple command.

## Features

- `codex` stays untouched
- `codex-zai` works like normal Codex and forwards all arguments
- remembers your last Z.ai API key locally
- runs only on `127.0.0.1`
- uses Docker Compose for reproducible setup
- bundles a patched MIT-licensed Responses bridge based on `open-responses-server`
- pins tested base image versions
- includes regression tests for the Responses event sequence Codex expects
- supports isolated installs via `CODEX_ZAI_PROJECT` to avoid compose-name collisions

## Install

Requirements:

- Docker with Compose
- `codex` on your `PATH`

Install:

```bash
git clone https://github.com/sobir-git/codex-zai-bridge.git codex-zai
cd codex-zai
./scripts/install.sh
```

Then:

```bash
codex-zai auth
codex-zai exec --ephemeral "Reply with exactly one word: ok"
```

## Usage

Run Codex with Z.ai:

```bash
codex-zai
codex-zai exec --ephemeral "explain this repo"
codex-zai --help
```

Management commands:

```bash
codex-zai status
codex-zai doctor
codex-zai resume
codex-zai stop
codex-zai rebuild
codex-zai forget-key
```

## Config

After install, runtime config lives in:

[`~/.local/share/codex-zai/.env`](/home/fire/.local/share/codex-zai/.env)

Supported values:

```env
ZAI_API_KEY=
CODEX_ZAI_MODEL=glm-5.1
CODEX_ZAI_PORT=18081
```

You can also set `CODEX_ZAI_PROJECT`, `CODEX_ZAI_MODEL`, or `CODEX_ZAI_PORT` before running `./scripts/install.sh` to seed a custom install.

You can also override the key per run with:

```bash
ZAI_API_KEY=... codex-zai exec --ephemeral "say ok"
```

If you need multiple side-by-side installs, give each one a different compose project:

```bash
CODEX_ZAI_PROJECT=codex-zai-work codex-zai status
```

Codex profiles are still available through the normal `codex` CLI options, but `codex-zai` keeps the bridge wiring pinned with explicit overrides so profile defaults cannot break the local bridge.
`codex-zai` uses Codex's built-in `openai` provider name with `openai_base_url` pointed at the local bridge, so interactive `codex` and `codex-zai` runs should stay in the same resume history.

## Architecture

The local stack has two containers:

1. `nginx`
   Rewrites `POST /v1/chat/completions` to Z.ai's coding endpoint.

2. `responses-server`
   Accepts Responses API requests from Codex and converts them into chat completions.

More detail lives in [`docs/architecture.md`](docs/architecture.md).

The bridge binds only to:

```text
127.0.0.1:18081
```

## Notes

- This repo does not make Z.ai expose a native `/responses` API.
- It exists because current Codex requires Responses for custom providers.
- The vendored adapter source is MIT-licensed and acknowledged in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Troubleshooting

Check bridge health:

```bash
codex-zai status
```

`codex-zai status` exits non-zero when the bridge is unhealthy.

Check prerequisites:

```bash
codex-zai doctor
```

Rebuild after changes:

```bash
codex-zai rebuild
```

Run the packaged verification suite from the repo:

```bash
./scripts/test.sh
```

Stop everything:

```bash
codex-zai stop
```

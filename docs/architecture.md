# Architecture

`codex-zai` exists because current Codex requires the OpenAI Responses API for custom providers, while Z.ai exposes an OpenAI-compatible `chat/completions` API for GLM coding models.

The bridge fills that protocol gap locally.

## Request flow

```text
Codex CLI
  -> local Responses API bridge
  -> local nginx rewrite proxy
  -> Z.ai coding chat/completions endpoint
```

## Components

### 1. `codex-zai` wrapper

[`bin/codex-zai`](../bin/codex-zai)

Responsibilities:

- provides a friendly CLI around the bridge
- stores or reads the Z.ai API key from the installed `.env`
- starts the local bridge if needed
- launches `codex` with temporary provider overrides

This keeps the user's normal `codex` setup untouched.
Codex `--profile` and other config defaults can still be used normally, but the wrapper pins the bridge-critical settings explicitly so profile choice only affects non-bridge defaults.
The wrapper keeps Codex on its built-in `openai` provider name and only swaps the local base URL through `openai_base_url`. That preserves the normal Codex session namespace, so interactive `codex` and `codex-zai` threads should appear together in `codex resume`.

### 2. Responses bridge

[`adapter/src/open_responses_server`](../adapter/src/open_responses_server)

Responsibilities:

- accepts Responses API requests from Codex
- converts them into chat-completions requests
- translates streaming chat chunks back into Responses API streaming events

Important local patch:

- the vendored adapter emits the message lifecycle events Codex expects:
  - `response.output_item.added`
  - `response.content_part.added`
  - `response.output_text.delta`
  - `response.output_text.done`
  - `response.content_part.done`
  - `response.output_item.done`
  - `response.completed`

That event ordering is required for current Codex compatibility.

### 3. nginx upstream proxy

[`config/zai-nginx.conf`](../config/zai-nginx.conf)

Responsibilities:

- exposes `/v1/chat/completions` locally
- rewrites that request to:
  - `https://api.z.ai/api/coding/paas/v4/chat/completions`
- enforces longer upstream timeouts for Codex-sized prompts

This avoids patching the bridge for a Z.ai-specific path difference.

## Why not direct LiteLLM?

LiteLLM was a tempting first option, but for OpenAI-like upstreams it assumes upstream `/responses` support in the path that matters for current Codex.

Z.ai's official coding endpoint is `chat/completions`, not `responses`, so LiteLLM alone was not enough for this integration.

## Stability strategy

The repo tries to remain usable over time by:

- vendoring the bridge instead of depending on an unpinned external checkout
- pinning tested base images in Docker
- keeping the protocol adaptation small and easy to inspect
- providing a regression test for the Codex event sequence
- keeping the user-facing state limited to one installed `.env`

## Isolation

By default the installed tool uses a Compose project named `codex-zai`.

For side-by-side installs or testing, `CODEX_ZAI_PROJECT` can isolate container names and networks:

```bash
CODEX_ZAI_PROJECT=codex-zai-test codex-zai status
```

The install script also records `CODEX_ZAI_PROJECT`, `CODEX_ZAI_MODEL`, and `CODEX_ZAI_PORT` into the installed `.env` so custom setup survives later wrapper commands.

## Main risks going forward

The integration is most likely to break if:

1. Codex changes its required Responses event contract again.
2. Z.ai changes the coding endpoint path or request format.
3. The vendored bridge upstream changes in ways we want to re-import later.

That is why the most important thing to preserve is the test coverage around the streaming event sequence.

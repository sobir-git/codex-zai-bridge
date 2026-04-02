import json
import os
import subprocess
import textwrap
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from open_responses_server.api_controller import LLMClient, app
from open_responses_server.responses_service import process_chat_completions_stream

STREAM_LINES = [
    'data: {"id":"chatcmpl_1","created":1,"object":"chat.completion.chunk","model":"glm-5.1","choices":[{"index":0,"delta":{"role":"assistant","content":"ok"}}]}',
    'data: {"id":"chatcmpl_1","created":1,"object":"chat.completion.chunk","model":"glm-5.1","choices":[{"index":0,"finish_reason":"stop","delta":{"role":"assistant","content":""}}]}',
    "data: [DONE]",
]

EXEC_REQUEST = {
    "model": "glm-5.1",
    "stream": True,
    "input": [
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "Reply with exactly one word: ok"}],
        }
    ],
}


class FakeResponse:
    status_code = 200

    def __init__(self, lines):
        self._lines = lines

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def aread(self):
        return b""


class FakeLLMClient:
    def __init__(self, response):
        self._response = response
        self.calls = []

    @asynccontextmanager
    async def stream(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        yield self._response


def assert_completed_ok(text):
    events = [
        json.loads(line[len("data: ") :])
        for line in text.splitlines()
        if line.startswith("data: ")
    ]
    assert events[-1]["type"] == "response.completed"
    assert events[-1]["response"]["output"][0]["content"][0]["text"] == "ok"


def write_executable(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content))
    path.chmod(0o755)


class TempPathEnv:
    def __init__(self, tmp_path: Path):
        self.home_dir = tmp_path / "home"
        self.install_dir = self.home_dir / ".local" / "share" / "codex-zai"
        self.bin_dir = tmp_path / "bin"
        self.calls_dir = tmp_path / "calls"

    def prepare(self) -> None:
        self.calls_dir.mkdir()
        self.install_dir.joinpath("scripts").mkdir(parents=True)
        self.bin_dir.mkdir()


@pytest.mark.asyncio
async def test_stop_stream_emits_required_message_lifecycle_events():
    response = FakeResponse(STREAM_LINES)

    raw_events = []
    events = []
    async for raw_event in process_chat_completions_stream(response, {"messages": []}):
        assert raw_event.startswith("data: ")
        raw_events.append(raw_event)
        payload = raw_event[len("data: ") :].strip()
        events.append(json.loads(payload))

    event_types = [event["type"] for event in events]

    assert event_types[:4] == [
        "response.created",
        "response.in_progress",
        "response.output_item.added",
        "response.content_part.added",
    ]
    assert "response.output_text.delta" in event_types
    assert "response.output_text.done" in event_types
    assert "response.content_part.done" in event_types
    assert "response.output_item.done" in event_types
    assert event_types[-1] == "response.completed"
    assert events[-1]["response"]["status"] == "completed"
    assert_completed_ok("\n".join(raw_events))


@pytest.mark.asyncio
async def test_responses_route_streams_events_end_to_end(monkeypatch):
    fake_client = FakeLLMClient(FakeResponse(STREAM_LINES))

    async def fake_get_client():
        return fake_client

    monkeypatch.setattr(LLMClient, "get_client", fake_get_client)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post("/responses", headers={"Authorization": "Bearer dummy-key"}, json=EXEC_REQUEST)

    assert resp.status_code == 200
    args, kwargs = fake_client.calls[0]
    assert args == ("POST", "/v1/chat/completions")
    assert kwargs["json"]["model"] == "glm-5.1"
    assert kwargs["json"]["stream"] is True
    assert kwargs["json"]["messages"][0]["role"] == "user"
    assert kwargs["json"]["messages"][0]["content"] == "Reply with exactly one word: ok"
    assert kwargs["timeout"] == 120.0
    assert_completed_ok(resp.text)


def test_responses_websocket_streams_events_end_to_end(monkeypatch):
    fake_client = FakeLLMClient(FakeResponse(STREAM_LINES))

    async def fake_get_client():
        return fake_client

    monkeypatch.setattr(LLMClient, "get_client", fake_get_client)

    with TestClient(app) as client:
        with client.websocket_connect("/responses") as websocket:
            websocket.send_json(
                {
                    "type": "response.create",
                    **EXEC_REQUEST,
                }
            )
            messages = []
            while True:
                try:
                    messages.append(websocket.receive_text())
                except Exception:
                    break

    assert fake_client.calls
    args, kwargs = fake_client.calls[0]
    assert args == ("POST", "/v1/chat/completions")
    assert kwargs["json"]["stream"] is True
    assert_completed_ok("\n".join(f"data: {message}" for message in messages))


def test_codex_zai_exec_invokes_bridge_and_codex(tmp_path):
    env_paths = TempPathEnv(tmp_path)
    env_paths.prepare()
    home_dir = env_paths.home_dir
    install_dir = env_paths.install_dir
    bin_dir = env_paths.bin_dir
    calls_dir = env_paths.calls_dir

    write_executable(
        install_dir / "scripts" / "start.sh",
        f"""\
        #!/usr/bin/env sh
        printf 'started\\n' > "{calls_dir / 'start.txt'}"
        exit 0
        """,
    )
    write_executable(
        bin_dir / "codex",
        f"""\
        #!/usr/bin/env sh
        printf '%s\\n' "$@" > "{calls_dir / 'codex-args.txt'}"
        printf '%s\\n' "$OPENAI_API_KEY" > "{calls_dir / 'openai-key.txt'}"
        exit 0
        """,
    )
    (install_dir / ".env").write_text(
        "ZAI_API_KEY=dummy-key\nCODEX_ZAI_MODEL=glm-5.1\nCODEX_ZAI_PORT=18081\n"
    )

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home_dir),
            "PATH": f"{bin_dir}:{env['PATH']}",
        }
    )

    subprocess.run(
        [
            str(Path(__file__).resolve().parents[2] / "bin" / "codex-zai"),
            "exec",
            "--ephemeral",
            "--skip-git-repo-check",
            "Reply with exactly one word: ok",
        ],
        env=env,
        check=True,
        text=True,
    )

    assert (calls_dir / "start.txt").read_text().strip() == "started"
    assert (calls_dir / "openai-key.txt").read_text().strip() == "dummy-key"

    codex_args = (calls_dir / "codex-args.txt").read_text().splitlines()
    assert "-c" in codex_args
    assert 'model="glm-5.1"' in codex_args
    assert 'model_provider="openai"' in codex_args
    assert 'openai_base_url="http://127.0.0.1:18081"' in codex_args

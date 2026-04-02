import json

import pytest

from open_responses_server.responses_service import process_chat_completions_stream


class FakeResponse:
    def __init__(self, lines):
        self._lines = lines

    async def aiter_lines(self):
        for line in self._lines:
            yield line


@pytest.mark.asyncio
async def test_stop_stream_emits_required_message_lifecycle_events():
    response = FakeResponse(
        [
            'data: {"id":"chatcmpl_1","created":1,"object":"chat.completion.chunk","model":"glm-5.1","choices":[{"index":0,"delta":{"role":"assistant","content":"ok"}}]}',
            'data: {"id":"chatcmpl_1","created":1,"object":"chat.completion.chunk","model":"glm-5.1","choices":[{"index":0,"finish_reason":"stop","delta":{"role":"assistant","content":""}}]}',
            "data: [DONE]",
        ]
    )

    events = []
    async for raw_event in process_chat_completions_stream(response, {"messages": []}):
        assert raw_event.startswith("data: ")
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

    completed = events[-1]["response"]
    assert completed["status"] == "completed"
    assert completed["output"][0]["content"][0]["text"] == "ok"

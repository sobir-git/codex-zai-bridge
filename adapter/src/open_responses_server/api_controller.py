import asyncio
import json
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from open_responses_server.common.config import logger, HEARTBEAT_INTERVAL, STREAM_TIMEOUT
from open_responses_server.common.llm_client import startup_llm_client, shutdown_llm_client, LLMClient
from open_responses_server.common.mcp_manager import mcp_manager
from open_responses_server.responses_service import convert_responses_to_chat_completions, process_chat_completions_stream
from open_responses_server.chat_completions_service import handle_chat_completions

_HEARTBEAT = object()


async def _with_heartbeat(async_gen, interval):
    """Wrap an async generator to yield _HEARTBEAT sentinels during idle periods.

    Uses asyncio.wait with timeout so the underlying task is never cancelled.
    This keeps SSE connections alive when the backend LLM is slow to respond.
    """
    if not interval or interval <= 0:
        interval = 1.0

    inner = async_gen.__aiter__()
    task = None
    try:
        while True:
            task = asyncio.ensure_future(inner.__anext__())
            while not task.done():
                done, _ = await asyncio.wait({task}, timeout=interval)
                if not done:
                    yield _HEARTBEAT
            try:
                yield task.result()
            except StopAsyncIteration:
                return
            finally:
                task = None
    finally:
        await _cleanup_heartbeat(task, inner)


async def _cleanup_heartbeat(task, inner):
    """Cancel in-flight task and close the underlying async iterator."""
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            raise
    if hasattr(inner, "aclose"):
        try:
            await inner.aclose()
        except Exception:
            logger.debug("Error closing heartbeat inner iterator", exc_info=True)


def _build_chat_request(request_data: dict) -> dict:
    if mcp_manager.mcp_functions_cache:
        existing_tools = request_data.get("tools", [])

        mcp_tools = [
            {"type": "function", "name": f["name"], "description": f.get("description"), "parameters": f.get("parameters", {})}
            for f in mcp_manager.mcp_functions_cache
        ]

        existing_tool_names = _tool_names(existing_tools)
        filtered_mcp_tools = [
            tool for tool in mcp_tools
            if tool["name"] not in existing_tool_names
        ]

        request_data["tools"] = existing_tools + filtered_mcp_tools

        logger.info(f"[TOOL-INJECT] /responses: {len(existing_tools)} existing tools, {len(mcp_manager.mcp_functions_cache)} MCP tools available")
        logger.info(f"[TOOL-INJECT] /responses: existing tool names: {list(existing_tool_names)}")
        logger.info(f"[TOOL-INJECT] /responses: available MCP tools: {[t['name'] for t in mcp_tools]}")
        logger.info(f"[TOOL-INJECT] /responses: filtered {len(filtered_mcp_tools)} MCP tools to inject: {[t['name'] for t in filtered_mcp_tools]}")
        logger.info(f"[TOOL-INJECT] /responses: final tool count: {len(request_data['tools'])}")
    else:
        logger.info("[TOOL-INJECT] /responses: no MCP tools available in cache")

    chat_request = convert_responses_to_chat_completions(request_data)

    if mcp_manager.mcp_functions_cache:
        existing_functions = chat_request.get("functions", [])

        if "tools" not in chat_request:
            chat_request["tools"] = []

        existing_tool_names = set()
        for tool in chat_request["tools"]:
            if isinstance(tool, dict) and "function" in tool and "name" in tool["function"]:
                existing_tool_names.add(tool["function"]["name"])
            elif isinstance(tool, dict) and "name" in tool:
                existing_tool_names.add(tool["name"])

        for func in existing_functions:
            if func.get("name") not in existing_tool_names:
                chat_request["tools"].append({
                    "type": "function",
                    "function": func
                })
                existing_tool_names.add(func.get("name", ""))

        mcp_tools_added = []
        for func in mcp_manager.mcp_functions_cache:
            if func.get("name") not in existing_tool_names:
                chat_request["tools"].append({
                    "type": "function",
                    "function": func
                })
                mcp_tools_added.append(func.get("name"))

        chat_request.pop("functions", None)

        logger.info(f"[TOOL-CONVERT] /responses: converted {len(existing_functions)} existing functions to tools format")
        logger.info(f"[TOOL-CONVERT] /responses: added {len(mcp_tools_added)} MCP tools: {mcp_tools_added}")
        logger.info(f"[TOOL-CONVERT] /responses: final chat_request tools count: {len(chat_request.get('tools', []))}")
    else:
        logger.info("[TOOL-CONVERT] /responses: no MCP functions cached, sending without MCP tools")

    chat_request.pop("tool_choice", None)
    return chat_request


def _tool_name(tool: dict) -> str | None:
    if "function" in tool and "name" in tool["function"]:
        return tool["function"]["name"]
    if "name" in tool:
        return tool["name"]
    return None


def _tool_names(tools: list[dict]) -> set[str]:
    return {name for tool in tools if (name := _tool_name(tool))}


def _merge_function_tools(chat_request: dict, functions: list[dict]) -> tuple[dict, list[str]]:
    existing_tools = list(chat_request.get("tools", []))
    existing_tool_names = _tool_names(existing_tools)
    added_function_names = []

    for func in functions:
        function_name = func.get("name")
        if function_name and function_name not in existing_tool_names:
            existing_tools.append({
                "type": "function",
                "function": func
            })
            existing_tool_names.add(function_name)
            added_function_names.append(function_name)

    if existing_tools:
        chat_request["tools"] = existing_tools
    else:
        chat_request.pop("tools", None)

    chat_request.pop("functions", None)
    return chat_request, added_function_names


async def _merge_runtime_tools(chat_request: dict) -> dict:
    mcp_functions = []
    for server in mcp_manager.mcp_servers:
        try:
            for t in await server.list_tools():
                mcp_functions.append({
                    "name": t["name"],
                    "description": t.get("description"),
                    "parameters": t.get("parameters", {}),
                })
        except Exception as e:
            logger.warning(f"Error listing tools from {server.name}: {e}")

    if mcp_functions:
        existing_functions = list(chat_request.get("functions", []))
        chat_request, added_function_names = _merge_function_tools(chat_request, existing_functions + mcp_functions)
        logger.info(
            f"Converted {len(existing_functions)} existing functions and {len(mcp_functions)} MCP functions to tools format"
        )
    elif "functions" in chat_request:
        existing_functions = list(chat_request.get("functions", []))
        chat_request, added_function_names = _merge_function_tools(chat_request, existing_functions)
        if existing_functions:
            logger.info(f"Converted {len(existing_functions)} existing functions to tools format")
        if not added_function_names and not chat_request.get("tools"):
            logger.info("No tools or functions available, sending without them")

    return chat_request


async def _stream_responses_events(chat_request: dict):
    chat_request = await _merge_runtime_tools(chat_request)
    logger.info(f"Sending Chat Completions request: {json.dumps(chat_request)}")
    client = await LLMClient.get_client()
    async with client.stream(
        "POST",
        "/v1/chat/completions",
        json=chat_request,
        timeout=STREAM_TIMEOUT
    ) as response:
        logger.info(f"Stream request status: {response.status_code}")

        if response.status_code != 200:
            error_content = await response.aread()
            logger.error(f"Error from LLM API: {error_content}")
            yield f"data: {json.dumps({'type': 'error', 'error': {'message': f'Error from LLM API: {response.status_code}'}})}\n\n"
            return

        async for event in _with_heartbeat(
            process_chat_completions_stream(response, chat_request),
            HEARTBEAT_INTERVAL
        ):
            if event is _HEARTBEAT:
                logger.debug("[STREAM-HEARTBEAT] Sending SSE keepalive")
                yield ": heartbeat\n\n"
            else:
                yield event


app = FastAPI(
    title="Open Responses Server",
    description="A proxy server that converts between different OpenAI-compatible API formats.",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Application startup event handler."""
    await startup_llm_client()
    await mcp_manager.startup_mcp_servers()
    logger.info("API Controller startup complete.")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event handler."""
    await shutdown_llm_client()
    await mcp_manager.shutdown_mcp_servers()
    logger.info("API Controller shutdown complete.")


# API endpoints
@app.websocket("/responses")
async def create_response_websocket(websocket: WebSocket):
    await websocket.accept()
    try:
        message = await websocket.receive_text()
        request_data = json.loads(message)
        logger.info("Received websocket request to /responses")
        logger.info(f"Received websocket request: model={request_data.get('model')}, stream={request_data.get('stream')}")

        if request_data.get("type") != "response.create":
            await websocket.send_text(json.dumps({"type": "error", "error": {"message": "Expected response.create"}}))
            await websocket.close(code=1003)
            return

        chat_request = _build_chat_request(request_data)
        async for event in _stream_responses_events(chat_request):
            if event.startswith("data: "):
                await websocket.send_text(event[len("data: ") :].strip())
        await websocket.close()
    except WebSocketDisconnect:
        logger.info("Websocket disconnected during /responses")
    except Exception as e:
        logger.error(f"Error in websocket create_response: {str(e)}")
        if websocket.client_state.name == "CONNECTED":
            await websocket.send_text(json.dumps({"type": "error", "error": {"message": str(e)}}))
            await websocket.close(code=1011)


@app.post("/responses")
async def create_response(request: Request):
    """
    Create a response in Responses API format, translating to/from chat.completions API.
    """
    try:
        logger.info("Received request to /responses")
        request_data = await request.json()
        
        # Log basic request information
        logger.info(f"Received request: model={request_data.get('model')}, stream={request_data.get('stream')}")
        
        # Log input content for better visibility
        if "input" in request_data and request_data["input"]:
            logger.info("==== REQUEST CONTENT ====")
            #     "input": [{"role": "user", "content": [{"type": "input_text", "text": "save a file with \"demo2\" text called \"demo2.md\""}], "type": "message"}],
            for i, item in enumerate(request_data["input"]):
                if isinstance(item, dict):
                    if item.get("type") == "message" and item.get("role") == "user":
                        if "content" in item and isinstance(item["content"], list):
                            for index, content_item in enumerate(item["content"]):
                                if isinstance(content_item, dict):
                                    # Handle nested content structure like {"type": "input_text", "text": "actual message"}
                                    if content_item.get("type") == "input_text" and "text" in content_item:
                                        user_text = content_item.get("text", "")
                                        logger.info(f"USER INPUT: {user_text}")
                                    elif content_item.get("type") == "text" and "text" in content_item:
                                        user_text = content_item.get("text", "")
                                        logger.info(f"USER INPUT: {user_text}")
                                    # Handle other content types
                                    elif "type" in content_item:
                                        logger.info(f"USER INPUT ({content_item.get('type')}): {str(content_item)[:100]}...")
                                elif isinstance(content_item, str):
                                    logger.info(f"USER INPUT: {content_item}")
                    elif item.get("type") == "function_call_output":
                        logger.info(f"FUNCTION RESULT: call_id={item.get('call_id')}, output={str(item.get('output', ''))[:100]}...")
                elif isinstance(item, str):
                    logger.info(f"USER INPUT: {item}")
            logger.info("=======================")

        chat_request = _build_chat_request(request_data)
        
        # Check for streaming mode
        stream = request_data.get("stream", False)
        
        if stream:
            logger.info("Handling streaming response")
            # Handle streaming response
            async def stream_response():
                try:
                    async for event in _stream_responses_events(chat_request):
                        yield event
                except Exception as e:
                    logger.error(f"Error in stream_response: {str(e)}")
                    yield f"data: {json.dumps({'type': 'error', 'error': {'message': str(e)}})}\n\n"
            
            return StreamingResponse(
                stream_response(),
                media_type="text/event-stream"
            )
        
        else:
            logger.info("Non-streaming response unsupported")
            raise HTTPException(
                status_code=501,
                detail="Non-streaming responses are not supported on /responses. Set stream=True."
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_response: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        )


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """
    Endpoint for /v1/chat/completions, delegating to the service.
    """
    logger.info("Handling chat completions")
    response = await handle_chat_completions(request)
    logger.info("Chat completions handled")
    return response


@app.get("/health")
async def health_check():
    return {"status": "ok", "adapter": "running"}

@app.get("/")
async def root():
    return {"message": "Open Responses Server is running."}

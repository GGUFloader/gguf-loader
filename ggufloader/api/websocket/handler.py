"""WebSocket handler for real-time streaming.

Sends typed events to the React frontend:
- token: Streaming text tokens
- reasoning: Thinking/reasoning tokens
- tool_call: Tool call started
- tool_result: Tool call result
- approval_needed: Approval request
- message_complete: Full message done
- agent_complete: Agent run finished
- heartbeat: Keepalive
- error: Error occurred
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Optional

from fastapi import WebSocket, WebSocketDisconnect

from ggufloader.api.deps import get_model_backend
from ggufloader.api.routes.agent import update_plan_state

logger = logging.getLogger(__name__)

# Heartbeat interval in seconds
HEARTBEAT_INTERVAL = 30


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self._heartbeat_tasks: dict[WebSocket, asyncio.Task] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket connected. Total: %d", len(self.active_connections))
        # Start heartbeat
        self._heartbeat_tasks[websocket] = asyncio.create_task(
            self._heartbeat_loop(websocket)
        )

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        # Cancel heartbeat
        task = self._heartbeat_tasks.pop(websocket, None)
        if task and not task.done():
            task.cancel()
        logger.info("WebSocket disconnected. Total: %d", len(self.active_connections))

    async def _heartbeat_loop(self, websocket: WebSocket):
        """Send periodic heartbeats to keep connection alive."""
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                try:
                    await websocket.send_json({"type": "heartbeat", "ts": time.time()})
                except Exception:
                    break
        except asyncio.CancelledError:
            pass

    async def send_event(self, websocket: WebSocket, event: dict):
        try:
            await websocket.send_json(event)
        except Exception:
            self.disconnect(websocket)


manager = ConnectionManager()

# Store pending approvals so the WebSocket can wait for a response
_pending_approvals: dict[str, asyncio.Future] = {}


async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for chat streaming."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            event_type = data.get("type", "")

            if event_type in ("chat", "chat_message"):
                await handle_chat(websocket, data)
            elif event_type == "agent_start":
                await handle_agent_start(websocket, data)
            elif event_type == "agent_stop":
                await handle_agent_stop(websocket)
            elif event_type == "approve":
                await handle_approval_response(data)
            elif event_type == "ping":
                await manager.send_event(websocket, {"type": "pong", "ts": time.time()})
            else:
                await manager.send_event(websocket, {
                    "type": "error",
                    "message": f"Unknown event type: {event_type}",
                })
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("WebSocket error: %s", e, exc_info=True)
    finally:
        manager.disconnect(websocket)


async def handle_chat(websocket: WebSocket, data: dict):
    """Handle chat message with streaming."""
    backend = get_model_backend()
    if backend is None:
        await manager.send_event(websocket, {
            "type": "error",
            "message": "No model loaded. Please load a model first.",
        })
        return

    message = data.get("message", "")
    if not message.strip():
        await manager.send_event(websocket, {
            "type": "error",
            "message": "Empty message",
        })
        return

    session_id = data.get("session_id")
    system_prompt = data.get("system_prompt")
    temperature = data.get("temperature", 0.2)
    max_tokens = data.get("max_tokens", 4096)

    # Build messages
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": message})

    message_id = f"msg_{int(time.time() * 1000)}"
    start_time = time.time()

    try:
        # Check if backend supports streaming
        if hasattr(backend, "generate_stream"):
            await _stream_response(websocket, backend, messages, message_id, start_time, temperature, max_tokens)
        else:
            await _generate_response(websocket, backend, messages, message_id, start_time, temperature, max_tokens)

    except Exception as e:
        logger.error("Chat generation failed: %s", e, exc_info=True)
        await manager.send_event(websocket, {
            "type": "error",
            "message": str(e),
        })


async def _stream_response(websocket, backend, messages, message_id, start_time, temperature, max_tokens):
    """Stream response token by token."""
    loop = asyncio.get_event_loop()

    def token_generator():
        """Generator that yields tokens from the backend."""
        for token in backend.chat_stream(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            yield token

    # Send tokens as they arrive
    full_response = []
    buffer = []

    def process_tokens():
        """Process tokens in a thread."""
        for token in token_generator():
            full_response.append(token)
            buffer.append(token)
            # Yield control periodically
            if len(buffer) >= 3:
                yield "".join(buffer)
                buffer.clear()
        # Flush remaining
        if buffer:
            yield "".join(buffer)

    # Run in executor and send tokens
    gen = process_tokens()
    try:
        while True:
            token_batch = await loop.run_in_executor(None, next, gen, _SENTINEL)
            if token_batch is _SENTINEL:
                break
            await manager.send_event(websocket, {
                "type": "token",
                "token": token_batch,
                "message_id": message_id,
            })
    except StopIteration:
        pass

    content = "".join(full_response)
    duration_ms = int((time.time() - start_time) * 1000)

    await manager.send_event(websocket, {
        "type": "message_complete",
        "message_id": message_id,
        "content": content,
        "tokens_used": len(content.split()),
        "duration_ms": duration_ms,
    })


# Sentinel for the generator
_SENTINEL = object()


async def _generate_response(websocket, backend, messages, message_id, start_time, temperature, max_tokens):
    """Non-streaming fallback: generate entire response at once."""
    loop = asyncio.get_event_loop()

    def generate():
        return backend.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    response = await loop.run_in_executor(None, generate)
    duration_ms = int((time.time() - start_time) * 1000)

    await manager.send_event(websocket, {
        "type": "message_complete",
        "message_id": message_id,
        "content": response,
        "tokens_used": len(response.split()),
        "duration_ms": duration_ms,
    })


async def handle_agent_start(websocket: WebSocket, data: dict):
    """Start agent execution with structured phase streaming."""
    preset = data.get("preset", "standard")
    message = data.get("message", "")
    system_prompt = data.get("system_prompt")
    temperature = data.get("temperature", 0.2)
    max_tokens = data.get("max_tokens", 4096)

    await manager.send_event(websocket, {
        "type": "agent_started",
        "preset": preset,
    })

    if not message.strip():
        await manager.send_event(websocket, {
            "type": "error",
            "message": "Empty message",
        })
        return

    backend = get_model_backend()
    if backend is None:
        await manager.send_event(websocket, {
            "type": "error",
            "message": "No model loaded. Please load a model first.",
        })
        return

    message_id = f"agent_{int(time.time() * 1000)}"
    start_time = time.time()

    try:
        # Import agent engine
        from ggufloader.core.agent.agent_engine import AgentEngine, extract_json

        # Build LLM callable from backend
        def llm_call(prompt, max_tokens=2048, temperature=0.2):
            """Synchronous LLM call for the agent engine."""
            messages = [{"role": "user", "content": prompt}]
            if system_prompt:
                messages.insert(0, {"role": "system", "content": system_prompt})
            # Use non-streaming generate
            if hasattr(backend, "chat"):
                return backend.chat(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            # Fallback: collect streaming tokens
            result = []
            for token in backend.chat_stream(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                result.append(token)
            return "".join(result)

        # Create agent engine
        workspace = data.get("workspace", ".")
        agent = AgentEngine(
            llm=llm_call,
            workspace=workspace,
            max_tokens=max_tokens,
            max_steps=8,
        )

        # Callbacks that stream phase/plan events via WebSocket
        loop = asyncio.get_event_loop()

        def on_status(msg: str):
            """Send phase status events to the frontend."""
            # Detect phase from status prefix
            phase = None
            if msg.startswith("🎯"):
                phase = "goal"
            elif msg.startswith("📋"):
                phase = "plan"
            elif msg.startswith("▶"):
                phase = "execute"
            elif msg.startswith("🔍"):
                phase = "verify"
            elif msg.startswith("✅"):
                phase = "continue"
            elif msg.startswith("📝"):
                phase = "finish"

            # Determine current plan step if in execute phase
            plan_step = None
            if msg.startswith("▶ Step "):
                import re as _re
                m = _re.match(r"▶ Step (\d+)/(\d+): (.+)", msg)
                if m:
                    plan_step = {
                        "current": int(m.group(1)),
                        "total": int(m.group(2)),
                        "description": m.group(3),
                    }

            event = {
                "type": "agent_phase",
                "message_id": message_id,
                "status": msg,
            }
            if phase:
                event["phase"] = phase
            if plan_step:
                event["plan_step"] = plan_step

            # Update the REST-accessible plan state
            update_plan_state(
                phase=phase or _current_phase,
                plan_step=plan_step,
            )

            asyncio.run_coroutine_threadsafe(
                manager.send_event(websocket, event),
                loop,
            )

        def on_tool(result: dict):
            """Send tool result events to the frontend."""
            asyncio.run_coroutine_threadsafe(
                manager.send_event(websocket, {
                    "type": "tool_result",
                    "message_id": message_id,
                    "tool": result.get("tool_name", "unknown"),
                    "success": result.get("status") == "success",
                    "result": result.get("content", result.get("error", ""))[:500],
                }),
                loop,
            )

        def on_plan_update(data: dict):
            """Send plan step updates to the frontend in real time."""
            asyncio.run_coroutine_threadsafe(
                manager.send_event(websocket, {
                    "type": "agent_plan_update",
                    "message_id": message_id,
                    "phase": data.get("phase", "idle"),
                    "plan": data.get("plan", []),
                    "step": data.get("step"),
                    "step_status": data.get("status"),
                }),
                loop,
            )

        # Run the agent engine in a thread (it's synchronous)
        result = await loop.run_in_executor(
            None,
            lambda: agent.process(
                user_message=message,
                on_status=on_status,
                on_tool=on_tool,
                on_plan_update=on_plan_update,
            ),
        )

        # Send the final response with plan + phase_log
        plan_data = result.get("plan", [])
        phase_log_data = result.get("phase_log", [])

        await manager.send_event(websocket, {
            "type": "message_complete",
            "message_id": message_id,
            "content": result.get("response", ""),
            "tokens_used": len(result.get("response", "").split()),
            "duration_ms": int((time.time() - start_time) * 1000),
            "plan": plan_data,
            "phase_log": phase_log_data,
        })

        await manager.send_event(websocket, {
            "type": "agent_complete",
            "message_id": message_id,
            "plan": plan_data,
            "phase_log": phase_log_data,
        })

        # Update REST-accessible state with final plan
        update_plan_state(
            phase="idle",
            plan=plan_data,
            phase_log=phase_log_data,
        )

    except Exception as e:
        logger.error("Agent execution failed: %s", e, exc_info=True)
        await manager.send_event(websocket, {
            "type": "error",
            "message": f"Agent error: {e}",
        })


async def handle_agent_stop(websocket: WebSocket):
    """Stop agent execution."""
    await manager.send_event(websocket, {
        "type": "agent_stopped",
    })


async def handle_approval_response(data: dict):
    """Handle tool call approval response."""
    call_id = data.get("call_id", "")
    approved = data.get("approved", False)

    # Resolve the pending approval future
    future = _pending_approvals.pop(call_id, None)
    if future and not future.done():
        future.set_result(approved)

    # Broadcast to all connections
    for conn in manager.active_connections:
        await manager.send_event(conn, {
            "type": "approval_response",
            "call_id": call_id,
            "approved": approved,
        })


async def request_approval(tool_name: str, args: dict, timeout: float = 60.0) -> bool:
    """Request user approval for a tool call. Returns True if approved."""
    call_id = f"approval_{int(time.time() * 1000)}"

    # Create a future to wait for the response
    loop = asyncio.get_event_loop()
    future = loop.create_future()
    _pending_approvals[call_id] = future

    # Send approval request to all connections
    for conn in manager.active_connections:
        await manager.send_event(conn, {
            "type": "tool_approval",
            "id": call_id,
            "tool": tool_name,
            "args": args,
        })

    try:
        approved = await asyncio.wait_for(future, timeout=timeout)
        return approved
    except asyncio.TimeoutError:
        _pending_approvals.pop(call_id, None)
        return False

"""WebSocket handler for real-time streaming.

Sends typed events to the React frontend:
- token: Streaming text tokens
- reasoning: Thinking/reasoning tokens
- tool_call: Tool call started
- tool_result: Tool call result
- tool_approval: Approval request (blocks agent until response)
- message_complete: Full message done
- agent_complete: Agent run finished
- agent_started / agent_stopped: Lifecycle events
- agent_phase: Phase transitions (goal → plan → execute → verify → finish)
- agent_plan_update: Real-time plan step status
- heartbeat: Keepalive
- error: Error occurred
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
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

# ---------------------------------------------------------------------------
# Approval flow: bridges agent thread ↔ async WebSocket
# ---------------------------------------------------------------------------

# GraphAgent approval: agent thread blocks on an asyncio.Event, frontend
# resolves it via handle_approval_response.
_approval_events: dict[str, asyncio.Event] = {}
_approval_results: dict[str, bool] = {}

# Legacy REST approval (kept for backward compat with addons)
_pending_approvals: dict[str, asyncio.Future] = {}

# Active agent graph for cancellation
_agent_graph: Any = None


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
            elif event_type in ("approve", "approval_response"):
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


# ---------------------------------------------------------------------------
# Chat (unchanged from original)
# ---------------------------------------------------------------------------

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
        if hasattr(backend, "generate_stream"):
            await _stream_response(websocket, backend, messages, message_id, start_time, temperature, max_tokens)
        else:
            await _generate_response(websocket, backend, messages, message_id, start_time, temperature, max_tokens)
    except Exception as e:
        logger.error("Chat generation failed: %s", e, exc_info=True)
        await manager.send_event(websocket, {"type": "error", "message": str(e)})


_SENTINEL = object()


async def _stream_response(websocket, backend, messages, message_id, start_time, temperature, max_tokens):
    """Stream response token by token."""
    loop = asyncio.get_event_loop()

    def token_generator():
        for token in backend.chat_stream(
            messages=messages, temperature=temperature, max_tokens=max_tokens,
        ):
            yield token

    full_response = []
    buffer = []

    def process_tokens():
        for token in token_generator():
            full_response.append(token)
            buffer.append(token)
            if len(buffer) >= 3:
                yield "".join(buffer)
                buffer.clear()
        if buffer:
            yield "".join(buffer)

    gen = process_tokens()
    try:
        while True:
            token_batch = await loop.run_in_executor(None, next, gen, _SENTINEL)
            if token_batch is _SENTINEL:
                break
            await manager.send_event(websocket, {
                "type": "token", "token": token_batch, "message_id": message_id,
            })
    except StopIteration:
        pass

    content = "".join(full_response)
    duration_ms = int((time.time() - start_time) * 1000)
    await manager.send_event(websocket, {
        "type": "message_complete", "message_id": message_id,
        "content": content, "tokens_used": len(content.split()), "duration_ms": duration_ms,
    })


async def _generate_response(websocket, backend, messages, message_id, start_time, temperature, max_tokens):
    """Non-streaming fallback."""
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None, lambda: backend.chat(messages=messages, temperature=temperature, max_tokens=max_tokens)
    )
    duration_ms = int((time.time() - start_time) * 1000)
    await manager.send_event(websocket, {
        "type": "message_complete", "message_id": message_id,
        "content": response, "tokens_used": len(response.split()), "duration_ms": duration_ms,
    })


# ---------------------------------------------------------------------------
# Agent execution (rewritten to use GraphAgent + presets + router)
# ---------------------------------------------------------------------------

async def handle_agent_start(websocket: WebSocket, data: dict):
    """Start agent execution using GraphAgent with full capability wiring.

    Receives from frontend:
      - message: user text
      - workspace: folder path for sandboxed tools
      - preset: agent preset ID (research/code_review/refactor/debug/full_stack/quick_fix)
      - model_path: path to loaded GGUF (for router optimization)
      - system_prompt: optional custom system prompt
      - temperature / max_tokens: sampling overrides
    """
    global _agent_graph

    message = data.get("message", "")
    workspace = data.get("workspace", ".")
    preset_id = data.get("preset", "full_stack")
    model_path = data.get("model_path")
    system_prompt = data.get("system_prompt")
    temperature = data.get("temperature", 0.2)
    max_tokens = data.get("max_tokens", 4096)

    await manager.send_event(websocket, {
        "type": "agent_started", "preset": preset_id, "workspace": workspace,
    })

    if not message.strip():
        await manager.send_event(websocket, {"type": "error", "message": "Empty message"})
        return

    backend = get_model_backend()
    if backend is None:
        await manager.send_event(websocket, {
            "type": "error", "message": "No model loaded. Please load a model first.",
        })
        return

    message_id = f"agent_{int(time.time() * 1000)}"
    start_time = time.time()

    try:
        # --- 1. Load preset ---
        from ggufloader.core.agent.presets import PresetManager
        from ggufloader.core.agent.agent_engine import _SYSTEM_PROMPT

        pm = PresetManager()
        preset_obj = pm.get(preset_id) or pm.get("full_stack")

        # --- 2. Get router-optimized agent params ---
        agent_temperature = preset_obj.temperature
        agent_max_tokens = preset_obj.max_tokens
        router_info = {}

        if model_path:
            try:
                from ggufloader.core.router import ModelRouter, ModelRole
                router = ModelRouter()
                profile = router.inspect(model_path)
                role_config = router.route(profile, ModelRole.AGENT)
                # Use router's agent params but respect preset overrides
                agent_temperature = role_config.temperature
                agent_max_tokens = role_config.max_tokens
                router_info = {
                    "family": profile.family,
                    "size_tier": profile.size_tier.value,
                    "architecture": profile.architecture,
                }
            except Exception as e:
                logger.debug("Router inspection failed, using preset defaults: %s", e)

        # --- 3. Build LLM callable with preset system prompt ---
        def llm_call(prompt, max_tokens=None, temperature=None):
            """Synchronous LLM call for the graph agent."""
            full_sys = preset_obj.get_system_prompt(_SYSTEM_PROMPT)
            if system_prompt:
                full_sys = system_prompt + "\n\n" + full_sys
            msgs = [
                {"role": "system", "content": full_sys},
                {"role": "user", "content": prompt},
            ]
            return backend.chat(
                messages=msgs,
                temperature=temperature or agent_temperature,
                max_tokens=max_tokens or agent_max_tokens,
            )

        # --- 4. Create GraphAgent (with checkpointing + cancellation) ---
        from ggufloader.core.agent.graph_agent import GraphAgent

        # Checkpoint path for session persistence across restarts
        import os as _os
        checkpoint_dir = _os.path.join(_os.path.expanduser("~"), ".ggufloader", "agent_checkpoints")
        _os.makedirs(checkpoint_dir, exist_ok=True)
        workspace_hash = hashlib.sha256(_os.path.abspath(workspace).encode()).hexdigest()[:16]
        checkpoint_path = _os.path.join(checkpoint_dir, f"{workspace_hash}.db")

        agent = GraphAgent(
            llm=llm_call,
            workspace=workspace,
            max_steps=preset_obj.max_steps,
            max_tokens=agent_max_tokens,
            json_retries=2,
            checkpoint_path=checkpoint_path,
        )
        _agent_graph = agent

        # --- 5. Wire callbacks ---
        loop = asyncio.get_event_loop()

        def on_status(msg: str):
            """Send phase status events to the frontend."""
            phase = None
            if msg.startswith("🤔") or msg.startswith("🎯"):
                phase = "goal"
            elif msg.startswith("📋"):
                phase = "plan"
            elif msg.startswith("▶") or msg.startswith("→"):
                phase = "execute"
            elif msg.startswith("🔍"):
                phase = "verify"
            elif msg.startswith("✅") or msg.startswith("📖"):
                phase = "continue"
            elif msg.startswith("📝"):
                phase = "finish"

            plan_step = None
            if msg.startswith("▶ Step "):
                m = re.match(r"▶ Step (\d+)/(\d+): (.+)", msg)
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
                "preset": preset_id,
            }
            if phase:
                event["phase"] = phase
            if plan_step:
                event["plan_step"] = plan_step

            update_plan_state(phase=phase or "idle", plan_step=plan_step)

            asyncio.run_coroutine_threadsafe(
                manager.send_event(websocket, event), loop,
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
                    "call_id": result.get("call_id", ""),
                }), loop,
            )

        def on_token(chunk: str):
            """Forward streaming tokens from agent's final answer."""
            asyncio.run_coroutine_threadsafe(
                manager.send_event(websocket, {
                    "type": "token",
                    "token": chunk,
                    "message_id": message_id,
                }), loop,
            )

        def on_approval(payload: dict) -> bool:
            """Block agent thread, send approval request, wait for frontend response.

            Called by GraphAgent when a tool requires approval (run_command, git write, etc.).
            The agent thread blocks here until the frontend sends an 'approve' event.
            """
            call_id = f"approval_{int(time.time() * 1000)}"
            event = asyncio.Event()
            _approval_events[call_id] = event

            # Send approval request to frontend
            call = payload.get("call", {})
            asyncio.run_coroutine_threadsafe(
                manager.send_event(websocket, {
                    "type": "tool_approval",
                    "id": call_id,
                    "tool": call.get("tool", "unknown"),
                    "args": call.get("parameters", {}),
                    "description": payload.get("description", ""),
                    "workspace": payload.get("workspace", workspace),
                }), loop,
            )

            # Block agent thread until frontend responds (max 120s)
            try:
                event.wait(timeout=120)
            except Exception:
                pass

            approved = _approval_results.pop(call_id, False)
            _approval_events.pop(call_id, None)
            return approved

        # --- 6. Run the graph agent in a thread ---
        result = await loop.run_in_executor(
            None,
            lambda: agent.process(
                user_message=message,
                on_status=on_status,
                on_tool=on_tool,
                on_token=on_token,
                on_approval=on_approval,
            ),
        )

        # --- 7. Send final response ---
        plan_data = result.get("plan", [])
        phase_log_data = result.get("phase_log", [])
        was_cancelled = result.get("cancelled", False)

        await manager.send_event(websocket, {
            "type": "message_complete",
            "message_id": message_id,
            "content": result.get("response", ""),
            "tokens_used": len(result.get("response", "").split()),
            "duration_ms": int((time.time() - start_time) * 1000),
            "plan": plan_data,
            "phase_log": phase_log_data,
            "cancelled": was_cancelled,
            "preset": preset_id,
            "router": router_info,
        })

        await manager.send_event(websocket, {
            "type": "agent_complete",
            "message_id": message_id,
            "plan": plan_data,
            "phase_log": phase_log_data,
            "cancelled": was_cancelled,
            "tool_results": result.get("tool_results", []),
        })

        update_plan_state(phase="idle", plan=plan_data, phase_log=phase_log_data)

    except Exception as e:
        logger.error("Agent execution failed: %s", e, exc_info=True)
        await manager.send_event(websocket, {
            "type": "error", "message": f"Agent error: {e}",
        })
    finally:
        _agent_graph = None


# ---------------------------------------------------------------------------
# Agent stop (cancels running GraphAgent)
# ---------------------------------------------------------------------------

async def handle_agent_stop(websocket: WebSocket):
    """Stop agent execution by cancelling the running graph."""
    global _agent_graph
    if _agent_graph is not None:
        try:
            _agent_graph.cancel()
            logger.info("Agent cancelled by user")
        except Exception as e:
            logger.warning("Agent cancel failed: %s", e)
        _agent_graph = None
    await manager.send_event(websocket, {"type": "agent_stopped"})


# ---------------------------------------------------------------------------
# Approval response (resolves the blocking event from on_approval)
# ---------------------------------------------------------------------------

async def handle_approval_response(data: dict):
    """Handle tool call approval response from frontend."""
    call_id = data.get("call_id") or data.get("id", "")
    approved = data.get("approved", False)

    # 1. Resolve GraphAgent approval (event-based)
    event = _approval_events.pop(call_id, None)
    _approval_results[call_id] = approved
    if event:
        event.set()

    # 2. Resolve legacy REST approval (future-based)
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


# ---------------------------------------------------------------------------
# Legacy approval (kept for addons)
# ---------------------------------------------------------------------------

async def request_approval(tool_name: str, args: dict, timeout: float = 60.0) -> bool:
    """Request user approval for a tool call. Returns True if approved."""
    call_id = f"approval_{int(time.time() * 1000)}"
    loop = asyncio.get_event_loop()
    future = loop.create_future()
    _pending_approvals[call_id] = future

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

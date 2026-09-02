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
- agent_phase: Phase transitions (goal -> plan -> execute -> verify -> finish)
- agent_plan_update: Real-time plan step status
- heartbeat: Keepalive
- error: Error occurred
"""

from __future__ import annotations

import asyncio
from pathlib import Path
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
# Approval flow: bridges agent thread <-> async WebSocket
# ---------------------------------------------------------------------------

# Approval manager (instance-based, replaces global mutable state)
from ggufloader.core.agent.approval_manager import ApprovalManager
_approval_mgr = ApprovalManager()

def get_approval_manager() -> ApprovalManager:
    """Return the global approval manager (used by AgentTransport)."""
    return _approval_mgr

# Legacy REST approval (kept for backward compat with addons)
_pending_approvals: dict[str, asyncio.Future] = {}

# Active agent graph for cancellation
_agent_graph: Any = None


class WSTransport:
    """Adapter that implements the Transport protocol for a single WebSocket.

    AgentTransport expects send_event(event), but ConnectionManager.send_event
    needs (websocket, event). This adapter bridges the gap.
    """

    def __init__(self, mgr: ConnectionManager, ws: WebSocket):
        self._mgr = mgr
        self._ws = ws

    async def send_event(self, event: dict):
        await self._mgr.send_event(self._ws, event)


async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for chat streaming."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            event_type = data.get("type", "")

            if event_type in ("chat", "chat_message", "agent_start"):
                # All messages go through the agent
                data["type"] = "agent_start"
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
    temperature = data.get("temperature", 0.7)
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
        

        pm = PresetManager()
        preset_obj = pm.get(preset_id) or pm.get("full_stack")

        # --- 2. Router is the SINGLE source for model settings ---
        # Router provides: system_prompt, temperature, top_k, top_p, repeat_penalty, max_tokens
        # Preset provides: mode instructions, tool restrictions, step limits
        router_info = {}
        router_system_prompt = None
        router_task_prompts = {}
        agent_temperature = 0.1  # safe default
        agent_max_tokens = 4096
        agent_top_k = 40
        agent_top_p = 0.9
        agent_repeat_penalty = 1.1

        if model_path:
            try:
                from ggufloader.core.router import ModelRouter, ModelRole
                router = ModelRouter()
                profile = router.inspect(model_path)
                role_config = router.route(profile, ModelRole.AGENT)
                agent_temperature = role_config.temperature
                agent_max_tokens = role_config.max_tokens
                agent_top_k = role_config.top_k
                agent_top_p = role_config.top_p
                agent_repeat_penalty = role_config.repeat_penalty
                router_system_prompt = role_config.system_prompt
                router_task_prompts = role_config.task_prompts
                router_info = {
                    "family": profile.family,
                    "size_tier": profile.size_tier.value,
                    "architecture": profile.architecture,
                }
            except Exception as e:
                logger.debug("Router inspection failed, using safe defaults: %s", e)

        # Preset adds MODE context on top of router settings
        preset_prompt_addition = preset_obj.system_prompt_addition or ""
        preset_allowed = preset_obj.allowed_tools if preset_obj.allowed_tools else None
        preset_blocked = preset_obj.blocked_tools if preset_obj.blocked_tools else None

        def llm_call(prompt, max_tokens=None, temperature=None):
            """Synchronous LLM call for the graph agent."""
            return backend(
                prompt,
                max_tokens=max_tokens or agent_max_tokens,
                temperature=temperature or agent_temperature,
                top_k=agent_top_k,
                top_p=agent_top_p,
                repeat_penalty=agent_repeat_penalty,
            )

        # --- 4. Create GraphAgent (with checkpointing + cancellation) ---
        from ggufloader.core.agent.graph_agent import GraphAgent

        # Each session gets a unique thread_id -- no history carryover.
        # This keeps the prompt small and fast.
        unique_thread_id = f"session_{int(time.time() * 1000)}"

        # Get actual context size from model backend
        try:
            backend_ref = get_model_backend()
            actual_n_ctx = backend_ref.n_ctx if backend_ref else agent_max_tokens
        except Exception:
            actual_n_ctx = agent_max_tokens

        # Combine router prompt + preset addition
        full_system_prompt = router_system_prompt or system_prompt or ""
        if preset_prompt_addition:
            full_system_prompt = full_system_prompt + chr(10) + chr(10) + preset_prompt_addition
        
        agent = GraphAgent(
            llm=llm_call,
            workspace=workspace,
            max_steps=preset_obj.max_steps,
            max_tokens=agent_max_tokens,
            n_ctx=actual_n_ctx,
            json_retries=2,
            thread_id=unique_thread_id,
            system_prompt=full_system_prompt or None,
            task_prompts=router_task_prompts or None,
            allowed_tools=preset_allowed,
            blocked_tools=preset_blocked,
        )
        _agent_graph = agent

        # --- 5. Wire callbacks via AgentTransport (3 lines instead of 150+) ---
        loop = asyncio.get_event_loop()
        from ggufloader.core.agent.agent_transport import AgentTransport
        ws_transport = WSTransport(manager, websocket)
        transport = AgentTransport(ws_transport, loop, message_id, preset_id)

        # --- 6. Run the graph agent in a thread ---
        def on_plan_update(phase: str, plan: list):
            """Send plan to frontend when created."""
            try:
                asyncio.run_coroutine_threadsafe(
                    manager.send_event(websocket, {
                        "type": "agent_plan_update",
                        "message_id": message_id,
                        "phase": phase,
                        "plan": plan,
                        "goal": plan[0].get("description", "") if plan else "",
                    }),
                    loop,
                )
            except Exception:
                pass

        result = await loop.run_in_executor(
            None,
            lambda: agent.process(
                user_message=message,
                on_status=transport.make_status_callback(),
                on_tool=transport.make_tool_callback(),
                on_token=transport.make_token_callback(),
                on_approval=transport.make_approval_callback(workspace),
                on_plan=on_plan_update,
            ),
        )

        # --- 7. Send final response ---
        plan_data = result.get("plan", [])
        phase_log_data = result.get("phase_log", [])
        was_cancelled = result.get("cancelled", False)

        response_content = result.get("response", "") or "Done."
        await manager.send_event(websocket, {
            "type": "message_complete",
            "message_id": message_id,
            "content": response_content,
            "tokens_used": len(response_content.split()),
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
    _approval_mgr.resolve(call_id, approved)

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

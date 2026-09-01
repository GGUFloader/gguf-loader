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
        from ggufloader.core.agent.agent_engine import _SYSTEM_PROMPT

        pm = PresetManager()
        preset_obj = pm.get(preset_id) or pm.get("full_stack")

        # --- 2. Get router-optimized agent params (single call) ---
        agent_temperature = preset_obj.temperature
        agent_max_tokens = preset_obj.max_tokens
        agent_top_k = 40
        agent_top_p = 0.9
        agent_repeat_penalty = 1.05
        router_info = {}
        router_system_prompt = None

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
                router_info = {
                    "family": profile.family,
                    "size_tier": profile.size_tier.value,
                    "architecture": profile.architecture,
                }
            except Exception as e:
                logger.debug("Router inspection failed, using preset defaults: %s", e)

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

        agent = GraphAgent(
            llm=llm_call,
            workspace=workspace,
            max_steps=preset_obj.max_steps,
            max_tokens=agent_max_tokens,
            n_ctx=actual_n_ctx,
            json_retries=2,
            thread_id=unique_thread_id,
        )
        _agent_graph = agent

        # --- 5. Wire callbacks ---
        loop = asyncio.get_event_loop()

        def on_status(msg: str):
            """Send phase status events to the frontend.

            Now also emits progress_* events so the StepProgressPanel can
            render a Codebuff-style step-by-step view instead of a wall of
            'Thinking' blocks.
            """
            phase = None
            if msg.startswith("...") or msg.startswith("[target]"):
                phase = "goal"
            elif msg.startswith("[checklist]"):
                phase = "plan"
            elif msg.startswith(">") or msg.startswith("->"):
                phase = "execute"
            elif msg.startswith("[search]"):
                phase = "verify"
            elif msg.startswith("[ok]") or msg.startswith("[reading]"):
                phase = "continue"
            elif msg.startswith("[note]"):
                phase = "finish"

            plan_step = None
            if msg.startswith("> Step "):
                m = re.match(r"> Step (\d+)/(\d+): (.+)", msg)
                if m:
                    plan_step = {
                        "current": int(m.group(1)),
                        "total": int(m.group(2)),
                        "description": m.group(3),
                    }

            # --- Legacy agent_phase event (kept for PlanTracker) ---
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

            # --- Progress events for StepProgressPanel ---
            stripped = msg.strip()
            if not stripped:
                return

            # Announce what the agent is about to do (thinking/analysis/reasoning)
            if stripped.startswith("...") or stripped.startswith("[!]") or stripped.startswith("..."):
                # Clean emoji prefix for display
                clean = stripped.lstrip("...[!]...[checklist][search][ok][note][target]>>  \n")
                if clean:
                    asyncio.run_coroutine_threadsafe(
                        manager.send_event(websocket, {
                            "type": "progress_announce",
                            "content": clean,
                        }), loop,
                    )

            # Tool call being executed
            elif re.match(r"^\[\d+/\d+\]", stripped) or stripped.startswith("-> "):
                # e.g. "[1/3] list_directory ." or "-> List files in ."
                tool_desc = re.sub(r"^\[\d+/\d+\]\s*", "", stripped)
                tool_desc = tool_desc.lstrip("-> ")
                asyncio.run_coroutine_threadsafe(
                    manager.send_event(websocket, {
                        "type": "progress_tool_call",
                        "name": tool_desc.split(" ")[0] if tool_desc else "tool",
                        "content": tool_desc,
                    }), loop,
                )

            # Tool result (success)
            elif stripped.startswith("[ok]") or stripped.startswith("  [ok]"):
                result_text = stripped.lstrip("[ok] ")
                asyncio.run_coroutine_threadsafe(
                    manager.send_event(websocket, {
                        "type": "progress_tool_result",
                        "content": result_text,
                        "success": True,
                    }), loop,
                )

            # Tool result (failure)
            elif stripped.startswith("[FAIL]") or stripped.startswith("  [FAIL]"):
                result_text = stripped.lstrip("[FAIL] ")
                asyncio.run_coroutine_threadsafe(
                    manager.send_event(websocket, {
                        "type": "progress_tool_result",
                        "content": result_text,
                        "success": False,
                    }), loop,
                )

            # Approval needed
            elif stripped.startswith("[lock]"):
                asyncio.run_coroutine_threadsafe(
                    manager.send_event(websocket, {
                        "type": "progress_announce",
                        "content": stripped,
                    }), loop,
                )

            # Step indicator (plan step)
            elif stripped.startswith("> Step "):
                asyncio.run_coroutine_threadsafe(
                    manager.send_event(websocket, {
                        "type": "progress_step_complete",
                        "content": stripped,
                    }), loop,
                )

            # Other status messages (plan creation, verification, etc.)
            elif stripped.startswith("Plan") or stripped.startswith("All plan") or stripped.startswith("Verif"):
                asyncio.run_coroutine_threadsafe(
                    manager.send_event(websocket, {
                        "type": "progress_step_complete",
                        "content": stripped,
                    }), loop,
                )

            # Generic status -- still emit as announce so it shows up
            else:
                asyncio.run_coroutine_threadsafe(
                    manager.send_event(websocket, {
                        "type": "progress_announce",
                        "content": stripped,
                    }), loop,
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

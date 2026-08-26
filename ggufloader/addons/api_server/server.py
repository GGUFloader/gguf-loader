"""OpenAI-compatible HTTP server core (stdlib only, no FastAPI dep)."""

from __future__ import annotations

import json
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, Optional


def _json_response(handler: BaseHTTPRequestHandler, data: Any, status: int = 200):
    body = json.dumps(data).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _sse_headers(handler: BaseHTTPRequestHandler):
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream")
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Connection", "keep-alive")
    handler.end_headers()


def make_handler(get_backend: Callable[[], Any], get_model_id: Callable[[], str]):
    """Factory returning a BaseHTTPRequestHandler subclass bound to getters."""

    class ApiHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            # Suppress default stderr logging; use app logger if needed
            pass

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.end_headers()

        def do_GET(self):
            if self.path in ("/v1/models", "/v1/models/"):
                model_id = get_model_id()
                _json_response(self, {
                    "object": "list",
                    "data": [{
                        "id": model_id,
                        "object": "model",
                        "created": int(time.time()),
                        "owned_by": "user",
                    }],
                })
            elif self.path == "/health":
                _json_response(self, {"status": "ok"})
            else:
                _json_response(self, {"error": {"message": "Not found", "type": "not_found"}}, 404)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw.decode() or "{}")
            except Exception:
                _json_response(self, {"error": {"message": "Invalid JSON"}}, 400)
                return

            if self.path == "/v1/chat/completions":
                self._handle_chat(body)
            elif self.path == "/v1/completions":
                self._handle_completions(body)
            else:
                _json_response(self, {"error": {"message": "Not found"}}, 404)

        def _handle_chat(self, body: Dict[str, Any]):
            backend = get_backend()
            if backend is None or not backend.is_loaded:
                _json_response(self, {"error": {"message": "No model loaded"}}, 503)
                return
            messages = body.get("messages") or []
            if not isinstance(messages, list) or not messages:
                _json_response(self, {"error": {"message": "messages required"}}, 400)
                return
            stream = bool(body.get("stream"))
            max_tokens = int(body.get("max_tokens", 1024))
            temperature = float(body.get("temperature", 0.7))
            top_p = float(body.get("top_p", 0.9)) if body.get("top_p") is not None else 0.9
            top_k = int(body.get("top_k", 40)) if body.get("top_k") is not None else 40
            # Use resolved model params if available
            model_id = get_model_id()
            chat_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
            created = int(time.time())

            if stream:
                _sse_headers(self)
                try:
                    for chunk in backend.chat_stream(
                        messages,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        top_p=top_p,
                        top_k=top_k,
                    ):
                        if not chunk:
                            continue
                        payload = {
                            "id": chat_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model_id,
                            "choices": [{"index": 0, "delta": {"content": chunk}, "finish_reason": None}],
                        }
                        self.wfile.write(f"data: {json.dumps(payload)}\n\n".encode())
                        self.wfile.flush()
                    # final chunk
                    final = {
                        "id": chat_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model_id,
                        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                    }
                    self.wfile.write(f"data: {json.dumps(final)}\n\n".encode())
                    self.wfile.write(b"data: [DONE]\n\n")
                    self.wfile.flush()
                except BrokenPipeError:
                    pass
            else:
                try:
                    text = backend.chat(
                        messages,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        top_p=top_p,
                        top_k=top_k,
                    )
                except Exception as e:
                    _json_response(self, {"error": {"message": str(e)}}, 500)
                    return
                _json_response(self, {
                    "id": chat_id,
                    "object": "chat.completion",
                    "created": created,
                    "model": model_id,
                    "choices": [{
                        "index": 0,
                        "message": {"role": "assistant", "content": text},
                        "finish_reason": "stop",
                    }],
                    "usage": {
                        "prompt_tokens": sum(len(m.get("content", "").split()) for m in messages),
                        "completion_tokens": len(text.split()),
                        "total_tokens": sum(len(m.get("content", "").split()) for m in messages) + len(text.split()),
                    },
                })

        def _handle_completions(self, body: Dict[str, Any]):
            # Legacy completions: treat prompt as single user message
            prompt = body.get("prompt", "")
            if isinstance(prompt, list):
                prompt = prompt[0] if prompt else ""
            # Convert to chat
            messages = [{"role": "user", "content": str(prompt)}]
            body["messages"] = messages
            return self._handle_chat(body)

    return ApiHandler


def make_server(host: str, port: int, get_backend: Callable, get_model_id: Callable) -> ThreadingHTTPServer:
    handler = make_handler(get_backend, get_model_id)
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    return server

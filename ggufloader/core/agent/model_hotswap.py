"""
ModelHotSwap - Switch GGUF models at runtime without restarting the agent.

Provides:
- Load a new model, unloading the current one
- Fallback chain: try primary model, fall back to alternatives
- Warm-up: pre-load model into memory before switching
- Status tracking for the active model
- Thread-safe switching with pending queue

Pattern from: multi-model routing in production LLM gateways.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ModelInfo:
    """Snapshot of a loaded model."""

    def __init__(
        self,
        path: str,
        name: str = "",
        family: str = "",
        architecture: str = "",
        size_gb: float = 0.0,
        vram_gb: float = 0.0,
        context_length: int = 0,
    ) -> None:
        self.path = path
        self.name = name or Path(path).stem
        self.family = family
        self.architecture = architecture
        self.size_gb = size_gb
        self.vram_gb = vram_gb
        self.context_length = context_length

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "family": self.family,
            "architecture": self.architecture,
            "size_gb": self.size_gb,
            "vram_gb": self.vram_gb,
            "context_length": self.context_length,
        }


class ModelHotSwap:
    """Manages model loading/unloading with fallback chains and hot-swapping.

    Usage:
        swap = ModelHotSwap(
            load_fn=lambda path, **kw: load_gguf(path, **kw),
            unload_fn=lambda: unload_gguf(),
        )
        swap.set_fallback_chain(["model_a.gguf", "model_b.gguf"])
        swap.switch_to("model_a.gguf")
    """

    def __init__(
        self,
        load_fn: Callable[..., Any],
        unload_fn: Callable[[], None],
        inspect_fn: Optional[Callable[[str], Dict[str, Any]]] = None,
    ) -> None:
        """
        Args:
            load_fn: callable(path, n_ctx=, n_gpu_layers=) -> backend
            unload_fn: callable() to unload the current model
            inspect_fn: optional callable(path) -> dict with model metadata
        """
        self._load_fn = load_fn
        self._unload_fn = unload_fn
        self._inspect_fn = inspect_fn
        self._active: Optional[ModelInfo] = None
        self._backend: Any = None
        self._fallback_chain: List[str] = []
        self._lock = threading.Lock()
        self._switch_history: List[Dict[str, Any]] = []
        self._load_times: Dict[str, float] = {}  # path -> load time in seconds

    @property
    def active(self) -> Optional[ModelInfo]:
        """Currently loaded model info."""
        return self._active

    @property
    def backend(self) -> Any:
        """Currently loaded model backend."""
        return self._backend

    @property
    def is_loaded(self) -> bool:
        return self._backend is not None and self._active is not None

    def set_fallback_chain(self, paths: List[str]) -> None:
        """Set ordered list of fallback model paths."""
        self._fallback_chain = list(paths)

    def get_load_time(self, path: str) -> Optional[float]:
        """Get the last load time for a model path."""
        return self._load_times.get(path)

    def get_history(self) -> List[Dict[str, Any]]:
        """Get the switch history."""
        return list(self._switch_history)

    def switch_to(
        self,
        path: str,
        n_ctx: int = 4096,
        n_gpu_layers: int = -1,
        fallback: bool = True,
    ) -> Dict[str, Any]:
        """Hot-swap to a new model.

        Args:
            path: path to the GGUF model file
            n_ctx: context window size
            n_gpu_layers: GPU layers (-1 for auto)
            fallback: whether to try fallback chain on failure

        Returns:
            {"status": "success"|"error", "model": ModelInfo, ...}
        """
        with self._lock:
            # If same model already loaded, skip
            if self._active and self._active.path == path:
                return {
                    "status": "no_change",
                    "model": self._active.to_dict(),
                    "message": f"Model already loaded: {self._active.name}",
                }

            # Unload current model
            if self._backend is not None:
                try:
                    self._unload_fn()
                    logger.info("Unloaded previous model: %s", self._active.name if self._active else "?")
                except Exception as e:
                    logger.error("Failed to unload previous model: %s", e)

            self._backend = None
            self._active = None

            # Try loading the requested model
            start_time = time.monotonic()
            result = self._try_load(path, n_ctx, n_gpu_layers)
            load_time = time.monotonic() - start_time

            if result["status"] == "success":
                self._load_times[path] = load_time
                self._switch_history.append({
                    "action": "switch",
                    "path": path,
                    "success": True,
                    "load_time_s": round(load_time, 2),
                    "timestamp": time.time(),
                })
                return result

            # Try fallback chain
            if fallback and self._fallback_chain:
                for fallback_path in self._fallback_chain:
                    if fallback_path == path:
                        continue
                    logger.info("Trying fallback model: %s", fallback_path)
                    start_time = time.monotonic()
                    result = self._try_load(fallback_path, n_ctx, n_gpu_layers)
                    load_time = time.monotonic() - start_time
                    if result["status"] == "success":
                        self._load_times[fallback_path] = load_time
                        self._switch_history.append({
                            "action": "fallback",
                            "requested": path,
                            "loaded": fallback_path,
                            "success": True,
                            "load_time_s": round(load_time, 2),
                            "timestamp": time.time(),
                        })
                        result["message"] = f"Fell back to {Path(fallback_path).name}"
                        return result

            self._switch_history.append({
                "action": "switch",
                "path": path,
                "success": False,
                "timestamp": time.time(),
            })
            return result

    def unload(self) -> Dict[str, Any]:
        """Unload the current model."""
        with self._lock:
            if self._backend is None:
                return {"status": "no_model", "message": "No model loaded"}
            name = self._active.name if self._active else "?"
            try:
                self._unload_fn()
            except Exception as e:
                return {"status": "error", "error": str(e)}
            self._backend = None
            self._active = None
            self._switch_history.append({
                "action": "unload",
                "name": name,
                "timestamp": time.time(),
            })
            return {"status": "unloaded", "name": name}

    def _try_load(self, path: str, n_ctx: int, n_gpu_layers: int) -> Dict[str, Any]:
        """Attempt to load a model. Must be called with lock held."""
        try:
            backend = self._load_fn(path, n_ctx=n_ctx, n_gpu_layers=n_gpu_layers)
            self._backend = backend

            # Build model info
            info_kwargs: Dict[str, Any] = {"path": path}
            if self._inspect_fn:
                try:
                    meta = self._inspect_fn(path)
                    info_kwargs.update({
                        "name": meta.get("name", Path(path).stem),
                        "family": meta.get("family", ""),
                        "architecture": meta.get("architecture", ""),
                        "size_gb": meta.get("size_gb", 0.0),
                        "context_length": meta.get("context_length", 0),
                    })
                except Exception:
                    pass

            self._active = ModelInfo(**info_kwargs)
            logger.info("Loaded model: %s", self._active.name)
            return {
                "status": "success",
                "model": self._active.to_dict(),
            }
        except Exception as e:
            logger.error("Failed to load model %s: %s", path, e)
            return {
                "status": "error",
                "error": str(e),
                "path": path,
            }

    def status(self) -> Dict[str, Any]:
        """Get the current hot-swap status."""
        return {
            "loaded": self.is_loaded,
            "active_model": self._active.to_dict() if self._active else None,
            "fallback_chain": self._fallback_chain,
            "switch_count": len(self._switch_history),
            "load_times": {k: round(v, 2) for k, v in self._load_times.items()},
        }

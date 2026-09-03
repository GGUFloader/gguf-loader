"""Sole owner of llama-cpp runtime capability probes.

Every module that needs to know whether the installed llama-cpp-python
build supports GPU offload (CUDA) or Metal imports the probes from here;
no other module reaches into llama_cpp for feature detection. Keeps the
"what can this build do" question in exactly one place so a version bump
or backend swap never ripples through resource_manager, the router, the
API, and the installer with four different answers.
"""

from __future__ import annotations

__all__ = [
    "llama_cpp_available",
    "llama_supports_gpu_offload",
    "llama_supports_metal",
]


def llama_cpp_available() -> bool:
    """True when llama-cpp-python is importable at all."""
    try:
        import llama_cpp  # noqa: F401
        return True
    except Exception:  # pragma: no cover - environment dependent
        return False


def llama_supports_gpu_offload() -> bool:
    """True when the installed wheel can offload layers to a GPU.

    Uses the official runtime probe (``llama_supports_gpu_offload``) so it
    reflects the actually installed wheel - not just what the UI thinks
    was installed. Returns False when llama-cpp-python is missing.
    """
    try:
        from llama_cpp import llama_cpp as _llama_cpp
    except Exception:  # pragma: no cover - package missing
        return False
    probe = getattr(_llama_cpp, "llama_supports_gpu_offload", None)
    if callable(probe):
        try:
            return bool(probe())
        except Exception:  # pragma: no cover - backend init failure
            return False
    return False


def llama_supports_metal() -> bool:
    """True when the installed wheel was compiled with Apple Metal."""
    try:
        from llama_cpp import llama_cpp as _llama_cpp
    except Exception:  # pragma: no cover - package missing
        return False
    probe = getattr(_llama_cpp, "llama_supports_metal", None)
    if callable(probe):
        try:
            return bool(probe())
        except Exception:  # pragma: no cover - backend init failure
            return False
    return False

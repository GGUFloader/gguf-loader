"""Startup auto-load of the pinned Gemma 4 12B Q4_K_M GGUF.

Single-model app contract: the model should be ready when the UI opens,
with no manual "Load Model" step. This module:

1. Remembers the directory a model was last loaded from (config dir JSON),
   so an existing GGUF keeps working across app restarts without moving it.
2. Scans that directory plus the default models folder for a GGUF that
   passes the pinned-target gate.
3. Loads the best candidate in a background thread (server stays
   responsive while an 8 GB model loads) and publishes state that the
   ``/api/model/info`` endpoint surfaces to the UI.

Auto-load never blocks or crashes startup: failures become a status the
frontend can display, and everything is wrapped so a missing model file
is simply "not found".
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

from ggufloader.api.deps import get_model_backend, get_router, set_model_backend
from ggufloader.config import (
    PINNED_MODEL_FILENAME,
    PINNED_MODEL_URL,
    get_paths,
)
from ggufloader.resource_manager import find_config_dir

logger = logging.getLogger(__name__)

# Module-level state, guarded by a lock so exactly one scan/load runs.
_lock = threading.Lock()
_state: Dict[str, Optional[str]] = {
    "status": "idle",          # idle|scanning|loading|loaded|not_found|error|disabled
    "message": None,
    "path": None,
}
_worker: Optional[threading.Thread] = None

_STATUS_FILENAME = "model_auto_load.json"
_ENV_DIR_OVERRIDE = "GGUFLOADER_MODELS_DIR"
_ENV_SKIP = "GGUFLOADER_SKIP_AUTOLOAD"


def auto_load_status() -> dict:
    """Snapshot of auto-load state for the /model/info endpoint."""
    with _lock:
        status = dict(_state)
    status["models_dir"] = _primary_models_dir()
    backend = get_model_backend()
    if backend is not None and status["status"] != "loading":
        status["status"] = "loaded"
        status["path"] = getattr(backend, "model_path", None)
    return status


def remember_model_dir(directory: Optional[str]) -> Optional[str]:
    """Persist the directory models are loaded from (best-effort).

    Returns the normalized directory or None if it is unusable.
    """
    if not directory:
        return None
    d = Path(directory).expanduser()
    if not d.is_dir():
        logger.warning("Not remembering models dir (missing): %s", d)
        return None
    try:
        cfg = Path(find_config_dir())
        cfg.mkdir(parents=True, exist_ok=True)
        (cfg / _STATUS_FILENAME).write_text(
            json.dumps({"directory": str(d.resolve())}), encoding="utf-8")
        logger.info("Remembered models directory: %s", d)
    except OSError as e:  # read-only fs, etc. — never block startup on this
        logger.warning("Could not remember models dir %s: %s", d, e)
    return str(d)


def get_remembered_model_dir() -> Optional[str]:
    try:
        cfg = Path(find_config_dir()) / _STATUS_FILENAME
        if cfg.is_file():
            data = json.loads(cfg.read_text(encoding="utf-8"))
            d = data.get("directory")
            if d and Path(d).is_dir():
                return str(d)
    except (OSError, ValueError) as e:
        logger.debug("Could not read remembered models dir: %s", e)
    return None


def _default_models_dir() -> str:
    paths = get_paths()
    if "models" in paths:
        return str(Path(paths["models"]))
    return str(Path.home() / ".ggufloader" / "models")


def _primary_models_dir() -> str:
    """First directory the scanner will check (env override wins)."""
    override = os.environ.get(_ENV_DIR_OVERRIDE)
    if override:
        return str(Path(override).expanduser())
    return _default_models_dir()


def _candidate_dirs() -> List[str]:
    dirs: List[str] = []
    for d in (_primary_models_dir(), get_remembered_model_dir()):
        if d and d not in dirs:
            dirs.append(d)
    return dirs


def _is_pinned(profile) -> Optional[str]:
    """Return an error message if ``profile`` is not the pinned target.

    Mirrors the HTTP load gate in ``api/routes/model.py`` (single source
    of truth for what this build will run).
    """
    arch = (profile.architecture or "").lower()
    quant_blob = ((profile.quantization or "") + " " + profile.filename).upper()
    param_blob = ((profile.param_count_estimate or "") + " " + profile.filename).upper()
    if arch != "gemma4":
        return f"architecture '{profile.architecture}'"
    if "Q4_K_M" not in quant_blob:
        return f"quantization '{profile.quantization}'"
    if "12B" not in param_blob:
        return f"size '{profile.param_count_estimate}'"
    return None


def _find_pinned_file(dirs: List[str]):
    """Scan directories for the newest GGUF passing the pinned gate.

    Returns (path, profile) or (None, None). Inspect is metadata-only
    (cached by the router), so this is fast even for large files.
    """
    router = get_router()
    newest = None
    for d in dirs:
        root = Path(d)
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*.gguf"),
                        key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                profile = router.inspect(str(p))
            except Exception as e:
                logger.debug("Skipping unreadable GGUF %s: %s", p, e)
                continue
            reason = _is_pinned(profile)
            if reason is None:
                if newest is None or p.stat().st_mtime > newest[0].stat().st_mtime:
                    newest = (p, profile)
    return (newest[0], newest[1]) if newest else (None, None)


def _in_test_env() -> bool:
    """Never auto-load an 8 GB model while running the test suite."""
    if os.environ.get(_ENV_SKIP) == "1":
        return True
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    return os.path.basename(sys.argv[0]).startswith("pytest")


def _worker_run() -> None:
    try:
        dirs = _candidate_dirs()
        logger.info("Auto-load scan: %s", dirs)
        path, _profile = _find_pinned_file(dirs)
        if path is None:
            with _lock:
                _state.update({
                    "status": "not_found",
                    "message": "No Gemma 4 12B Q4_K_M GGUF found in models folder(s): "
                               + ", ".join(dirs or ["<none>"]) + ".",
                    "path": None,
                })
            return

        # Re-check under the lock: a manual load may have won the race.
        with _lock:
            if get_model_backend() is not None:
                _state.update({"status": "loaded", "message": None, "path": str(path)})
                return
            _state.update({"status": "loading", "message": None, "path": str(path)})

        from ggufloader.core.router import ModelRole
        backend, _profile, _strategy, _config = get_router().load(
            str(path), ModelRole.CHAT)
        set_model_backend(backend)
        remember_model_dir(str(Path(path).parent))
        with _lock:
            _state.update({
                "status": "loaded",
                "message": None,
                "path": str(path),
            })
        logger.info("Auto-loaded pinned model: %s", path)
    except Exception as e:  # noqa: BLE001 - surface instead of crashing
        logger.exception("Auto-load failed")
        with _lock:
            _state.update({"status": "error", "message": str(e), "path": None})


def start_auto_load(force: bool = False) -> dict:
    """Kick off a background auto-load (idempotent, never blocks).

    - Skipped entirely under pytest or when GGUFLOADER_SKIP_AUTOLOAD=1.
    - No-op if a model is already loaded (unless force=True).
    - Spawns at most one worker thread at a time.
    """
    global _worker
    if _in_test_env():
        with _lock:
            _state.update({
                "status": "disabled",
                "message": "Auto-load is disabled in this environment "
                           "(GGUFLOADER_SKIP_AUTOLOAD or test runner).",
                "path": None,
            })
        return auto_load_status()

    with _lock:
        if not force and get_model_backend() is not None:
            _state.update({"status": "loaded", "message": None})
            return auto_load_status()
        if _worker is not None and _worker.is_alive():
            return auto_load_status()
        _worker = threading.Thread(target=_worker_run, daemon=True, name="auto-load")
        _state.update({"status": "scanning", "message": None, "path": None})
        _worker.start()
    return auto_load_status()


def reset_auto_load() -> None:
    """Clear state after an explicit unload so the next start re-scans."""
    with _lock:
        _state.update({"status": "idle", "message": None, "path": None})


# ---------------------------------------------------------------------------
# Pinned model download (shown when no compatible GGUF is on disk)
# ---------------------------------------------------------------------------

_dl_lock = threading.Lock()
_dl_state: Dict[str, Optional[object]] = {
    "status": "idle",      # idle|downloading|done|error|disabled
    "progress": 0.0,        # 0..1
    "downloaded_bytes": 0,
    "total_bytes": 0,
    "message": None,
    "path": None,
}
_dl_worker: Optional[threading.Thread] = None

_DL_MIN_VALID_BYTES = 1024 ** 3  # an 8 GB Q4 file shorter than 1 GB is a partial
_DL_CHUNK = 1024 * 1024


def pinned_download_status() -> dict:
    """Snapshot of download state for the UI."""
    with _dl_lock:
        return dict(_dl_state)


def start_pinned_download(force: bool = False) -> dict:
    """Start a background download of the pinned Gemma 4 12B Q4_K_M GGUF.

    Idempotent: at most one worker runs; an already-valid file short-\
    circuits to ``done``. Download lands in the default models folder so
    the startup auto-loader finds it afterwards.
    """
    global _dl_worker

    if _in_test_env():
        with _dl_lock:
            _dl_state.update({
                "status": "disabled",
                "message": "Model download is disabled in this environment "
                           "(GGUFLOADER_SKIP_AUTOLOAD or test runner).",
                "path": None,
            })
        return pinned_download_status()

    dest = Path(_default_models_dir()) / PINNED_MODEL_FILENAME
    if dest.exists() and dest.stat().st_size >= _DL_MIN_VALID_BYTES:
        with _dl_lock:
            _dl_state.update({
                "status": "done",
                "progress": 1.0,
                "path": str(dest),
                "message": None,
            })
        return pinned_download_status()

    with _dl_lock:
        if not force and _dl_worker is not None and _dl_worker.is_alive():
            return pinned_download_status()
        _dl_state.update({
            "status": "downloading",
            "progress": 0.0,
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "message": None,
            "path": str(dest),
        })
        _dl_worker = threading.Thread(
            target=_download_worker_run, daemon=True, name="pinned-download")
        _dl_worker.start()
    return pinned_download_status()


def _set_dl(progress: float, **kw) -> None:
    with _dl_lock:
        _dl_state.update({"progress": progress, **kw})


def _download_worker_run() -> None:
    """Stream PINNED_MODEL_URL into the default models folder.

    Resume-capable via HTTP Range (interrupted multi-GB downloads pick up
    where they left off). On success the folder is remembered and the
    auto-loader is kicked so the model becomes ready without a manual
    load step.
    """
    dest_dir = Path(_default_models_dir())
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        _set_dl(0.0, status="error", message=f"Cannot create models folder {dest_dir}: {e}")
        return

    dest = dest_dir / PINNED_MODEL_FILENAME
    existing = dest.stat().st_size if dest.exists() else 0
    try:
        req = urllib.request.Request(PINNED_MODEL_URL, headers={"User-Agent": "GGUFLoader/2.3"})
        if existing > 0:
            req.add_header("Range", f"bytes={existing}-")
            logger.info("Resuming pinned download from byte %d", existing)
        resp = urllib.request.urlopen(req, timeout=60)  # noqa: S310
        code = resp.getcode()
        resumed = code == 206 and existing > 0
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = existing if resumed else 0
        mode = "ab" if resumed else "wb"
        if resumed:
            total = existing + total  # Content-Length is the remaining bytes
        _set_dl(downloaded / total if total else 0.0, total_bytes=total)

        with open(dest, mode) as f:
            while True:
                chunk = resp.read(_DL_CHUNK)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    _set_dl(min(downloaded / total, 1.0),
                            downloaded_bytes=downloaded, total_bytes=total)

        if dest.stat().st_size < _DL_MIN_VALID_BYTES:
            raise RuntimeError(
                f"Downloaded file is suspiciously small ({dest.stat().st_size} bytes) "
                "— server may have returned an error page.")

        remember_model_dir(str(dest_dir))
        _set_dl(1.0, status="done", path=str(dest), message=None,
                downloaded_bytes=dest.stat().st_size)
        logger.info("Pinned model downloaded: %s", dest)
        # Make the model ready immediately (no-op if already loaded).
        try:
            start_auto_load(force=True)
        except Exception:  # noqa: BLE001 - never let auto-load mask a good download
            logger.exception("Auto-load after download failed")
    except Exception as e:  # noqa: BLE001 - surface instead of crashing
        logger.exception("Pinned model download failed")
        _set_dl(0.0, status="error",
                message=f"Download failed: {e}. Partial file kept for resume.")

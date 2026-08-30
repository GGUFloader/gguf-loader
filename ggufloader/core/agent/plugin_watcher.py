"""
PluginWatcher - Watch plugin directories for changes and auto-reload.

Features:
- Monitor plugin directories for new/changed/deleted files
- Debounced reload to avoid rapid re-scans
- Callback-based notifications for plugin events
- Thread-safe operation
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

# Default plugin directories
PLUGIN_DIRS = [
    Path.home() / ".ggufloader" / "plugins",
    Path.home() / ".ggufloader" / "tools",
]


class PluginWatcher:
    """Watch plugin directories and notify on changes."""

    def __init__(
        self,
        workspace: Optional[Path] = None,
        on_change: Optional[Callable[[str, List[str]], None]] = None,
    ) -> None:
        """
        Args:
            workspace: workspace path for project-local plugins
            on_change: callback(event_type, affected_files) where event_type is
                       'created', 'modified', 'deleted', or 'reload'
        """
        self.workspace = workspace
        self._on_change = on_change
        self._watch_dirs: List[Path] = []
        self._file_hashes: Dict[str, str] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._interval = 5.0  # seconds between scans
        self._last_reload = 0.0
        self._reload_cooldown = 2.0  # minimum seconds between reloads

        # Build watch list
        for d in PLUGIN_DIRS:
            if d.is_dir():
                self._watch_dirs.append(d)
        if workspace:
            wp = workspace / ".ggufloader-tools"
            if wp.is_dir():
                self._watch_dirs.append(wp)

    @property
    def watching(self) -> bool:
        return self._running

    def start(self) -> None:
        """Start watching in a background thread."""
        if self._running:
            return
        self._running = True
        self._scan_initial()
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        logger.info("Plugin watcher started, monitoring %d directories", len(self._watch_dirs))

    def stop(self) -> None:
        """Stop watching."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None
        logger.info("Plugin watcher stopped")

    def scan_now(self) -> List[str]:
        """Force an immediate scan. Returns list of changed files."""
        return self._scan()

    def get_watched_dirs(self) -> List[str]:
        """Return list of directories being watched."""
        return [str(d) for d in self._watch_dirs]

    def _scan_initial(self) -> None:
        """Take initial snapshot of all plugin files."""
        for d in self._watch_dirs:
            for f in self._iter_plugin_files(d):
                self._file_hashes[str(f)] = self._hash_file(f)

    def _watch_loop(self) -> None:
        """Background scan loop."""
        while self._running:
            time.sleep(self._interval)
            if not self._running:
                break
            try:
                changed = self._scan()
                if changed:
                    now = time.time()
                    if now - self._last_reload >= self._reload_cooldown:
                        self._last_reload = now
                        if self._on_change:
                            self._on_change("reload", changed)
            except Exception as e:
                logger.error("Plugin watcher scan error: %s", e)

    def _scan(self) -> List[str]:
        """Scan for changes. Returns list of changed file paths."""
        changed = []
        current_files: Set[str] = set()

        # Check for new/modified files
        for d in self._watch_dirs:
            if not d.is_dir():
                continue
            for f in self._iter_plugin_files(d):
                fstr = str(f)
                current_files.add(fstr)
                current_hash = self._hash_file(f)
                old_hash = self._file_hashes.get(fstr)

                if old_hash is None:
                    changed.append(fstr)
                    logger.info("New plugin detected: %s", f.name)
                    if self._on_change:
                        self._on_change("created", [fstr])
                elif old_hash != current_hash:
                    changed.append(fstr)
                    logger.info("Plugin modified: %s", f.name)
                    if self._on_change:
                        self._on_change("modified", [fstr])

                self._file_hashes[fstr] = current_hash

        # Check for deleted files
        for fstr in list(self._file_hashes.keys()):
            if fstr not in current_files:
                changed.append(fstr)
                del self._file_hashes[fstr]
                logger.info("Plugin deleted: %s", Path(fstr).name)
                if self._on_change:
                    self._on_change("deleted", [fstr])

        return changed

    def _iter_plugin_files(self, directory: Path):
        """Iterate over plugin files in a directory."""
        try:
            for f in directory.iterdir():
                if f.is_file() and f.suffix in (".json", ".py") and not f.name.startswith("_"):
                    yield f
        except PermissionError:
            pass

    def _hash_file(self, path: Path) -> str:
        """Quick file content hash."""
        try:
            content = path.read_bytes()
            return hashlib.md5(content).hexdigest()
        except Exception:
            return ""

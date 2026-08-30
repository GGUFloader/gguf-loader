"""
ExportImport - Export and import sessions, settings, templates, and plugins.

Features:
- Bundle multiple data types into a single JSON export
- Import with conflict resolution (skip, overwrite, merge)
- Validate import bundles before applying
- Versioned bundle format for forward compatibility
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

BUNDLE_VERSION = 1


class ExportImport:
    """Manage export/import of application data bundles."""

    def __init__(self, workspace: Optional[Path] = None) -> None:
        self.workspace = workspace or Path.home() / ".ggufloader"
        self._exports_dir = self.workspace / "exports"
        self._exports_dir.mkdir(parents=True, exist_ok=True)

    def export_bundle(
        self,
        *,
        sessions: bool = True,
        settings: bool = True,
        templates: bool = True,
        plugins: bool = True,
        name: str = "",
    ) -> Path:
        """Create an export bundle with selected data types.

        Returns the path to the saved bundle file.
        """
        bundle: Dict[str, Any] = {
            "version": BUNDLE_VERSION,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "name": name or f"export_{int(time.time())}",
            "data": {},
        }

        if sessions:
            bundle["data"]["sessions"] = self._export_sessions()
        if settings:
            bundle["data"]["settings"] = self._export_settings()
        if templates:
            bundle["data"]["templates"] = self._export_templates()
        if plugins:
            bundle["data"]["plugins"] = self._export_plugins()

        # Save bundle
        filename = f"{bundle['name']}.json"
        path = self._exports_dir / filename
        path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def import_bundle(
        self,
        path: str | Path,
        *,
        conflict: str = "skip",  # skip, overwrite, merge
        data_types: Optional[List[str]] = None,  # None = all
    ) -> Dict[str, Any]:
        """Import data from a bundle file.

        Args:
            path: path to the bundle JSON file
            conflict: how to handle conflicts (skip/overwrite/merge)
            data_types: list of data types to import (None = all)

        Returns:
            Import report with counts of imported/skipped/conflicted items
        """
        path = Path(path)
        if not path.exists():
            return {"error": f"File not found: {path}"}

        try:
            bundle = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            return {"error": f"Invalid JSON: {e}"}

        # Validate version
        version = bundle.get("version", 0)
        if version > BUNDLE_VERSION:
            return {"error": f"Bundle version {version} is newer than supported ({BUNDLE_VERSION})"}

        report: Dict[str, Any] = {
            "imported": 0,
            "skipped": 0,
            "conflicts": 0,
            "errors": [],
            "details": {},
        }

        data = bundle.get("data", {})
        allowed = set(data_types) if data_types else set(data.keys())

        if "sessions" in allowed and "sessions" in data:
            r = self._import_sessions(data["sessions"], conflict)
            report["details"]["sessions"] = r
            report["imported"] += r.get("imported", 0)
            report["skipped"] += r.get("skipped", 0)

        if "settings" in allowed and "settings" in data:
            r = self._import_settings(data["settings"], conflict)
            report["details"]["settings"] = r
            report["imported"] += r.get("imported", 0)

        if "templates" in allowed and "templates" in data:
            r = self._import_templates(data["templates"], conflict)
            report["details"]["templates"] = r
            report["imported"] += r.get("imported", 0)
            report["skipped"] += r.get("skipped", 0)

        if "plugins" in allowed and "plugins" in data:
            r = self._import_plugins(data["plugins"], conflict)
            report["details"]["plugins"] = r
            report["imported"] += r.get("imported", 0)

        return report

    def list_exports(self) -> List[Dict[str, Any]]:
        """List all saved export bundles."""
        exports = []
        for f in sorted(self._exports_dir.glob("*.json"), reverse=True):
            try:
                bundle = json.loads(f.read_text(encoding="utf-8"))
                data_types = list(bundle.get("data", {}).keys())
                exports.append({
                    "filename": f.name,
                    "name": bundle.get("name", ""),
                    "created_at": bundle.get("created_at", ""),
                    "version": bundle.get("version", 0),
                    "data_types": data_types,
                    "size_bytes": f.stat().st_size,
                })
            except Exception:
                continue
        return exports

    def delete_export(self, filename: str) -> bool:
        """Delete an export bundle."""
        path = self._exports_dir / filename
        if path.exists() and path.suffix == ".json":
            path.unlink()
            return True
        return False

    # --- Private export methods ---

    def _export_sessions(self) -> List[Dict[str, Any]]:
        """Export all chat sessions."""
        sessions = []
        try:
            from ggufloader.config import get_paths
            from ggufloader.core.sessions.store import SessionStore
            store = SessionStore(get_paths()["chats"])
            for s in store.list_sessions():
                full = store.load(s["id"])
                if full:
                    sessions.append(full)
        except Exception as e:
            logger.warning("Failed to export sessions: %s", e)
        return sessions

    def _export_settings(self) -> Dict[str, Any]:
        """Export application settings."""
        settings = {}
        try:
            from ggufloader.config import get_paths
            settings_path = Path(get_paths().get("config", self.workspace / "settings.json"))
            if settings_path.exists():
                settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("Failed to export settings: %s", e)
        return settings

    def _export_templates(self) -> List[Dict[str, Any]]:
        """Export custom templates."""
        templates = []
        try:
            from ggufloader.core.agent.templates import TemplateManager
            mgr = TemplateManager(self.workspace)
            for t in mgr.list_all():
                if not t.builtin:
                    templates.append(t.to_dict())
        except Exception as e:
            logger.warning("Failed to export templates: %s", e)
        return templates

    def _export_plugins(self) -> List[Dict[str, Any]]:
        """Export plugin configurations."""
        plugins = []
        plugins_dir = self.workspace / "plugins"
        if plugins_dir.is_dir():
            for f in plugins_dir.glob("*.json"):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    plugins.append(data)
                except Exception:
                    continue
        return plugins

    # --- Private import methods ---

    def _import_sessions(self, sessions: List[Dict], conflict: str) -> Dict[str, int]:
        imported = 0
        skipped = 0
        try:
            from ggufloader.config import get_paths
            from ggufloader.core.sessions.store import SessionStore
            store = SessionStore(get_paths()["chats"])
            existing = {s["id"] for s in store.list_sessions()}
            for s in sessions:
                sid = s.get("id", "")
                if sid in existing:
                    if conflict == "skip":
                        skipped += 1
                        continue
                    elif conflict == "overwrite":
                        store.save(s)
                        imported += 1
                else:
                    store.save(s)
                    imported += 1
        except Exception as e:
            logger.warning("Failed to import sessions: %s", e)
        return {"imported": imported, "skipped": skipped}

    def _import_settings(self, settings: Dict, conflict: str) -> Dict[str, int]:
        try:
            from ggufloader.config import get_paths
            settings_path = Path(get_paths().get("config", self.workspace / "settings.json"))
            if conflict == "merge" and settings_path.exists():
                existing = json.loads(settings_path.read_text(encoding="utf-8"))
                existing.update(settings)
                settings = existing
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")
            return {"imported": 1}
        except Exception as e:
            logger.warning("Failed to import settings: %s", e)
            return {"imported": 0}

    def _import_templates(self, templates: List[Dict], conflict: str) -> Dict[str, int]:
        imported = 0
        skipped = 0
        try:
            from ggufloader.core.agent.templates import TemplateManager, PromptTemplate
            mgr = TemplateManager(self.workspace)
            for t_data in templates:
                tid = t_data.get("id", "")
                existing = mgr.get(tid)
                if existing:
                    if conflict == "skip":
                        skipped += 1
                        continue
                    elif conflict == "overwrite":
                        pass  # will overwrite
                t = PromptTemplate.from_dict(t_data)
                mgr.save(t)
                imported += 1
        except Exception as e:
            logger.warning("Failed to import templates: %s", e)
        return {"imported": imported, "skipped": skipped}

    def _import_plugins(self, plugins: List[Dict], conflict: str) -> Dict[str, int]:
        imported = 0
        plugins_dir = self.workspace / "plugins"
        plugins_dir.mkdir(parents=True, exist_ok=True)
        for p in plugins:
            name = p.get("name", "unknown")
            target = plugins_dir / f"{name}.json"
            if target.exists() and conflict == "skip":
                continue
            try:
                target.write_text(json.dumps(p, indent=2, ensure_ascii=False), encoding="utf-8")
                imported += 1
            except Exception:
                continue
        return {"imported": imported}

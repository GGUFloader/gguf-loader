"""
ConfigMigration - Handle configuration upgrades between versions.

Pattern from: Database migrations + Claude Code config evolution.
When the config schema changes between releases, this module:
1. Detects the old config version
2. Applies migrations in order
3. Preserves user customizations
4. Adds new fields with defaults
5. Removes deprecated fields

Each migration is a function that transforms the config dict.
"""

from __future__ import annotations

import json
import logging
import shutil
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class Migration:
    """A single configuration migration."""

    def __init__(self, from_version: int, to_version: int,
                 description: str, fn: Callable[[Dict], Dict]) -> None:
        self.from_version = from_version
        self.to_version = to_version
        self.description = description
        self.fn = fn

    def apply(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return self.fn(config)


# Migration registry
MIGRATIONS: List[Migration] = []


def migration(from_version: int, to_version: int, description: str):
    """Decorator to register a migration function."""
    def decorator(fn):
        MIGRATIONS.append(Migration(from_version, to_version, description, fn))
        return fn
    return decorator


@migration(1, 2, "Add context and health sections")
def migrate_v1_to_v2(config: Dict[str, Any]) -> Dict[str, Any]:
    """Migration from v1 to v2: Add new sections with defaults."""
    # Add context section
    if "context" not in config:
        config["context"] = {
            "budget_tokens": 8192,
            "system_prompt_tokens": 500,
        }

    # Add health section
    if "health" not in config:
        config["health"] = {
            "enabled": True,
            "monitor_interval": 5,
        }

    # Add audit section
    if "audit" not in config:
        config["audit"] = {
            "enabled": True,
            "max_entries": 5000,
        }

    # Rename deprecated fields
    if "max_context" in config.get("agent", {}):
        config["context"]["budget_tokens"] = config["agent"].pop("max_context")

    config["version"] = 2
    return config


class ConfigMigration:
    """Handle configuration version upgrades.

    Usage:
        migrator = ConfigMigration(workspace)
        config = migrator.load_and_migrate()
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self._backup_dir = workspace / ".ggufloader-backups"

    def needs_migration(self, config: Dict[str, Any]) -> bool:
        """Check if config needs migration."""
        current_version = config.get("version", 1)
        latest_version = max(m.from_version for m in MIGRATIONS) if MIGRATIONS else current_version
        return current_version < latest_version

    def migrate(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply all pending migrations to the config."""
        current_version = config.get("version", 1)

        # Sort migrations by version
        sorted_migrations = sorted(MIGRATIONS, key=lambda m: m.from_version)

        for m in sorted_migrations:
            if m.from_version >= current_version:
                logger.info("Applying migration v%d → v%d: %s",
                           m.from_version, m.to_version, m.description)
                try:
                    config = m.apply(config)
                except Exception as e:
                    logger.error("Migration v%d → v%d failed: %s",
                                m.from_version, m.to_version, e)

        return config

    def load_and_migrate(self, config_path: Path) -> Optional[Dict[str, Any]]:
        """Load a config file, migrate if needed, and save."""
        if not config_path.exists():
            return None

        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error("Failed to read config: %s", e)
            return None

        if self.needs_migration(config):
            # Backup before migration
            self._backup(config_path)

            # Apply migrations
            config = self.migrate(config)

            # Save migrated config
            try:
                config_path.write_text(
                    json.dumps(config, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                logger.info("Config migrated and saved: %s", config_path)
            except Exception as e:
                logger.error("Failed to save migrated config: %s", e)

        return config

    def _backup(self, config_path: Path) -> None:
        """Create a backup of the config before migration."""
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_name = f"config_{timestamp}.json"
        backup_path = self._backup_dir / backup_name
        try:
            shutil.copy2(config_path, backup_path)
            logger.info("Config backed up to %s", backup_path)
        except Exception as e:
            logger.warning("Failed to backup config: %s", e)

    def list_backups(self) -> List[Dict[str, Any]]:
        """List available config backups."""
        if not self._backup_dir.exists():
            return []
        backups = []
        for f in sorted(self._backup_dir.glob("config_*.json"), reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                backups.append({
                    "filename": f.name,
                    "version": data.get("version", "unknown"),
                    "timestamp": f.stat().st_mtime,
                })
            except Exception:
                continue
        return backups

    def restore_backup(self, filename: str) -> bool:
        """Restore a config backup."""
        backup_path = self._backup_dir / filename
        if not backup_path.exists():
            return False
        config_path = self.workspace / ".ggufloader.json"
        try:
            shutil.copy2(backup_path, config_path)
            return True
        except Exception:
            return False

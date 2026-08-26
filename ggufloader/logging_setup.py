"""File logging with previous-run retention (GPT4All logger.cpp parity).

Keeps ``log.txt`` for the current run and renames the previous one to
``log-prev.txt`` at startup - enough to diagnose "it worked last time".
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_INSTALLED = False


def setup_file_logging(logs_dir: str | Path) -> str:
    """Attach a rotating file handler to the root logger; returns path."""
    global _INSTALLED
    logs = Path(logs_dir)
    logs.mkdir(parents=True, exist_ok=True)
    log_file = logs / "log.txt"
    prev = logs / "log-prev.txt"

    if not _INSTALLED:
        try:
            if log_file.exists():
                if prev.exists():
                    prev.unlink()
                log_file.replace(prev)
            _INSTALLED = True
        except OSError:  # noqa: BLE001 - locked file must not block startup
            pass

    handler = RotatingFileHandler(
        log_file, maxBytes=2_000_000, backupCount=1, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(
        "[%(levelname)s] (%(asctime)s): %(message)s", "%Y-%m-%d %H:%M:%S"
    ))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
               for h in root.handlers):
        root.addHandler(logging.StreamHandler())
    return str(log_file)


def current_log_file(logs_dir: str | Path) -> Path:
    return Path(logs_dir) / os.path.basename("log.txt")

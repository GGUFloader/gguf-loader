"""Per-model chat parameter overrides.

Some models need non-default sampling to behave (LiquidAI LFM2.5 needs
temperature 0.2; creative models may want 0.8). Overrides live in an
optional ``model_params.json`` looked up in the config dir first, then
next to the package root:

    {
      "lfm2.5": {"temperature": 0.2, "top_k": 80, "repeat_penalty": 1.05},
      "qwen3": {"temperature": 0.6}
    }

Keys are lowercased substrings matched against the model file name
(first hit wins); values override any of: temperature, top_k, top_p,
repeat_penalty, max_tokens.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

OVERRIDABLE_NUMERIC = ("temperature", "top_k", "top_p", "repeat_penalty", "max_tokens", "min_p")
OVERRIDABLE_KEYS = OVERRIDABLE_NUMERIC + ("system_prompt",)


def _candidate_files() -> list:
    from ggufloader.resource_manager import find_config_dir

    return [Path(find_config_dir()) / "model_params.json"]


def load_model_params(model_path: str, overrides_file: Optional[Path] = None) -> Dict[str, float]:
    """Resolve chat parameter overrides for *model_path* ({} when none)."""
    path = Path(overrides_file) if overrides_file else None
    candidates = [path] if path else _candidate_files()
    table: Dict[str, dict] = {}
    for candidate in candidates:
        if candidate is None or not Path(candidate).is_file():
            continue
        try:
            # utf-8-sig tolerates a BOM (PowerShell's UTF8 encoding writes one)
            data = json.loads(Path(candidate).read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                table = {str(k).lower(): v for k, v in data.items() if isinstance(v, dict)}
            break
        except Exception as e:  # noqa: BLE001 - bad file must not break chat
            logger.warning("Could not read %s: %s", candidate, e)
            break

    name = Path(model_path).name.lower()
    for key, params in table.items():
        if key and key in name:
            clean: Dict[str, Any] = {}
            for k, v in params.items():
                if k == "system_prompt" and isinstance(v, str):
                    clean[k] = v
                elif k in OVERRIDABLE_NUMERIC and isinstance(v, (int, float)):
                    clean[k] = v
            if clean:
                logger.info("Model params override via '%s': %s", key,
                            {k: v for k, v in clean.items() if k != "system_prompt"})
                return clean
    return {}


# ---------------------------------------------------------------------------
# Write-side: per-model dialog persistence (C1-lite)
# ---------------------------------------------------------------------------

def _primary_overrides_file() -> Path:
    from ggufloader.resource_manager import find_config_dir
    return Path(find_config_dir()) / "model_params.json"


def set_model_override(model_path: str, params: Dict[str, float],
                       overrides_file: Optional[Path] = None) -> None:
    """Insert/update the override entry keyed by the model file name."""
    target = Path(overrides_file) if overrides_file else _primary_overrides_file()
    table: Dict[str, dict] = {}
    if target.is_file():
        try:
            data = json.loads(target.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                table = {str(k): v for k, v in data.items() if isinstance(v, dict)}
        except Exception as e:  # noqa: BLE001 - corrupt file gets replaced
            logger.warning("Replacing unreadable %s: %s", target.name, e)
    key = Path(model_path).name.lower()
    clean: Dict[str, Any] = {}
    for k, v in params.items():
        if k == "system_prompt" and isinstance(v, str):
            clean[k] = v
        elif k in OVERRIDABLE_NUMERIC and isinstance(v, (int, float)):
            clean[k] = v
    if clean:
        table[key] = clean
    else:
        table.pop(key, None)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(table, indent=2), encoding="utf-8")


def clear_model_override(model_path: str,
                         overrides_file: Optional[Path] = None) -> None:
    """Remove any override for this model (back to family defaults)."""
    key = Path(model_path).name.lower()
    target = Path(overrides_file) if overrides_file else _primary_overrides_file()
    if not target.is_file():
        return
    try:
        data = json.loads(target.read_text(encoding="utf-8-sig"))
    except Exception:  # noqa: BLE001
        return
    if isinstance(data, dict) and key in data:
        del data[key]
        target.write_text(json.dumps(data, indent=2), encoding="utf-8")

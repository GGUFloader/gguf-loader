"""
DiffViewer - Compute and format code diffs for the inline viewer.

Features:
- Unified and split diff formats
- Syntax-aware line highlighting
- File-level and hunk-level organization
- Tool call result diff extraction
"""

from __future__ import annotations

import difflib
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def compute_diff(
    old_text: str,
    new_text: str,
    filename: str = "",
    context_lines: int = 3,
) -> Dict[str, Any]:
    """Compute a unified diff between two text strings.

    Returns structured diff data for the frontend viewer.
    """
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    # Generate unified diff
    diff = list(difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"a/{filename}" if filename else "a/original",
        tofile=f"b/{filename}" if filename else "b/modified",
        n=context_lines,
    ))

    # Parse into hunks
    hunks = _parse_unified_diff(diff)

    # Count stats
    additions = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
    deletions = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))

    return {
        "filename": filename,
        "hunks": hunks,
        "stats": {
            "additions": additions,
            "deletions": deletions,
            "total_changes": additions + deletions,
        },
        "raw": "".join(diff),
    }


def compute_side_by_side(
    old_text: str,
    new_text: str,
    filename: str = "",
) -> Dict[str, Any]:
    """Compute a side-by-side diff."""
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()

    sm = difflib.SequenceMatcher(None, old_lines, new_lines)
    side_by_side = []

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for i in range(i1, i2):
                offset = i - i1
                side_by_side.append({
                    "old_line": i + 1,
                    "new_line": j1 + offset + 1,
                    "old_text": old_lines[i],
                    "new_text": new_lines[j1 + offset],
                    "type": "equal",
                })
        elif tag == "replace":
            max_len = max(i2 - i1, j2 - j1)
            for k in range(max_len):
                old_idx = i1 + k if k < (i2 - i1) else None
                new_idx = j1 + k if k < (j2 - j1) else None
                side_by_side.append({
                    "old_line": (old_idx + 1) if old_idx is not None else None,
                    "new_line": (new_idx + 1) if new_idx is not None else None,
                    "old_text": old_lines[old_idx] if old_idx is not None else "",
                    "new_text": new_lines[new_idx] if new_idx is not None else "",
                    "type": "replace",
                })
        elif tag == "delete":
            for i in range(i1, i2):
                side_by_side.append({
                    "old_line": i + 1,
                    "new_line": None,
                    "old_text": old_lines[i],
                    "new_text": "",
                    "type": "delete",
                })
        elif tag == "insert":
            for j in range(j1, j2):
                side_by_side.append({
                    "old_line": None,
                    "new_line": j + 1,
                    "old_text": "",
                    "new_text": new_lines[j],
                    "type": "insert",
                })

    additions = sum(1 for r in side_by_side if r["type"] in ("insert", "replace"))
    deletions = sum(1 for r in side_by_side if r["type"] in ("delete", "replace"))

    return {
        "filename": filename,
        "lines": side_by_side,
        "stats": {
            "additions": additions,
            "deletions": deletions,
        },
    }


def extract_diffs_from_tool_results(tool_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract file diffs from agent tool call results.

    Looks at write_file, edit_file results and extracts the changed content.
    """
    diffs = []
    for result in tool_results:
        tool = result.get("tool_name", "")

        if tool == "write_file" and result.get("status") == "success":
            # For write_file, show the new content as an addition
            content = result.get("content", result.get("result", ""))
            if content:
                diffs.append({
                    "filename": result.get("path", "file"),
                    "type": "create",
                    "stats": {"additions": len(content.splitlines()), "deletions": 0},
                    "content": content,
                })

        elif tool == "edit_file" and result.get("status") == "success":
            operation = result.get("operation", "replace")
            changes = result.get("changes_made", 0)
            diffs.append({
                "filename": result.get("path", "file"),
                "type": "modify",
                "operation": operation,
                "stats": {"changes": changes},
            })

    return diffs


def _parse_unified_diff(diff_lines: List[str]) -> List[Dict[str, Any]]:
    """Parse unified diff lines into structured hunks."""
    hunks = []
    current_hunk = None

    for line in diff_lines:
        # Hunk header: @@ -old_start,old_count +new_start,new_count @@
        hunk_match = re.match(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@(.*)", line)
        if hunk_match:
            if current_hunk:
                hunks.append(current_hunk)
            current_hunk = {
                "old_start": int(hunk_match.group(1)),
                "new_start": int(hunk_match.group(2)),
                "header": hunk_match.group(3).strip(),
                "lines": [],
            }
            continue

        if current_hunk is not None:
            if line.startswith("+"):
                current_hunk["lines"].append({"type": "add", "content": line[1:]})
            elif line.startswith("-"):
                current_hunk["lines"].append({"type": "delete", "content": line[1:]})
            elif line.startswith(" "):
                current_hunk["lines"].append({"type": "context", "content": line[1:]})
            elif line.startswith("\\"):
                current_hunk["lines"].append({"type": "info", "content": line})

    if current_hunk:
        hunks.append(current_hunk)

    return hunks

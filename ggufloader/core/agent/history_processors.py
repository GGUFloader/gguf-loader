"""
History Processors - Composable context management pipeline.

Inspired by SWE-agent's HistoryProcessor system. Each processor is a
callable that takes a history list and returns a modified copy. Processors
can be chained into a pipeline for composable context management.

This replaces the hardcoded CLIP_RECENT/CLIP_OLD approach with a flexible,
configurable pipeline that can be extended without touching the agent loop.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class HistoryProcessor(ABC):
    """Base class for history processors."""

    @abstractmethod
    def __call__(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process history and return modified copy."""
        ...

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"


class DefaultHistoryProcessor(HistoryProcessor):
    """No-op passthrough. Used as the base of the pipeline."""

    def __call__(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return list(history)


class AgeBasedClipper(HistoryProcessor):
    """Clip older entries to save context space.

    Keeps the last `keep_recent` entries at full length, clips older
    entries to `clip_old_chars` chars. Tool results get more space
    than assistant messages.

    This is the direct replacement for the old CLIP_RECENT/CLIP_OLD system.
    """

    def __init__(
        self,
        keep_recent: int = 6,
        clip_recent_chars: int = 2000,
        clip_old_chars: int = 400,
        max_history_chars: int = 30000,
    ) -> None:
        self.keep_recent = keep_recent
        self.clip_recent_chars = clip_recent_chars
        self.clip_old_chars = clip_old_chars
        self.max_history_chars = max_history_chars

    def __call__(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not history:
            return []

        result = []
        for i, entry in enumerate(history):
            entry = dict(entry)  # shallow copy
            is_recent = i >= len(history) - self.keep_recent

            if is_recent:
                limit = self.clip_recent_chars
            else:
                limit = self.clip_old_chars

            content = entry.get("content", "")
            if isinstance(content, str) and len(content) > limit:
                entry["content"] = content[:limit] + f"... [truncated {len(content) - limit} chars]"
            elif isinstance(content, list):
                # Handle multimodal content (list of text/image objects)
                truncated = []
                total = 0
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text = item.get("text", "")
                        if total + len(text) > limit:
                            remaining = max(0, limit - total)
                            if remaining > 0:
                                truncated.append({**item, "text": text[:remaining] + "... [truncated]"})
                            break
                        total += len(text)
                    truncated.append(item)
                entry["content"] = truncated if truncated else content

            result.append(entry)

        # Hard cap on total characters
        total_chars = sum(len(str(e.get("content", ""))) for e in history)
        while total_chars > self.max_history_chars and len(result) > 2:
            removed = result.pop(0)
            total_chars -= len(str(removed.get("content", "")))

        return result


class DeduplicationProcessor(HistoryProcessor):
    """Remove duplicate read_file results for the same path.

    When the model reads the same file multiple times, keep only the
    most recent read. This prevents context flooding from repeated reads.
    """

    def __call__(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not history:
            return []

        # Track last read position for each file path
        last_read: Dict[str, int] = {}
        for i, entry in enumerate(history):
            if entry.get("role") == "tool" and entry.get("name") == "read_file":
                try:
                    args = entry.get("args", {})
                    path = args.get("path", "")
                    if path:
                        last_read[path] = i
                except (AttributeError, TypeError):
                    pass

        # Remove older reads of the same file
        result = []
        for i, entry in enumerate(history):
            if entry.get("role") == "tool" and entry.get("name") == "read_file":
                try:
                    path = entry.get("args", {}).get("path", "")
                    if path and last_read.get(path) != i:
                        continue  # skip older duplicate
                except (AttributeError, TypeError):
                    pass
            result.append(entry)

        return result


class TaggedToolKeepProcessor(HistoryProcessor):
    """Keep specific tool results regardless of age.

    When a tool result is tagged with a keep tag, it won't be clipped
    by the AgeBasedClipper. Useful for keeping important results like
    write_file confirmations or search results.
    """

    KEEP_TAG = "keep_output"

    def __init__(self, tools_to_keep: Optional[set] = None) -> None:
        self.tools_to_keep = tools_to_keep or {"write_file", "edit_file", "search_files"}

    def __call__(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        result = []
        for entry in history:
            entry = dict(entry)
            if entry.get("role") == "tool" and entry.get("name") in self.tools_to_keep:
                tags = set(entry.get("tags", []))
                tags.add(self.KEEP_TAG)
                entry["tags"] = list(tags)
            result.append(entry)
        return result


class RegexRemover(HistoryProcessor):
    """Remove content matching regex patterns from history entries.

    Useful for stripping diff blocks, long stack traces, or other
    repetitive content that wastes context space.
    """

    def __init__(
        self,
        patterns: Optional[List[str]] = None,
        keep_last: int = 2,
    ) -> None:
        self.patterns = patterns or [
            r"<diff>.*?</diff>",
            r"```diff.*?```",
        ]
        self.keep_last = keep_last
        self._compiled = [re.compile(p, re.DOTALL) for p in self.patterns]

    def __call__(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        result = []
        for i, entry in enumerate(history):
            entry = dict(entry)
            # Don't process the last N entries
            if i >= len(history) - self.keep_last:
                result.append(entry)
                continue

            content = entry.get("content", "")
            if isinstance(content, str):
                for pattern in self._compiled:
                    content = pattern.sub("", content)
                entry["content"] = content
            result.append(entry)

        return result


class SummaryInserter(HistoryProcessor):
    """Insert a summary message when history gets too long.

    When history exceeds `threshold_chars`, replaces older entries with
    a single summary entry. The summary is generated by the caller
    (background summarization thread) and set via `set_summary()`.
    """

    def __init__(self, threshold_chars: int = 20000) -> None:
        self.threshold_chars = threshold_chars
        self._summary: Optional[str] = None

    def set_summary(self, summary: Optional[str]) -> None:
        """Set the summary text to inject (or None to disable)."""
        self._summary = summary

    def get_summary(self) -> Optional[str]:
        """Get current summary text."""
        return self._summary

    def __call__(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not self._summary or not history:
            return list(history)

        total_chars = sum(len(str(e.get("content", ""))) for e in history)
        if total_chars <= self.threshold_chars:
            return list(history)

        # Find a good split point: keep the last 4 messages intact
        keep_count = min(4, len(history))
        split_point = len(history) - keep_count

        # Build result: summary + recent messages
        result = [
            {
                "role": "system",
                "content": f"[Previous conversation summary]\n{self._summary}",
                "is_summary": True,
            }
        ]
        result.extend(history[split_point:])
        return result


class HistoryProcessorPipeline:
    """Chain multiple processors into a composable pipeline.

    Example usage:
        pipeline = HistoryProcessorPipeline([
            TaggedToolKeepProcessor(),
            DeduplicationProcessor(),
            AgeBasedClipper(keep_recent=6, clip_recent_chars=2000),
            RegexRemover(),
            SummaryInserter(threshold_chars=20000),
        ])
        processed = pipeline(raw_history)
    """

    def __init__(self, processors: Optional[List[HistoryProcessor]] = None) -> None:
        self.processors: List[HistoryProcessor] = processors or [
            DefaultHistoryProcessor()
        ]

    def add(self, processor: HistoryProcessor) -> "HistoryProcessorPipeline":
        """Add a processor to the end of the pipeline."""
        self.processors.append(processor)
        return self

    def process(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Run history through all processors in order."""
        result = list(history)
        for processor in self.processors:
            result = processor(result)
        return result

    def __call__(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self.process(history)

    def __repr__(self) -> str:
        names = [type(p).__name__ for p in self.processors]
        return f"HistoryProcessorPipeline([{', '.join(names)}])"


def create_default_pipeline(
    keep_recent: int = 6,
    clip_recent_chars: int = 2000,
    clip_old_chars: int = 400,
    max_history_chars: int = 30000,
    summary_threshold: int = 20000,
) -> HistoryProcessorPipeline:
    """Create the default processor pipeline for GGUFLoader agent.

    This matches the current CLIP_RECENT/CLIP_OLD behavior but in a
    composable form that can be extended.
    """
    return HistoryProcessorPipeline([
        TaggedToolKeepProcessor(),
        DeduplicationProcessor(),
        AgeBasedClipper(
            keep_recent=keep_recent,
            clip_recent_chars=clip_recent_chars,
            clip_old_chars=clip_old_chars,
            max_history_chars=max_history_chars,
        ),
        RegexRemover(),
        SummaryInserter(threshold_chars=summary_threshold),
    ])

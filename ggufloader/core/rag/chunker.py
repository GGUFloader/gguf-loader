"""Paragraph-aware text chunker with overlap for RAG ingestion.

Ports GPT4All's chunking strategy (512 chars, last-space split) but
adds 15% overlap so passages straddling chunk boundaries aren't lost.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class Chunk:
    """One piece of a document with its source offset for citation."""

    text: str
    index: int
    char_offset: int  # start position in the original document


def chunk_text(
    text: str,
    *,
    max_chars: int = 512,
    overlap_pct: float = 0.15,
    min_chunk_chars: int = 64,
) -> List[Chunk]:
    """Split *text* into overlapping paragraph-aware chunks.

    Strategy:
    1. Split on double newlines into paragraphs.
    2. Pack paragraphs into chunks up to *max_chars*.
    3. Each new chunk re-includes the tail of the previous chunk
       (up to *overlap_pct* of *max_chars*) for boundary continuity.
    4. Oversized paragraphs are split at sentence boundaries, then
       at word boundaries as a last resort.

    Returns a list of :class:`Chunk` with source offsets.
    """
    if not text or not text.strip():
        return []

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    overlap_budget = int(max_chars * overlap_pct)

    # Split into paragraphs (double newline)
    paragraphs = _split_paragraphs(text)
    if not paragraphs:
        return []

    chunks: List[Chunk] = []
    current_parts: List[str] = []
    current_len = 0
    # Track char offset: we rebuild it as we consume paragraphs
    offset_map = _build_offset_map(text, paragraphs)
    para_idx = 0

    for para in paragraphs:
        para_len = len(para)

        # Check if adding this paragraph exceeds the budget
        separator_len = 2 if current_parts else 0  # "\n\n"
        if current_parts and current_len + separator_len + para_len > max_chars:
            # Emit current chunk
            chunk_text_str = "\n\n".join(current_parts)
            chunk_offset = offset_map[para_idx - len(current_parts)]
            chunks.append(Chunk(
                text=chunk_text_str,
                index=len(chunks),
                char_offset=chunk_offset,
            ))

            # Carry tail for overlap
            tail_parts: List[str] = []
            tail_len = 0
            for prev in reversed(current_parts):
                if tail_len + len(prev) + (2 if tail_parts else 0) > overlap_budget:
                    break
                tail_parts.insert(0, prev)
                tail_len += len(prev) + (2 if tail_parts else 0)

            current_parts = tail_parts
            current_len = tail_len

            # If even the tail + this paragraph overflows, emit tail alone
            if current_parts and current_len + separator_len + para_len > max_chars:
                chunk_text_str = "\n\n".join(current_parts)
                chunk_offset = offset_map[para_idx - len(current_parts)]
                chunks.append(Chunk(
                    text=chunk_text_str,
                    index=len(chunks),
                    char_offset=chunk_offset,
                ))
                current_parts = []
                current_len = 0

        current_parts.append(para)
        current_len += para_len + (2 if len(current_parts) > 1 else 0)
        para_idx += 1

    # Final chunk
    if current_parts:
        chunk_offset = offset_map[para_idx - len(current_parts)]
        chunks.append(Chunk(
            text="\n\n".join(current_parts),
            index=len(chunks),
            char_offset=chunk_offset,
        ))

    return chunks


def _split_paragraphs(text: str) -> List[str]:
    """Split text into non-empty paragraphs."""
    paras = [p.strip() for p in text.split("\n\n")]
    result: List[str] = []
    for p in paras:
        if not p:
            continue
        if len(p) <= 512:
            result.append(p)
        else:
            # Oversized paragraph: split at sentence boundaries
            result.extend(_split_sentences(p))
    return result


def _split_sentences(text: str) -> List[str]:
    """Split oversized text at sentence boundaries, then words."""
    import re
    # Split at sentence-ending punctuation followed by space/newline
    sentences = re.split(r'(?<=[.!?])\s+', text)
    if len(sentences) > 1:
        # Re-group sentences into chunks up to 512 chars
        parts: List[str] = []
        current = ""
        for s in sentences:
            if len(current) + len(s) + 1 > 512:
                if current:
                    parts.append(current)
                # If a single sentence is too long, split by words
                if len(s) > 512:
                    parts.extend(_split_words(s, 512))
                    current = ""
                else:
                    current = s
            else:
                current = (current + " " + s).strip() if current else s
        if current:
            parts.append(current)
        return parts
    return _split_words(text, 512)


def _split_words(text: str, max_chars: int) -> List[str]:
    """Last-resort word-level splitting."""
    words = text.split()
    parts: List[str] = []
    current: List[str] = []
    current_len = 0
    for w in words:
        piece_len = len(w) + (1 if current else 0)
        if current and current_len + piece_len > max_chars:
            parts.append(" ".join(current))
            current = []
            current_len = 0
        current.append(w)
        current_len += piece_len
    if current:
        parts.append(" ".join(current))
    return parts


def _build_offset_map(text: str, paragraphs: List[str]) -> List[int]:
    """Map each paragraph to its character offset in the original text."""
    offsets: List[int] = []
    search_start = 0
    for para in paragraphs:
        idx = text.find(para, search_start)
        if idx == -1:
            # Fallback: approximate
            idx = search_start
        offsets.append(idx)
        search_start = idx + len(para)
    return offsets

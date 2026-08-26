"""RAG ingestion pipeline: walk folders, extract text, chunk, embed, store.

Design mirrors GPT4All's LocalDocs ingestion:
- Walk folder tree (skip .git, __pycache__, node_modules, etc.)
- Extract text from supported file types
- Split into paragraph-aware chunks with overlap
- Generate embeddings via the loaded model (or a dedicated embed model)
- Store in SQLite + FTS5

Embeddings are optional: ingestion proceeds without them (BM25-only mode)
and they're generated on-demand when an embedding model is available.
"""

from __future__ import annotations

import fnmatch
import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Sequence

import numpy as np

from ggufloader.core.rag.chunker import Chunk, chunk_text
from ggufloader.core.rag.store import ChunkStore

logger = logging.getLogger(__name__)

# Directories to skip during folder walk
SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    "dist", "build", ".idea", ".vscode", ".freebuff",
    "chats", "exports", "logs", "cache", "models",
}

# Supported text file patterns
TEXT_PATTERNS = (
    "*.txt", "*.md", "*.rst", "*.py", "*.js", "*.ts", "*.jsx", "*.tsx",
    "*.json", "*.csv", "*.log", "*.yaml", "*.yml", "*.ini", "*.cfg",
    "*.toml", "*.html", "*.css", "*.sql", "*.sh", "*.bat", "*.ps1",
    "*.go", "*.rs", "*.java", "*.kt", "*.swift", "*.c", "*.cpp", "*.h",
    "*.hpp", "*.cs", "*.rb", "*.php", "*.lua", "*.r", "*.m", "*.mm",
)

MAX_FILE_BYTES = 2_000_000  # 2MB per file


@dataclass
class IngestResult:
    """Result of an ingestion run."""

    files_scanned: int = 0
    files_ingested: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    chunks_created: int = 0
    embeddings_generated: int = 0
    elapsed_secs: float = 0.0
    errors: List[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return (
            f"Scanned {self.files_scanned} files, "
            f"ingested {self.files_ingested}, "
            f"created {self.chunks_created} chunks, "
            f"embedded {self.embeddings_generated} "
            f"({self.elapsed_secs:.1f}s)"
        )


def ingest_folder(
    store: ChunkStore,
    folder: str | Path,
    *,
    patterns: Optional[str] = None,
    embed_fn: Optional[Callable[[List[str]], List[np.ndarray]]] = None,
    on_progress: Optional[Callable[[str, int, int], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
    max_files: int = 200,
) -> IngestResult:
    """Walk *folder*, chunk text files, optionally embed, store in *store*.

    Args:
        store: The ChunkStore to write into.
        folder: Root directory to scan.
        patterns: Whitespace/comma-separated fnmatch patterns (default: all text).
        embed_fn: Callable that takes a list of texts and returns embeddings.
                  If None, chunks are stored without embeddings (BM25-only).
        on_progress: Called with (filepath, index, total) per file.
        should_cancel: Checked between files; return True to abort.
        max_files: Hard cap on files processed.
    """
    t0 = time.monotonic()
    result = IngestResult()
    file_patterns = _parse_patterns(patterns)
    paths = _walk_folder(Path(folder), file_patterns, max_files=max_files)
    result.files_scanned = len(paths)
    logger.info("RAG ingest: found %d files in %s", len(paths), folder)

    BATCH_SIZE = 32  # Embed in batches for efficiency

    batch_texts: List[str] = []
    batch_chunks: List[Chunk] = []
    batch_doc_ids: List[int] = []
    batch_doc_paths: List[str] = []

    for idx, path in enumerate(paths):
        if should_cancel and should_cancel():
            logger.info("RAG ingest cancelled at file %d/%d", idx, len(paths))
            break

        if on_progress:
            on_progress(str(path), idx + 1, len(paths))

        try:
            stat = path.stat()
            if stat.st_size > MAX_FILE_BYTES:
                result.files_skipped += 1
                continue
            if not store.document_needs_update(str(path), stat.st_mtime):
                result.files_skipped += 1
                continue

            text = _read_text(path)
            if not text or len(text.strip()) < 20:
                result.files_skipped += 1
                continue

            chunks = chunk_text(text)
            if not chunks:
                result.files_skipped += 1
                continue

            doc_id = store.upsert_document(str(path), stat.st_mtime, stat.st_size)
            texts = [c.text for c in chunks]

            if embed_fn is not None:
                batch_texts.extend(texts)
                batch_chunks.extend(chunks)
                batch_doc_ids.extend([doc_id] * len(chunks))
                batch_doc_paths.extend([str(path)] * len(chunks))

                if len(batch_texts) >= BATCH_SIZE:
                    _flush_embeddings(
                        store, embed_fn, batch_texts, batch_chunks,
                        batch_doc_ids, batch_doc_paths, result,
                    )
                    batch_texts, batch_chunks, batch_doc_ids, batch_doc_paths = [], [], [], []
            else:
                # No embedding function: store without embeddings
                store.replace_chunks(
                    doc_id, texts,
                    embeddings=None,
                    char_offsets=[c.char_offset for c in chunks],
                )

            result.files_ingested += 1
            result.chunks_created += len(chunks)

        except Exception as e:  # noqa: BLE001
            result.files_failed += 1
            result.errors.append(f"{path}: {e}")
            logger.warning("RAG ingest failed for %s: %s", path, e)

    # Flush remaining batch
    if batch_texts and embed_fn is not None:
        _flush_embeddings(
            store, embed_fn, batch_texts, batch_chunks,
            batch_doc_ids, batch_doc_paths, result,
        )

    result.elapsed_secs = time.monotonic() - t0
    logger.info("RAG ingest complete: %s", result.summary)
    return result


def _flush_embeddings(
    store: ChunkStore,
    embed_fn: Callable[[List[str]], List[np.ndarray]],
    texts: List[str],
    chunks: List[Chunk],
    doc_ids: List[int],
    doc_paths: List[str],
    result: IngestResult,
) -> None:
    """Generate embeddings for a batch and store them."""
    try:
        embeddings = embed_fn(texts)
        # Group by document and store
        by_doc: dict = {}  # doc_id -> [(chunk_index, embedding, char_offset)]
        for i, (doc_id, emb, chunk) in enumerate(zip(doc_ids, embeddings, chunks)):
            if doc_id not in by_doc:
                by_doc[doc_id] = []
            by_doc[doc_id].append((chunk.index, emb, chunk.char_offset))

        for doc_id, items in by_doc.items():
            # Get existing texts for this doc
            indices = [idx for idx, _, _ in items]
            embs = [emb for _, emb, _ in items]
            offsets = [off for _, _, off in items]
            texts_batch = [chunks[i].text for i in range(len(chunks))
                          if doc_ids[i] == doc_id]

            store.replace_chunks(
                doc_id, texts_batch, embs,
                char_offsets=offsets,
            )
            result.embeddings_generated += len(embs)

    except Exception as e:  # noqa: BLE001
        logger.warning("Embedding generation failed: %s", e)
        # Store without embeddings as fallback
        by_doc: dict = {}
        for i, (doc_id, chunk) in enumerate(zip(doc_ids, chunks)):
            if doc_id not in by_doc:
                by_doc[doc_id] = ([], [])
            by_doc[doc_id][0].append(chunk.text)
            by_doc[doc_id][1].append(chunk.char_offset)

        for doc_id, (texts_batch, offsets) in by_doc.items():
            store.replace_chunks(doc_id, texts_batch, None, char_offsets=offsets)


def _walk_folder(
    root: Path, patterns: List[str], *, max_files: int = 200
) -> List[Path]:
    """Recursively list matching files under root, skipping noise dirs."""
    found: List[Path] = []

    def _walk(directory: Path) -> None:
        if len(found) >= max_files:
            return
        try:
            with os.scandir(directory) as it:
                entries = list(it)
        except OSError:
            return
        for entry in entries:
            if len(found) >= max_files:
                return
            try:
                if entry.is_dir(follow_symlinks=False):
                    if entry.name not in SKIP_DIRS and not entry.name.startswith("."):
                        _walk(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    if any(fnmatch.fnmatch(entry.name, p) for p in patterns):
                        found.append(Path(entry.path))
            except OSError:
                continue

    _walk(root)
    return sorted(found)


def _read_text(path: Path) -> str:
    """Read a file as text with size and binary guards."""
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    if b"\x00" in data[:8192]:
        return ""  # binary file
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            return data.decode("latin-1")
        except UnicodeDecodeError:
            return ""


def _parse_patterns(patterns: Optional[str]) -> List[str]:
    if not patterns or not patterns.strip():
        return list(TEXT_PATTERNS)
    return [p for p in patterns.replace(",", " ").split() if p]

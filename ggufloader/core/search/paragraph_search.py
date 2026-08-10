"""
Paragraph search without RAG - find the passage that answers a query.

Strategy: split the document into overlapping chunks and ask the loaded
model, per chunk, whether it contains the target passage (and to quote it
verbatim). The LLM's own comprehension is the matcher, so it finds
*semantic* matches ("the part about GPU offloading") with no embeddings,
no vector store, and no new dependencies. Works on any text, of any size:
each chunk call is cheap (greedy, short output), so a 200k-token document
costs a few hundred tiny prompts.

The engine is any callable with the shape of ``ModelBackend.generate``::

    def generate(prompt: str, **kwargs) -> str: ...

``ModelEngine.complete`` fits too: ``lambda prompt, **kw: engine.complete(prompt, **kw)``.
"""

from __future__ import annotations

import fnmatch
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence

CHARS_PER_TOKEN = 4  # rough heuristic: ~4 chars per token for LLM tokenizers

# Directories never scanned by folder search (noise / binaries / vendored).
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv",
             "dist", "build", ".idea", ".vscode", ".freebuff"}

# Common words that carry no search signal; never used as keywords.
STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "about", "how", "what", "why", "where", "when", "who", "which", "is",
    "are", "was", "were", "be", "been", "being", "do", "does", "did", "can",
    "could", "would", "should", "will", "this", "that", "these", "those", "it",
    "its", "find", "found", "passage", "paragraph", "section", "search",
    "looking", "explain", "tell", "me", "show", "give", "need", "want", "from",
    "into", "over", "under", "at", "by", "as", "if", "then", "than", "so",
    "not", "no", "yes", "has", "have", "had", "they", "them", "their", "there",
}

# Files with at most this many chunks are always scanned fully in light mode:
# a handful of model calls is cheap and much more robust than keyword-gating.
SMALL_FILE_CHUNKS = 2

# Responses the model gives when a chunk does NOT contain the passage.
_NO_RESPONSES = ("no", "no.", "no,", "no passage", "not found", "not present",
                 "does not contain", "doesn't contain", "no matching")

GenerateFn = Callable[..., str]


@dataclass
class Hit:
    """One located passage, quoted by the model."""

    text: str
    chunk_index: int
    source: str = ""  # file path when searching a folder

    def to_dict(self) -> dict:
        return {"text": self.text, "chunk_index": self.chunk_index, "source": self.source}


class ParagraphSearcher:
    """Chunked-LLM paragraph search against a loaded model."""

    def __init__(
        self,
        generate: GenerateFn,
        *,
        chunk_tokens: int = 1000,
        overlap_tokens: int = 120,
        max_chunks: Optional[int] = None,
        max_tokens: int = 400,
    ) -> None:
        self._generate = generate
        self.chunk_tokens = chunk_tokens
        self.overlap_tokens = overlap_tokens
        self.max_chunks = max_chunks
        self.max_tokens = max_tokens
        self._chunk_budget = max(chunk_tokens, 50) * CHARS_PER_TOKEN
        self._overlap_budget = max(overlap_tokens, 0) * CHARS_PER_TOKEN

    # ------------------------------------------------------------------
    # Chunking
    # ------------------------------------------------------------------
    def split(self, text: str) -> List[str]:
        """Split *text* into overlapping, paragraph-aware chunks.

        Paragraphs are packed into chunks up to ``chunk_tokens``; each new
        chunk re-includes the previous chunk's trailing paragraphs (up to
        ``overlap_tokens``) so a passage straddling a boundary is still seen
        whole. Oversized paragraphs are split at newlines, then at words.
        """
        text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
        blocks = self._to_blocks(text)
        if not blocks:
            return []

        chunks: List[str] = []
        cur: List[str] = []
        cur_chars = 0

        for block in blocks:
            b_chars = len(block)
            if cur and cur_chars + b_chars > self._chunk_budget:
                chunks.append("\n\n".join(cur))
                # Carry the tail of the finished chunk into the next one.
                tail: List[str] = []
                tail_chars = 0
                for prev in reversed(cur):
                    if tail_chars + len(prev) > self._overlap_budget:
                        break
                    tail.insert(0, prev)
                    tail_chars += len(prev)
                cur = tail
                cur_chars = tail_chars
                # If the overlap tail plus this block still overflows, emit
                # the tail alone so no chunk exceeds the budget.
                if cur and cur_chars + b_chars > self._chunk_budget:
                    chunks.append("\n\n".join(cur))
                    cur = []
                    cur_chars = 0
            cur.append(block)
            cur_chars += b_chars

        if cur:
            chunks.append("\n\n".join(cur))
        return chunks

    def _to_blocks(self, text: str) -> List[str]:
        """Break *text* into blocks, each at most one chunk in size."""
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text)]
        paragraphs = [p for p in paragraphs if p]
        if not paragraphs:
            # No blank-line separation: fall back to whole lines.
            paragraphs = [l.strip() for l in text.split("\n") if l.strip()]

        blocks: List[str] = []
        for para in paragraphs:
            if len(para) <= self._chunk_budget:
                blocks.append(para)
                continue
            # A single paragraph larger than a chunk: split by lines first.
            lines = [l.strip() for l in para.split("\n") if l.strip()]
            if len(lines) > 1:
                blocks.extend(self._split_oversized(lines))
            else:
                # One giant line: split at word boundaries.
                blocks.extend(self._split_words(para))
        return blocks

    def _split_oversized(self, items: List[str]) -> List[str]:
        blocks: List[str] = []
        cur: List[str] = []
        cur_chars = 0
        for item in items:
            if len(item) > self._chunk_budget:
                if cur:
                    blocks.append("\n".join(cur))
                    cur, cur_chars = [], 0
                blocks.extend(self._split_words(item))
                continue
            if cur and cur_chars + len(item) > self._chunk_budget:
                blocks.append("\n".join(cur))
                cur, cur_chars = [], 0
            cur.append(item)
            cur_chars += len(item)
        if cur:
            blocks.append("\n".join(cur))
        return blocks

    def _split_words(self, text: str) -> List[str]:
        words = text.split(" ")
        blocks: List[str] = []
        cur: List[str] = []
        cur_chars = 0
        for word in words:
            piece = (word + " ") if word else ""
            if cur and cur_chars + len(piece) > self._chunk_budget:
                blocks.append(" ".join(cur))
                cur, cur_chars = [], 0
            cur.append(word)
            cur_chars += len(piece)
        if cur:
            blocks.append(" ".join(cur))
        return blocks

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def search(
        self,
        query: str,
        text: str,
        *,
        on_progress: Optional[Callable[[int, int], None]] = None,
        on_hit: Optional[Callable[[Hit], None]] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
    ) -> List[Hit]:
        """Find passages in *text* answering *query*.

        Scans every chunk with the model; each chunk that contains the
        passage yields a :class:`Hit` (the model's verbatim quote).
        Identical/overlapping quotes are merged at the end. ``on_progress``
        is called as ``(done, total)`` after each chunk; ``should_cancel``
        (if given) stops the scan between chunks.
        """
        chunks = self.split(text)
        if self.max_chunks is not None:
            chunks = chunks[:max(self.max_chunks, 0)]
        total = len(chunks)
        hits = self._scan(
            query, chunks, range(len(chunks)),
            on_progress=on_progress, on_hit=on_hit, should_cancel=should_cancel,
            offset=0, total=total,
        )
        return self._dedupe(hits)

    def _scan(
        self,
        query: str,
        chunks: Sequence[str],
        indices: Iterable[int],
        *,
        on_progress: Optional[Callable[[int, int], None]] = None,
        on_hit: Optional[Callable[[Hit], None]] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
        offset: int = 0,
        total: int,
    ) -> List[Hit]:
        """Ask the model about ``chunks[i]`` for every ``i`` in *indices*.

        Shared by :meth:`search` (all indices) and folder search (a
        keyword-selected subset). ``offset``/``total`` shape the progress
        reports so multi-file scans count up across files.
        """
        hits: List[Hit] = []
        for pos, i in enumerate(indices):
            if should_cancel is not None and should_cancel():
                break
            answer = self._ask(query, chunks[i])
            passage = self._extract_passage(answer)
            if passage:
                hit = Hit(passage, i)
                hits.append(hit)
                if on_hit is not None:
                    on_hit(hit)
            if on_progress is not None:
                on_progress(offset + pos + 1, total)
        return hits

    # ------------------------------------------------------------------
    # Folder search
    # ------------------------------------------------------------------
    def search_folder(
        self,
        query: str,
        folder: str | Path,
        *,
        patterns: Optional[str] = None,
        max_files: int = 50,
        max_bytes_per_file: int = 2_000_000,
        exhaustive: bool = False,
        keywords: Optional[Sequence[str]] = None,
        files: Optional[Sequence[str]] = None,
        on_progress: Optional[Callable[[int, int], None]] = None,
        on_hit: Optional[Callable[[Hit], None]] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
        on_file_started: Optional[Callable[[str, int, int], None]] = None,
    ) -> List[Hit]:
        """Search matching files under *folder*, aggregating hits.

        Light mode (default) keeps the model calls to a minimum: files are
        first probed for query keywords at the byte level (never even
        decoded if they miss), and within a surviving file only chunks
        that contain a keyword are scanned (small files are scanned fully).
        ``keywords`` (e.g. from a :class:`~core.search.planner.SearchPlanner`)
        overrides the crude query-derived extraction; if the provided
        keywords match nothing, the scan transparently falls back to the
        query's own keywords. ``files`` restricts the scan to those
        workspace-relative paths (from the planner's decision tree).
        ``exhaustive=True`` scans every chunk of every file - correct but
        expensive on large workspaces. ``on_file_started`` reports
        ``(path, 1-based index, file count)`` before each file is scanned;
        ``on_progress`` reports ``(done, total)`` per file. Each hit
        carries its source file; identical passages found in multiple
        files merge in the final dedup.
        """
        if files:
            paths = self._resolve_files(folder, files)
        else:
            paths = self.glob_files(folder, patterns, max_files=max_files)
        provided = keywords is not None
        keywords = list(keywords) if keywords else extract_keywords(query)
        light = not exhaustive and bool(keywords)

        files = self._probe_files(paths, keywords, light, max_bytes=max_bytes_per_file)
        # Planner keywords may miss the corpus entirely; retry with the
        # query's own words before spending any model calls.
        if light and not files and provided:
            fallback = extract_keywords(query)
            if fallback:
                keywords = fallback
                files = self._probe_files(paths, keywords, light, max_bytes=max_bytes_per_file)

        # Per-file chunk selection (light mode: keyword-bearing chunks only).
        scanned: List[tuple[Path, Sequence[str], List[int]]] = []
        for path, text in files:
            chunks = self.split(text)
            if light and len(chunks) > SMALL_FILE_CHUNKS:
                idxs = [i for i, c in enumerate(chunks) if _chunk_score(c, keywords) > 0]
            else:
                idxs = list(range(len(chunks)))
            scanned.append((path, chunks, idxs))

        return self._finish_folder_scan(
            scanned, query,
            on_progress=on_progress, on_hit=on_hit,
            should_cancel=should_cancel, on_file_started=on_file_started,
        )

    @staticmethod
    def _resolve_files(folder: str | Path, files: Sequence[str]) -> List[Path]:
        """Resolve planner-selected relative paths, skipping escapes/misses."""
        root = Path(folder).resolve()
        paths: List[Path] = []
        for rel in files:
            candidate = (root / rel).resolve()
            if candidate != root and root not in candidate.parents:
                continue  # escape attempt - ignore
            if candidate.is_file():
                paths.append(candidate)
        return paths

    def _probe_files(
        self,
        paths: Sequence[Path],
        keywords: Sequence[str],
        light: bool,
        *,
        max_bytes: int,
    ) -> List[tuple[Path, str]]:
        """Read+decode files whose bytes contain a keyword (byte-level probe)."""
        files: List[tuple[Path, str]] = []
        for path in paths:
            data = _read_bytes(path, max_bytes=max_bytes)
            if not data:
                continue
            if light and not _bytes_hit(data, keywords):
                continue
            text = _decode(data)
            if text:
                files.append((path, text))
        return files

    def _finish_folder_scan(
        self,
        scanned: Sequence[tuple[Path, Sequence[str], List[int]]],
        query: str,
        *,
        on_progress, on_hit, should_cancel, on_file_started,
    ) -> List[Hit]:
        """Run the per-file chunk scans collected by :meth:`search_folder`."""
        hits: List[Hit] = []
        file_count = len(scanned)
        for file_index, (path, chunks, idxs) in enumerate(scanned, start=1):
            if should_cancel is not None and should_cancel():
                break
            if on_file_started is not None:
                on_file_started(str(path), file_index, file_count)

            def hit_cb(hit: Hit, _path: Path = path) -> None:
                hit.source = str(_path)
                if on_hit is not None:
                    on_hit(hit)

            hits.extend(
                self._scan(
                    query, chunks, idxs,
                    on_progress=on_progress, on_hit=hit_cb,
                    should_cancel=should_cancel,
                    offset=0, total=len(idxs),
                )
            )
        return self._dedupe(hits)

        file_count = len(scanned)
        hits: List[Hit] = []
        for file_index, (path, chunks, idxs) in enumerate(scanned, start=1):
            if should_cancel is not None and should_cancel():
                break
            if on_file_started is not None:
                on_file_started(str(path), file_index, file_count)

            def hit_cb(hit: Hit, _path: Path = path) -> None:
                hit.source = str(_path)
                if on_hit is not None:
                    on_hit(hit)

            hits.extend(
                self._scan(
                    query, chunks, idxs,
                    on_progress=on_progress, on_hit=hit_cb,
                    should_cancel=should_cancel,
                    offset=0, total=len(idxs),
                )
            )

        return self._dedupe(hits)

    @staticmethod
    def glob_files(
        folder: str | Path,
        patterns: Optional[str] = None,
        *,
        max_files: int = 50,
    ) -> List[Path]:
        """Recursively list text-ish files under *folder* matching *patterns*.

        ``patterns`` is whitespace/comma-separated fnmatch patterns (e.g.
        ``"*.txt *.md"``); defaults to common text extensions. Hidden
        build/dependency directories in :data:`SKIP_DIRS` are skipped.
        """
        pats = _parse_patterns(patterns)
        root = Path(folder)
        found: List[Path] = []

        def _walk(directory: Path) -> None:
            """Depth-first walk that never descends into SKIP_DIRS.

            Uses ``os.scandir`` (each DirEntry carries its stat info, so no
            extra per-file syscall) and stops descending into build/dependency
            directories - previously ``rglob`` walked the *entire* tree
            (e.g. .venv's thousands of files) before filtering.
            """
            try:
                with os.scandir(directory) as it:
                    entries = list(it)
            except OSError:
                return
            for entry in entries:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in SKIP_DIRS:
                            _walk(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        if any(fnmatch.fnmatch(entry.name, p) for p in pats):
                            found.append(Path(entry.path))
                except OSError:
                    continue

        _walk(root)
        # Deterministic alphabetical order, capped like before.
        return sorted(found)[:max_files]

    def _ask(self, query: str, chunk: str) -> str:
        prompt = (
            "You are scanning a document to locate a specific passage.\n\n"
            f"Query: {query}\n\n"
            "Below is one section of the document, between the markers.\n"
            "If this section contains the passage that answers the query, "
            "reply with ONLY that passage, quoted verbatim from the section, "
            'with no commentary and no "Here it is:" prefix.\n'
            "If the section does NOT contain the passage, reply with exactly: NO\n\n"
            "=== SECTION ===\n"
            f"{chunk}"
        )
        return self._generate(prompt, max_tokens=self.max_tokens, temperature=0.0)

    def _extract_passage(self, answer: str) -> Optional[str]:
        resp = (answer or "").strip()
        low = resp.lower()
        if low in _NO_RESPONSES:
            return None
        if low.startswith(_NO_RESPONSES[2:]):  # "no," / "no passage" / ...
            return None
        # Strip a pair of surrounding quotation marks the model may add.
        if len(resp) >= 2 and resp[0] == resp[-1] and resp[0] in ("\"", "'"):
            resp = resp[1:-1].strip()
        return resp or None

    @staticmethod
    def _dedupe(hits: List[Hit]) -> List[Hit]:
        """Merge duplicate/overlapping quotes from neighboring chunks.

        Keeps the longest quote when one hit's text is contained in another
        (overlapping chunks quote the same passage). Preserves order.
        """
        def norm(s: str) -> str:
            return re.sub(r"\s+", " ", s).strip().lower()

        # Normalize each hit exactly once; the containment checks below only
        # ever compare precomputed strings (previously norm() - a regex sub -
        # ran on every comparison, making this O(n^2) regex work).
        deduped: List[Hit] = []
        norms: List[str] = []
        for hit in hits:
            n = norm(hit.text)
            if not n:
                continue
            replaced = False
            for j, en in enumerate(norms):
                if n == en or n in en:  # duplicate or covered by longer quote
                    replaced = True
                    break
                if en in n:  # this quote is more complete - swap it in
                    deduped[j] = hit
                    norms[j] = n
                    replaced = True
                    break
            if not replaced:
                deduped.append(hit)
                norms.append(n)
        return deduped


DEFAULT_PATTERNS = (
    "*.txt *.md *.py *.json *.log *.csv *.html "
    "*.js *.ts *.yml *.yaml *.ini *.cfg *.toml"
)


def _parse_patterns(patterns: Optional[str]) -> List[str]:
    if not patterns or not patterns.strip():
        return DEFAULT_PATTERNS.split()
    return [p for p in re.split(r"[\s,]+", patterns.strip()) if p]


def extract_keywords(query: str, max_keywords: int = 6) -> List[str]:
    """Pull search keywords out of a natural-language *query*.

    Lowercases, drops stopwords and tokens shorter than 3 ASCII characters
    (2 for non-ASCII, e.g. Persian), dedupes, and caps the list. Used by
    light-mode folder search to decide which files/chunks the model must
    actually read. Returns [] when nothing useful survives (short/foreign
    queries) - callers then fall back to exhaustive scanning.
    """
    seen: set = set()
    out: List[str] = []
    for tok in re.findall(r"\w+", (query or "").lower(), flags=re.UNICODE):
        min_len = 2 if not tok.isascii() else 3
        if len(tok) < min_len or tok in STOPWORDS:
            continue
        if tok not in seen:
            seen.add(tok)
            out.append(tok)
            if len(out) >= max_keywords:
                break
    return out


def _read_bytes(path: Path, *, max_bytes: int) -> bytes:
    """Read *path* bounded by *max_bytes*; b"" on error or oversize."""
    try:
        if path.stat().st_size > max_bytes:
            return b""
        return path.read_bytes()
    except OSError:
        return b""


def _decode(data: bytes) -> str:
    """Decode bytes to text, skipping binary (NUL sniff) content."""
    if b"\x00" in data[:8192]:
        return ""
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            return data.decode("latin-1")
        except UnicodeDecodeError:
            return ""


def _bytes_hit(data: bytes, keywords: Sequence[str]) -> bool:
    """True if any *keyword* appears in *data* (ASCII case-insensitive)."""
    low = data.lower()
    return any(k.encode("utf-8") in low for k in keywords)


def _chunk_score(chunk: str, keywords: Sequence[str]) -> int:
    """Count keyword occurrences in *chunk* (ASCII case-insensitive)."""
    low = chunk.lower()
    return sum(low.count(k) for k in keywords)


def read_text_file(path: str | Path, *, max_bytes: int = 2_000_000) -> str:
    """Read *path* as text with a size cap and a binary guard.

    Skips files that look binary (NUL bytes) and returns "" for anything
    over *max_bytes*. Tries UTF-8 (BOM-aware) first, then Latin-1.
    """
    p = Path(path)
    try:
        if p.stat().st_size > max_bytes:
            return ""
        data = p.read_bytes()
    except OSError:
        return ""
    if b"\x00" in data[:8192]:
        return ""
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            return data.decode("latin-1")
        except UnicodeDecodeError:
            return ""

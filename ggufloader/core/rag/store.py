"""SQLite + FTS5 store for RAG document chunks with embedding BLOBs.

Schema mirrors GPT4All's LocalDocs v3: one ``documents`` table tracking
ingested files, one ``chunks`` table with text + float32 embedding blobs,
and an FTS5 virtual table for BM25 keyword search.

Embeddings are stored as raw float32 BLOBs (numpy.frombuffer on read).
The FTS5 table uses porter stemming + unicode61 tokenizer for robust
BM25 ranking.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 1

_DDL = """\
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    path      TEXT UNIQUE NOT NULL,
    mtime     REAL NOT NULL,
    size      INTEGER NOT NULL DEFAULT 0,
    ingested  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chunks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id       INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index  INTEGER NOT NULL,
    text         TEXT NOT NULL,
    embedding    BLOB,
    char_offset  INTEGER NOT NULL DEFAULT 0,
    UNIQUE(doc_id, chunk_index)
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text,
    content=chunks,
    content_rowid=id,
    tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
END;

CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.id, old.text);
END;

CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES ('delete', old.id, old.text);
    INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
END;
"""


class ChunkStore:
    """SQLite-backed store for document chunks with FTS5 + embedding BLOBs."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._conn: Optional[sqlite3.Connection] = None
        self._open()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _open(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_DDL)
        # Schema version for future migrations
        cur = self._conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        )
        row = cur.fetchone()
        if row is None:
            self._conn.execute(
                "INSERT INTO meta(key, value) VALUES('schema_version', ?)",
                (str(_SCHEMA_VERSION),),
            )
            self._conn.commit()
        logger.info("RAG store opened: %s", self._db_path)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Documents
    # ------------------------------------------------------------------

    def upsert_document(self, path: str, mtime: float, size: int) -> int:
        """Insert or update a document record; returns its id."""
        assert self._conn is not None
        cur = self._conn.execute(
            "SELECT id FROM documents WHERE path = ?", (path,)
        )
        row = cur.fetchone()
        if row is not None:
            doc_id = row[0]
            self._conn.execute(
                "UPDATE documents SET mtime=?, size=? WHERE id=?",
                (mtime, size, doc_id),
            )
        else:
            cur = self._conn.execute(
                "INSERT INTO documents(path, mtime, size) VALUES(?, ?, ?)",
                (path, mtime, size),
            )
            doc_id = cur.lastrowid
        self._conn.commit()
        return doc_id

    def delete_document(self, path: str) -> None:
        """Delete a document and all its chunks."""
        assert self._conn is not None
        self._conn.execute("DELETE FROM chunks WHERE doc_id IN "
                           "(SELECT id FROM documents WHERE path=?)", (path,))
        self._conn.execute("DELETE FROM documents WHERE path=?", (path,))
        self._conn.commit()

    def document_needs_update(self, path: str, mtime: float) -> bool:
        """True if the file has changed since last ingestion."""
        assert self._conn is not None
        cur = self._conn.execute(
            "SELECT mtime FROM documents WHERE path=?", (path,)
        )
        row = cur.fetchone()
        return row is None or abs(row[0] - mtime) > 0.01

    def list_documents(self) -> List[Dict[str, Any]]:
        """Return all ingested documents."""
        assert self._conn is not None
        cur = self._conn.execute(
            "SELECT id, path, mtime, size, ingested FROM documents ORDER BY path"
        )
        return [
            {"id": r[0], "path": r[1], "mtime": r[2], "size": r[3],
             "ingested": r[4]}
            for r in cur.fetchall()
        ]

    # ------------------------------------------------------------------
    # Chunks
    # ------------------------------------------------------------------

    def replace_chunks(
        self,
        doc_id: int,
        texts: Sequence[str],
        embeddings: Optional[Sequence[np.ndarray]],
        char_offsets: Optional[Sequence[int]] = None,
    ) -> None:
        """Delete old chunks for *doc_id* and insert fresh ones."""
        assert self._conn is not None
        self._conn.execute("DELETE FROM chunks WHERE doc_id=?", (doc_id,))
        for i, text in enumerate(texts):
            emb_blob = _encode_embedding(embeddings[i]) if embeddings and i < len(embeddings) else None
            offset = char_offsets[i] if char_offsets and i < len(char_offsets) else 0
            self._conn.execute(
                "INSERT INTO chunks(doc_id, chunk_index, text, embedding, char_offset) "
                "VALUES (?, ?, ?, ?, ?)",
                (doc_id, i, text, emb_blob, offset),
            )
        self._conn.commit()

    def count_chunks(self) -> int:
        assert self._conn is not None
        cur = self._conn.execute("SELECT COUNT(*) FROM chunks")
        return cur.fetchone()[0]

    def count_documents(self) -> int:
        assert self._conn is not None
        cur = self._conn.execute("SELECT COUNT(*) FROM documents")
        return cur.fetchone()[0]

    # ------------------------------------------------------------------
    # BM25 search
    # ------------------------------------------------------------------

    def bm25_search(
        self, query: str, top_k: int = 10
    ) -> List[Tuple[int, str, float, str]]:
        """FTS5 BM25 search; returns [(chunk_id, text, score, doc_path)]."""
        assert self._conn is not None
        # FTS5 bm25() returns negative scores (lower = better); negate for ranking
        cur = self._conn.execute(
            """
            SELECT c.id, c.text, bm25(chunks_fts) AS score, d.path
            FROM chunks_fts fts
            JOIN chunks c ON c.id = fts.rowid
            JOIN documents d ON d.id = c.doc_id
            WHERE chunks_fts MATCH ?
            ORDER BY score
            LIMIT ?
            """,
            (query, top_k),
        )
        return [(r[0], r[1], -r[2], r[3]) for r in cur.fetchall()]

    # ------------------------------------------------------------------
    # Embedding search (brute-force inner product)
    # ------------------------------------------------------------------

    def vector_search(
        self, query_embedding: np.ndarray, top_k: int = 10
    ) -> List[Tuple[int, str, float, str]]:
        """Brute-force inner-product search; returns [(chunk_id, text, score, doc_path)]."""
        assert self._conn is not None
        cur = self._conn.execute(
            """
            SELECT c.id, c.text, c.embedding, d.path
            FROM chunks c
            JOIN documents d ON d.id = c.doc_id
            WHERE c.embedding IS NOT NULL
            """
        )
        dim = len(query_embedding)
        q = query_embedding.astype(np.float32)
        q_norm = np.linalg.norm(q)
        if q_norm > 0:
            q = q / q_norm

        results: List[Tuple[int, str, float, str]] = []
        for row in cur.fetchall():
            chunk_id, text, emb_blob, doc_path = row
            if emb_blob is None:
                continue
            emb = _decode_embedding(emb_blob, dim)
            if emb is None:
                continue
            e_norm = np.linalg.norm(emb)
            if e_norm > 0:
                emb = emb / e_norm
            score = float(np.dot(q, emb))
            results.append((chunk_id, text, score, doc_path))

        results.sort(key=lambda x: -x[2])
        return results[:top_k]


# ------------------------------------------------------------------
# Embedding serialization
# ------------------------------------------------------------------

def _encode_embedding(emb: np.ndarray) -> bytes:
    """Pack a float32 numpy array into bytes for SQLite BLOB storage."""
    return emb.astype(np.float32).tobytes()


def _decode_embedding(blob: bytes, expected_dim: int) -> Optional[np.ndarray]:
    """Unpack a float32 BLOB back into a numpy array."""
    try:
        arr = np.frombuffer(blob, dtype=np.float32)
        if len(arr) != expected_dim:
            return None
        return arr
    except Exception:  # noqa: BLE001
        return None

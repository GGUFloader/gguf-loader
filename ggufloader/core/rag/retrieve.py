"""Retrieval engine combining vector similarity + BM25 via RRF fusion.

Ports GPT4All's hybrid retrieval design:
- Vector inner product (numpy brute-force, fine for <1M chunks)
- FTS5 BM25 with porter stemming
- Reciprocal Rank Fusion (RRF) with k=60, BM25 weight 0.9

The fusion formula per GPT4All v3:
    score(d) = sum( 1 / (k + rank_i(d)) )  for each retrieval method
    with BM25 weighted 0.9 and vector weighted 0.1
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from ggufloader.core.rag.store import ChunkStore

logger = logging.getLogger(__name__)

# RRF parameters (from GPT4All v3 LocalDocs)
RRF_K = 60
BM25_WEIGHT = 0.9
VECTOR_WEIGHT = 0.1


@dataclass
class RetrievedChunk:
    """One retrieved chunk with source info for citation."""

    text: str
    doc_path: str
    chunk_id: int
    score: float = 0.0
    char_offset: int = 0

    def to_context_block(self, max_chars: int = 1500) -> str:
        """Format as a citation block for prompt injection."""
        source = self.doc_path
        # Shorten path for display
        parts = source.replace("\\", "/").split("/")
        if len(parts) > 3:
            source = ".../" + "/".join(parts[-2:])
        preview = self.text[:max_chars]
        if len(self.text) > max_chars:
            preview += "..."
        return f"[Source: {source}]\n{preview}"


class Retriever:
    """Hybrid vector + BM25 retriever with RRF fusion."""

    def __init__(
        self,
        store: ChunkStore,
        *,
        rrf_k: int = RRF_K,
        bm25_weight: float = BM25_WEIGHT,
        vector_weight: float = VECTOR_WEIGHT,
    ) -> None:
        self._store = store
        self._rrf_k = rrf_k
        self._bm25_weight = bm25_weight
        self._vector_weight = vector_weight

    def search(
        self,
        query: str,
        query_embedding: Optional[np.ndarray] = None,
        *,
        top_k: int = 3,
        min_score: float = 0.01,
    ) -> List[RetrievedChunk]:
        """Hybrid search fusing BM25 and vector similarity.

        When *query_embedding* is None (no embedding model loaded),
        falls back to BM25-only search.
        """
        bm25_results = self._bm25_search(query, top_k=top_k * 2)
        vector_results = (
            self._vector_search(query_embedding, top_k=top_k * 2)
            if query_embedding is not None
            else []
        )

        if not bm25_results and not vector_results:
            return []

        # RRF fusion
        fused = self._rrf_fuse(bm25_results, vector_results)

        # Filter low scores and deduplicate
        seen_texts: set = set()
        results: List[RetrievedChunk] = []
        for chunk_id, score, text, doc_path, char_offset in fused:
            if score < min_score:
                continue
            # Deduplicate by first 100 chars
            key = text[:100].strip().lower()
            if key in seen_texts:
                continue
            seen_texts.add(key)
            results.append(RetrievedChunk(
                text=text,
                doc_path=doc_path,
                chunk_id=chunk_id,
                score=score,
                char_offset=char_offset,
            ))
            if len(results) >= top_k:
                break

        logger.info(
            "RAG retrieved %d chunks (bm25=%d, vector=%d) for query '%s'",
            len(results), len(bm25_results), len(vector_results), query[:50],
        )
        return results

    def _bm25_search(
        self, query: str, top_k: int = 10
    ) -> List[tuple]:
        """FTS5 BM25 search returning [(chunk_id, score, text, doc_path, offset)]."""
        try:
            # Pre-process query for FTS5: prefix-match each term
            terms = [t for t in re.findall(r'\w+', query.lower()) if len(t) >= 2]
            if not terms:
                return []
            # Use OR matching with prefix for recall
            fts_query = " OR ".join(f'"{t}"*' for t in terms)
            results = self._store.bm25_search(fts_query, top_k=top_k)
            # Fetch char_offsets
            enriched = []
            for chunk_id, text, score, doc_path in results:
                enriched.append((chunk_id, score, text, doc_path, 0))
            return enriched
        except Exception as e:  # noqa: BLE001
            logger.debug("BM25 search failed: %s", e)
            return []

    def _vector_search(
        self, query_embedding: np.ndarray, top_k: int = 10
    ) -> List[tuple]:
        """Vector inner-product search."""
        try:
            results = self._store.vector_search(query_embedding, top_k=top_k)
            return [(cid, score, text, path, 0) for cid, text, score, path in results]
        except Exception as e:  # noqa: BLE001
            logger.debug("Vector search failed: %s", e)
            return []

    def _rrf_fuse(
        self,
        bm25_results: List[tuple],
        vector_results: List[tuple],
    ) -> List[tuple]:
        """Reciprocal Rank Fusion of BM25 and vector results.

        Returns [(chunk_id, fused_score, text, doc_path, char_offset)]
        sorted by descending score.
        """
        scores: dict = {}  # chunk_id -> (score, text, doc_path, offset)

        # BM25 contributions
        for rank, (cid, _bm_score, text, doc_path, offset) in enumerate(bm25_results):
            rrf = self._bm25_weight / (self._rrf_k + rank + 1)
            if cid in scores:
                scores[cid] = (scores[cid][0] + rrf, text, doc_path, offset)
            else:
                scores[cid] = (rrf, text, doc_path, offset)

        # Vector contributions
        for rank, (cid, _v_score, text, doc_path, offset) in enumerate(vector_results):
            rrf = self._vector_weight / (self._rrf_k + rank + 1)
            if cid in scores:
                scores[cid] = (scores[cid][0] + rrf, text, doc_path, offset)
            else:
                scores[cid] = (rrf, text, doc_path, offset)

        # Sort by fused score descending
        fused = [
            (cid, score, text, doc_path, offset)
            for cid, (score, text, doc_path, offset) in scores.items()
        ]
        fused.sort(key=lambda x: -x[1])
        return fused

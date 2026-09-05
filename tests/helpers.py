"""Shared test doubles: a deterministic embedder and an in-memory vector store.

These let the loader -> chunker -> ingest -> retrieve pipeline be tested without
downloading the real sentence-transformers model (no torch needed).
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Sequence

from rag import config
from rag.vector_store import Retrieved, VectorStore

_WORD = re.compile(r"\w+")


def _token_bucket(token: str, dim: int) -> int:
    digest = hashlib.md5(token.encode("utf-8")).hexdigest()
    return int(digest, 16) % dim


def hashing_embed(texts: Sequence[str], dim: int = 64) -> list[list[float]]:
    """Deterministic bag-of-words hashing embedding, L2-normalised.

    Shares direction between texts with overlapping vocabulary, so nearest
    neighbour search returns sensible results in tests.
    """
    vectors: list[list[float]] = []
    for text in texts:
        vec = [0.0] * dim
        for token in _WORD.findall(text.lower()):
            vec[_token_bucket(token, dim)] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        vectors.append([v / norm for v in vec])
    return vectors


def _cosine_distance(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return 1.0 - dot


class InMemoryVectorStore(VectorStore):
    """Minimal VectorStore backed by a dict; brute-force cosine search."""

    def __init__(self) -> None:
        self._rows: dict[str, tuple[list[float], str, dict]] = {}

    def add(self, ids, embeddings, documents, metadatas) -> None:
        for id_, emb, doc, meta in zip(ids, embeddings, documents, metadatas):
            self._rows[id_] = (list(emb), doc, dict(meta))

    def query(self, embedding, top_k=None) -> list[Retrieved]:
        top_k = top_k or config.TOP_K
        scored = sorted(
            (
                (_cosine_distance(embedding, emb), doc, meta)
                for emb, doc, meta in self._rows.values()
            ),
            key=lambda row: row[0],
        )
        return [
            Retrieved(text=doc, metadata=meta, distance=dist)
            for dist, doc, meta in scored[:top_k]
        ]

    def count(self) -> int:
        return len(self._rows)

    def reset(self) -> None:
        self._rows.clear()

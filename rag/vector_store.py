"""Vector store abstraction + ChromaDB implementation (plan step 5).

Call sites depend only on :class:`VectorStore`; Phase 2 adds a
``PineconeVectorStore`` behind the same interface with no changes elsewhere.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence

from rag import config

Vector = Sequence[float]


@dataclass
class Retrieved:
    """One search hit: the chunk text, its metadata, and the cosine distance."""

    text: str
    metadata: dict
    distance: float

    @property
    def source(self) -> str:
        return self.metadata.get("source", "")

    @property
    def page(self) -> int | None:
        return self.metadata.get("page")


class VectorStore(ABC):
    @abstractmethod
    def add(
        self,
        ids: Sequence[str],
        embeddings: Sequence[Vector],
        documents: Sequence[str],
        metadatas: Sequence[dict],
    ) -> None:
        """Insert or update chunks (idempotent on ``ids``)."""

    @abstractmethod
    def query(self, embedding: Vector, top_k: int | None = None) -> list[Retrieved]:
        """Return up to ``top_k`` nearest chunks, closest first."""

    @abstractmethod
    def count(self) -> int:
        """Number of chunks currently stored."""

    @abstractmethod
    def reset(self) -> None:
        """Delete everything in the collection."""


def _clean_metadata(meta: dict | None) -> dict:
    """Chroma only accepts str/int/float/bool values and rejects empty dicts."""
    cleaned = {k: v for k, v in (meta or {}).items() if v is not None}
    return cleaned or {"source": "unknown"}


class ChromaVectorStore(VectorStore):
    def __init__(
        self, path: str | None = None, collection_name: str | None = None
    ) -> None:
        import chromadb

        self._collection_name = collection_name or config.COLLECTION_NAME
        self._client = chromadb.PersistentClient(
            path=str(path or config.CHROMA_DIR),
            settings=chromadb.Settings(anonymized_telemetry=False),
        )
        self._collection = self._get_or_create()

    def _get_or_create(self):
        return self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add(self, ids, embeddings, documents, metadatas) -> None:
        ids = list(ids)
        if not ids:
            return
        self._collection.upsert(
            ids=ids,
            embeddings=[list(e) for e in embeddings],
            documents=list(documents),
            metadatas=[_clean_metadata(m) for m in metadatas],
        )

    def query(self, embedding, top_k=None) -> list[Retrieved]:
        top_k = top_k or config.TOP_K
        if self.count() == 0:
            return []
        result = self._collection.query(
            query_embeddings=[list(embedding)],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        return [
            Retrieved(text=text, metadata=dict(meta or {}), distance=float(dist))
            for text, meta, dist in zip(documents, metadatas, distances)
        ]

    def count(self) -> int:
        return self._collection.count()

    def reset(self) -> None:
        self._client.delete_collection(self._collection_name)
        self._collection = self._get_or_create()

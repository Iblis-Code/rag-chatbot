"""Ingestion pipeline: load -> chunk -> embed -> store (plan step 6).

Chunk IDs are ``sha1(f"{source}:{page}:{chunk_index}")`` where ``chunk_index``
restarts per (source, page). Re-ingesting the same file therefore produces the
same IDs and the store upserts instead of duplicating.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence

from rag.chunker import chunk_text
from rag.loaders import Document, PathLike, load_paths
from rag.vector_store import VectorStore

EmbedFn = Callable[[Sequence[str]], list[list[float]]]


@dataclass
class IngestReport:
    files: int = 0
    documents: int = 0
    chunks: int = 0
    sources: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        listed = ", ".join(self.sources) if self.sources else "-"
        return (
            f"Ingested {self.chunks} chunks from {self.files} file(s) "
            f"({self.documents} document section(s)): {listed}"
        )


def _default_embed(texts: Sequence[str]) -> list[list[float]]:
    # Imported lazily so `import rag.ingest` never pulls in torch.
    from rag.embeddings import embed_texts

    return embed_texts(texts)


def _chunk_id(source: str, page: int | None, index: int) -> str:
    key = f"{source}:{page if page is not None else '-'}:{index}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def ingest_documents(
    documents: Iterable[Document],
    store: VectorStore,
    embed_fn: EmbedFn | None = None,
    *,
    size: int | None = None,
    overlap: int | None = None,
) -> IngestReport:
    """Chunk, embed, and upsert an iterable of :class:`Document` into ``store``."""
    documents = list(documents)
    embed_fn = embed_fn or _default_embed

    ids: list[str] = []
    texts: list[str] = []
    metadatas: list[dict] = []
    seen_sources: list[str] = []
    index_by_key: dict[tuple[str, object], int] = {}

    for doc in documents:
        source = doc.source or "unknown"
        if source not in seen_sources:
            seen_sources.append(source)
        for chunk in chunk_text(doc.text, size, overlap):
            key = (source, doc.page)
            index = index_by_key.get(key, 0)
            index_by_key[key] = index + 1
            ids.append(_chunk_id(source, doc.page, index))
            texts.append(chunk)
            metadatas.append({"source": source, "page": doc.page, "chunk": index})

    if ids:
        store.add(
            ids=ids,
            embeddings=embed_fn(texts),
            documents=texts,
            metadatas=metadatas,
        )

    return IngestReport(
        files=len(seen_sources),
        documents=len(documents),
        chunks=len(ids),
        sources=seen_sources,
    )


def ingest_paths(
    paths: PathLike | Iterable[PathLike],
    store: VectorStore,
    embed_fn: EmbedFn | None = None,
    *,
    size: int | None = None,
    overlap: int | None = None,
) -> IngestReport:
    """Load files/directories, then :func:`ingest_documents`."""
    return ingest_documents(
        load_paths(paths), store, embed_fn, size=size, overlap=overlap
    )

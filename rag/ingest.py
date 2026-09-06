"""Ingestion pipeline: load -> chunk -> embed -> store (plan step 6).

Chunk IDs are ``sha1(f"{doc_key}:{page}:{chunk_index}")`` where ``chunk_index``
restarts per (doc_key, page). ``doc_key`` is the file's path rather than its bare
name, so two files that share a filename in different folders do not collide.

Re-ingesting a file first deletes its existing chunks, then upserts the new ones.
Upsert alone is not enough: if the file shrank, its old trailing chunk IDs would
never be written again and would linger in the store as retrievable stale text.
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


def _chunk_id(doc_key: str, page: int | None, index: int) -> str:
    key = f"{doc_key}:{page if page is not None else '-'}:{index}"
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
    # Display names for the report line -- two files can share one, which is why
    # they cannot be counted. `seen_keys` is the distinct-file count; `chunked_keys`
    # is the subset that produced chunks, and so the set to clear before upserting.
    seen_sources: list[str] = []
    seen_keys: list[str] = []
    chunked_keys: list[str] = []
    index_by_key: dict[tuple[str, object], int] = {}

    for doc in documents:
        source = doc.source or "unknown"
        doc_key = doc.doc_key or source
        if source not in seen_sources:
            seen_sources.append(source)
        if doc_key not in seen_keys:
            seen_keys.append(doc_key)
        for chunk in chunk_text(doc.text, size, overlap):
            if doc_key not in chunked_keys:
                chunked_keys.append(doc_key)
            key = (doc_key, doc.page)
            index = index_by_key.get(key, 0)
            index_by_key[key] = index + 1
            ids.append(_chunk_id(doc_key, doc.page, index))
            texts.append(chunk)
            metadatas.append(
                {
                    "source": source,
                    "doc_key": doc_key,
                    "page": doc.page,
                    "chunk": index,
                }
            )

    if ids:
        # Drop each file's previous chunks before re-adding it, so a document that
        # shrank does not leave orphaned trailing chunks behind. Keys are collected
        # during chunking, so a document that yielded nothing never clears itself.
        for doc_key in chunked_keys:
            store.delete_by_source(doc_key)
        store.add(
            ids=ids,
            embeddings=embed_fn(texts),
            documents=texts,
            metadatas=metadatas,
        )

    return IngestReport(
        files=len(seen_keys),
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

"""Tests for ``rag.ingest`` using in-memory test doubles (plan step 6/10)."""

from __future__ import annotations

from rag.ingest import ingest_documents, ingest_paths
from rag.loaders import Document
from tests.helpers import InMemoryVectorStore, hashing_embed

LONG_BODY = " ".join(f"word{i}" for i in range(500))  # forces several chunks


def test_ingest_documents_chunks_embeds_and_stores():
    store = InMemoryVectorStore()
    report = ingest_documents(
        [Document(LONG_BODY, {"source": "doc.txt"})],
        store,
        embed_fn=hashing_embed,
        size=200,
        overlap=20,
    )

    assert report.files == 1
    assert report.documents == 1
    assert report.chunks == store.count() > 1
    assert report.sources == ["doc.txt"]


def test_chunk_ids_are_deterministic_so_reingest_upserts():
    docs = [Document(LONG_BODY, {"source": "doc.txt"})]

    store = InMemoryVectorStore()
    ingest_documents(docs, store, embed_fn=hashing_embed, size=200, overlap=20)
    first_ids = set(store._rows)
    count_after_first = store.count()

    ingest_documents(docs, store, embed_fn=hashing_embed, size=200, overlap=20)
    assert set(store._rows) == first_ids
    assert store.count() == count_after_first  # no duplicates


def test_metadata_records_source_page_and_chunk_index():
    store = InMemoryVectorStore()
    ingest_documents(
        [
            Document("first page body text", {"source": "a.pdf", "page": 1}),
            Document("second page body text", {"source": "a.pdf", "page": 2}),
        ],
        store,
        embed_fn=hashing_embed,
    )
    metas = [meta for _, _, meta in store._rows.values()]
    assert {m["source"] for m in metas} == {"a.pdf"}
    assert {m["page"] for m in metas} == {1, 2}
    assert all(m["chunk"] == 0 for m in metas)  # one chunk per short page


def test_empty_input_produces_empty_report():
    store = InMemoryVectorStore()
    report = ingest_documents([], store, embed_fn=hashing_embed)
    assert report.chunks == 0
    assert store.count() == 0
    assert "0 chunks" in str(report)


def test_ingest_paths_reads_from_disk(tmp_path):
    (tmp_path / "note.md").write_text("# Note\n\n" + LONG_BODY, encoding="utf-8")
    store = InMemoryVectorStore()
    report = ingest_paths(tmp_path, store, embed_fn=hashing_embed, size=200, overlap=20)
    assert report.sources == ["note.md"]
    assert store.count() == report.chunks > 1

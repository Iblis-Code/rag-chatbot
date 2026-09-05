"""End-to-end pipeline smoke test (plan step 10).

Runs loaders -> chunker -> ingest -> ChromaVectorStore -> query against a real
on-disk Chroma collection in a temp dir, using a deterministic hashing embedder
so no model download / torch is required. Skips cleanly if chromadb is absent.
"""

from __future__ import annotations

import pytest

pytest.importorskip("chromadb")

from rag.ingest import ingest_paths  # noqa: E402
from rag.vector_store import ChromaVectorStore  # noqa: E402
from tests.helpers import hashing_embed  # noqa: E402

DOCS = {
    "geography.md": (
        "# Geography\n\n"
        "The capital of France is Paris, a city on the river Seine.\n\n"
        "The capital of Japan is Tokyo, the most populous metropolitan area."
    ),
    "cooking.md": (
        "# Cooking\n\n"
        "To make a roux you cook equal parts flour and butter in a pan.\n\n"
        "Bread needs flour, water, salt, and yeast, then time to prove."
    ),
}


@pytest.fixture
def store(tmp_path):
    for name, body in DOCS.items():
        (tmp_path / name).write_text(body, encoding="utf-8")
    vs = ChromaVectorStore(path=str(tmp_path / "chroma"), collection_name="smoke")
    ingest_paths(tmp_path, vs, embed_fn=hashing_embed, size=200, overlap=40)
    return vs


def test_ingest_populates_the_collection(store):
    assert store.count() >= len(DOCS)


def test_query_returns_the_relevant_chunk_first(store):
    hits = store.query(hashing_embed(["What is the capital of France?"])[0], top_k=3)
    assert hits
    assert "Paris" in hits[0].text
    assert hits[0].source == "geography.md"
    assert hits[0].distance <= hits[-1].distance  # ordered closest-first


def test_reset_empties_the_collection(store):
    store.reset()
    assert store.count() == 0
    assert store.query(hashing_embed(["anything"])[0]) == []

"""Tests for the CLI scripts (plan step 9/10), using torch-free test doubles."""

from __future__ import annotations

import json

import pytest

from rag.ingest import ingest_documents
from rag.loaders import Document
from scripts.eval_retrieval import (
    evaluate,
    format_report,
    load_eval_set,
    run_eval,
)
from scripts.ingest_cli import main as ingest_main
from scripts.ingest_cli import run_ingest
from tests.helpers import InMemoryVectorStore, hashing_embed

BODY = " ".join(f"word{i}" for i in range(300))
GEO = Document("The capital of France is Paris, on the river Seine.", {"source": "geo.md"})
FOOD = Document("A roux is equal parts flour and butter cooked together.", {"source": "food.md"})


# --- ingest_cli ----------------------------------------------------------------


def test_run_ingest_populates_the_store(tmp_path):
    (tmp_path / "a.md").write_text(f"# A\n\n{BODY}", encoding="utf-8")
    store = InMemoryVectorStore()
    report = run_ingest([tmp_path], store=store, embed_fn=hashing_embed)
    assert report.chunks > 1
    assert store.count() == report.chunks


def test_run_ingest_reset_clears_existing_rows(tmp_path):
    (tmp_path / "a.md").write_text("alpha body text here", encoding="utf-8")
    store = InMemoryVectorStore()
    store.add(
        ids=["stale"],
        embeddings=hashing_embed(["stale document"]),
        documents=["stale document"],
        metadatas=[{"source": "old.md"}],
    )
    run_ingest([tmp_path], store=store, embed_fn=hashing_embed, reset=True)
    sources = {meta["source"] for _, _, meta in store._rows.values()}
    assert sources == {"a.md"}


def test_ingest_main_reports_missing_path(capsys):
    rc = ingest_main(["definitely/not/here"])
    assert rc == 2
    assert "error" in capsys.readouterr().err


# --- eval_retrieval ----------------------------------------------------------


@pytest.fixture
def eval_store():
    store = InMemoryVectorStore()
    ingest_documents([GEO, FOOD], store, embed_fn=hashing_embed)
    return store


def test_load_eval_set_accepts_both_key_forms(tmp_path):
    path = tmp_path / "eval.json"
    path.write_text(
        json.dumps(
            [
                {"question": "capital of France?", "expected_source": "geo.md"},
                {"question": "what is a roux?", "expected_sources": ["food.md"]},
            ]
        ),
        encoding="utf-8",
    )
    items = load_eval_set(path)
    assert items[0]["expected"] == ["geo.md"]
    assert items[1]["expected"] == ["food.md"]


@pytest.mark.parametrize(
    "bad",
    ["not json", "{}", "[]", '[{"expected_source": "x"}]', '[{"question": "q"}]'],
)
def test_load_eval_set_rejects_bad_input(tmp_path, bad):
    path = tmp_path / "eval.json"
    path.write_text(bad, encoding="utf-8")
    with pytest.raises(ValueError):
        load_eval_set(path)


def test_load_eval_set_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_eval_set(tmp_path / "nope.json")


def test_evaluate_scores_hits_rank_and_mrr(eval_store):
    eval_set = [
        {"question": "What is the capital of France?", "expected": ["geo.md"]},
        {"question": "How do you make a roux?", "expected": ["food.md"]},
    ]
    result = evaluate(eval_set, eval_store, k=2, embed_fn=hashing_embed)
    assert result.total == 2
    assert result.hits == 2
    assert result.hit_rate == 1.0
    assert 0.0 < result.mrr <= 1.0
    assert all(row.rank == 1 for row in result.rows)

    report = format_report(result)
    assert "hit@2 = 1.00  (2/2)" in report


def test_evaluate_counts_a_miss(eval_store):
    eval_set = [{"question": "capital of France?", "expected": ["nonexistent.md"]}]
    result = evaluate(eval_set, eval_store, k=3, embed_fn=hashing_embed)
    assert result.hit_rate == 0.0
    assert result.rows[0].rank is None
    assert "MISS" in format_report(result)


def test_run_eval_reads_a_json_file(tmp_path, eval_store):
    path = tmp_path / "eval.json"
    path.write_text(
        json.dumps([{"question": "capital of France", "expected_source": "geo.md"}]),
        encoding="utf-8",
    )
    result = run_eval(path, k=3, store=eval_store, embed_fn=hashing_embed)
    assert result.hit_rate == 1.0

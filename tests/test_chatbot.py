"""Tests for ``rag.chatbot`` with a faked Claude client (plan step 7/10)."""

from __future__ import annotations

import pytest

from rag import chatbot, config
from rag.ingest import ingest_documents
from rag.loaders import Document
from rag.vector_store import Retrieved
from tests.helpers import InMemoryVectorStore, hashing_embed

DOCS = [
    Document("The capital of France is Paris on the Seine.", {"source": "geo.md"}),
    Document("A roux is equal parts flour and butter.", {"source": "food.md"}),
]


@pytest.fixture
def store():
    vs = InMemoryVectorStore()
    ingest_documents(DOCS, vs, embed_fn=hashing_embed)
    return vs


class _FakeStream:
    def __init__(self, deltas):
        self._deltas = deltas

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    @property
    def text_stream(self):
        return iter(self._deltas)


class _FakeMessages:
    def __init__(self, deltas):
        self.deltas = deltas
        self.calls: list[dict] = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeStream(self.deltas)


class _FakeClient:
    def __init__(self, deltas):
        self.messages = _FakeMessages(deltas)


@pytest.fixture
def fake_client(monkeypatch):
    client = _FakeClient(["Paris", " is ", "the capital [geo.md]."])
    monkeypatch.setattr(chatbot, "_client", lambda: client)
    return client


def test_format_context_numbers_blocks_and_shows_page():
    chunks = [
        Retrieved("alpha text", {"source": "a.pdf", "page": 3}, 0.1),
        Retrieved("beta text", {"source": "b.md"}, 0.2),
    ]
    context = chatbot.format_context(chunks)
    assert "[1] (source: a.pdf, page 3)" in context
    assert "[2] (source: b.md)" in context
    assert "alpha text" in context and "beta text" in context


def test_build_messages_keeps_history_then_appends_question():
    history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    chunks = [Retrieved("ctx", {"source": "a.md"}, 0.1)]
    messages = chatbot.build_messages("why?", chunks, history)
    assert messages[:2] == history
    assert messages[-1]["role"] == "user"
    assert "Question: why?" in messages[-1]["content"]
    assert "ctx" in messages[-1]["content"]


def test_build_messages_trims_history_to_history_turns(monkeypatch):
    monkeypatch.setattr(config, "HISTORY_TURNS", 1)
    history = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "q2"},
        {"role": "assistant", "content": "a2"},
    ]
    chunks = [Retrieved("ctx", {"source": "a.md"}, 0.1)]
    messages = chatbot.build_messages("q3", chunks, history)
    assert [m["content"] for m in messages[:-1]] == ["q2", "a2"]  # last turn only
    assert "Question: q3" in messages[-1]["content"]


def test_build_messages_zero_history_turns_sends_no_history(monkeypatch):
    monkeypatch.setattr(config, "HISTORY_TURNS", 0)
    chunks = [Retrieved("ctx", {"source": "a.md"}, 0.1)]
    messages = chatbot.build_messages("q", chunks, [{"role": "user", "content": "old"}])
    assert len(messages) == 1
    assert "Question: q" in messages[0]["content"]


def test_trim_history_drops_leading_non_user_message():
    history = [
        {"role": "assistant", "content": "a0"},
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
    ]
    trimmed = chatbot._trim_history(history, max_turns=2)
    assert [m["role"] for m in trimmed] == ["user", "assistant"]


def test_answer_without_hits_returns_canned_message(fake_client):
    empty = InMemoryVectorStore()
    response = chatbot.answer("anything", empty, embed_fn=hashing_embed)
    assert response.chunks == []
    assert response.sources == []
    assert "".join(response.stream) == chatbot.NO_CONTEXT_MESSAGE
    assert fake_client.messages.calls == []  # API never called


def test_answer_streams_from_claude_and_reports_sources(store, fake_client):
    response = chatbot.answer(
        "What is the capital of France?", store, embed_fn=hashing_embed, top_k=2
    )

    # Retrieval already happened; the API call is deferred until the stream runs.
    assert response.chunks
    assert response.sources[0] == "geo.md"
    assert fake_client.messages.calls == []

    text = "".join(response.stream)
    assert text == "Paris is the capital [geo.md]."
    assert len(fake_client.messages.calls) == 1
    call = fake_client.messages.calls[0]
    assert call["model"] == config.CLAUDE_MODEL
    assert call["system"] == chatbot.SYSTEM_PROMPT
    assert call["max_tokens"] == config.MAX_TOKENS
    # Thinking is off: its tokens would otherwise be billed and eat MAX_TOKENS.
    assert call["thinking"] == {"type": "disabled"}


def test_sources_are_deduped_in_retrieval_order(store, fake_client):
    store.add(
        ids=["dup"],
        embeddings=hashing_embed(["The capital of France is Paris again"]),
        documents=["The capital of France is Paris again"],
        metadatas=[{"source": "geo.md"}],
    )
    response = chatbot.answer(
        "capital of France?", store, embed_fn=hashing_embed, top_k=5
    )
    assert response.sources.count("geo.md") == 1


# --- Relevance threshold --------------------------------------------------

def test_is_relevant_gates_on_the_nearest_chunk():
    near = Retrieved("ctx", {"source": "a.md"}, 0.4)
    far = Retrieved("ctx", {"source": "b.md"}, 0.9)
    assert chatbot.is_relevant([near, far], max_distance=0.75)
    assert not chatbot.is_relevant([far, near], max_distance=0.75)
    assert not chatbot.is_relevant([], max_distance=0.75)


def test_off_topic_question_is_declined_without_calling_claude(store, fake_client):
    """Nothing in `store` is close to this, so it must not reach the API."""
    response = chatbot.answer("anything", store, embed_fn=hashing_embed)

    assert response.chunks == []          # no Sources panel for a declined answer
    assert response.sources == []
    assert "".join(response.stream) == chatbot.NO_CONTEXT_MESSAGE
    assert fake_client.messages.calls == []


def test_raising_max_distance_lets_a_weak_match_through(store, fake_client):
    response = chatbot.answer(
        "anything", store, embed_fn=hashing_embed, max_distance=2.0
    )
    assert response.chunks
    assert "".join(response.stream) == "Paris is the capital [geo.md]."
    assert len(fake_client.messages.calls) == 1


def test_threshold_defaults_to_config(monkeypatch, store, fake_client):
    monkeypatch.setattr(config, "MAX_DISTANCE", 2.0)
    assert chatbot.answer("anything", store, embed_fn=hashing_embed).chunks

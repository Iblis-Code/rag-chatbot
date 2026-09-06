"""Smoke tests for the Streamlit UI (plan step 8/10).

These check that ``app.py`` executes end-to-end and wires widgets to config;
the retrieval/answer logic itself is covered by the ``rag`` test modules.

Running ``app.py`` auto-ingests ``data/samples/`` whenever the store is empty --
and ``conftest`` gives every test a fresh temp store, so that happens once per
test here. Left alone it would load the real ~90 MB sentence-transformers model
each time, which needs torch, needs the network on a cold cache, and blows the
``AppTest`` timeout. The embedder is stubbed with the same deterministic hashing
double the rest of the suite uses, keeping these tests fast and torch-free.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest  # noqa: E402

from rag import config  # noqa: E402
from tests.helpers import hashing_embed  # noqa: E402

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture(autouse=True)
def stub_embedder(monkeypatch):
    """Swap the real sentence-transformers model for the deterministic double.

    ``rag.ingest`` and ``app.ensure_embedder_ready`` both import from
    ``rag.embeddings`` at call time, so patching the module attributes is enough.
    """
    from rag import embeddings

    monkeypatch.setattr(embeddings, "embed_texts", hashing_embed)
    monkeypatch.setattr(embeddings, "embed_query", lambda text: hashing_embed([text])[0])


def _run() -> AppTest:
    return AppTest.from_file(APP_PATH, default_timeout=30).run()


def test_app_runs_without_exception():
    at = _run()
    assert not at.exception
    assert at.title[0].value == "Chat with your documents"
    assert {b.label for b in at.sidebar.button} == {
        "Ingest uploaded files",
        "Clear index",
        "Reset chat",
    }
    assert at.metric[0].label == "Chunks indexed"


def test_chat_disabled_and_warned_without_api_key(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", None)
    at = _run()
    assert at.chat_input[0].disabled is True
    assert any("ANTHROPIC_API_KEY" in w.value for w in at.warning)


def test_chat_enabled_with_api_key(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-ant-test")
    at = _run()
    assert at.chat_input[0].disabled is False
    assert not any("ANTHROPIC_API_KEY" in w.value for w in at.warning)


# --- Cost / abuse guardrails (plan step 13) -------------------------------

def test_password_gate_blocks_then_unlocks(monkeypatch):
    monkeypatch.setattr(config, "APP_PASSWORD", "secret")
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-ant-test")
    at = _run()
    assert len(at.chat_input) == 0  # script stopped before the chat UI
    assert len(at.text_input) == 1

    at.text_input[0].set_value("wrong").run()
    at.button[0].click().run()
    assert any("Incorrect" in e.value for e in at.error)
    assert len(at.chat_input) == 0

    at.text_input[0].set_value("secret").run()
    at.button[0].click().run()
    assert len(at.chat_input) == 1  # unlocked


def test_long_question_rejected_without_api_call(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(config, "MAX_QUESTION_CHARS", 10)
    at = _run()
    at.chat_input[0].set_value("x" * 50).run()
    assert any("shorten" in w.value.lower() for w in at.warning)
    assert at.session_state["messages"] == []


def test_global_rate_limit_blocks_when_exhausted(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(config, "RATE_LIMIT_PER_HOUR", 0)  # nothing allowed
    at = _run()
    at.chat_input[0].set_value("hello?").run()
    assert any("try again" in w.value.lower() for w in at.warning)
    assert at.session_state["messages"] == []  # never reached the answer path


def test_per_session_cap_disables_input(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(config, "MAX_MESSAGES_PER_SESSION", 1)
    at = _run()
    at.session_state["messages"] = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
    ]
    at.run()
    assert at.chat_input[0].disabled is True
    assert any("limit" in i.value.lower() for i in at.info)

"""Streamlit chat UI for the RAG chatbot (plan step 8).

Run:  streamlit run app.py

Retrieval and generation live in ``rag/``; this file is only wiring:
a cached vector store, a sidebar for adding/clearing documents, and a chat pane
that streams grounded answers with their sources.
"""

from __future__ import annotations

import time
from collections import deque
from pathlib import Path

import streamlit as st

from rag import chatbot, config
from rag.ingest import ingest_paths
from rag.loaders import iter_supported_files
from rag.vector_store import ChromaVectorStore

st.set_page_config(page_title="RAG Chatbot", page_icon="📚", layout="centered")

UPLOAD_TYPES = ["pdf", "txt", "md", "markdown"]
PREVIEW_CHARS = 500


# --------------------------------------------------------------------------
# Cost / abuse guardrails (plan step 13)
# --------------------------------------------------------------------------
def require_password() -> None:
    """Gate the whole app behind ``APP_PASSWORD`` when one is configured."""
    if not config.APP_PASSWORD or st.session_state.get("authed"):
        return
    st.title("Chat with your documents")
    st.caption("This demo is password-protected.")
    pw = st.text_input("Access password", type="password")
    if st.button("Enter"):
        if pw == config.APP_PASSWORD:
            st.session_state.authed = True
            st.rerun()
        st.error("Incorrect password.")
    st.stop()


@st.cache_resource(show_spinner=False)
def _rate_window() -> deque:
    """Recent Claude-call timestamps, shared across every session in this process."""
    return deque()


def rate_limit_ok() -> bool:
    """True (and records the call) while under the app-wide hourly Claude-call cap."""
    calls = _rate_window()
    now = time.monotonic()
    cutoff = now - 3600
    while calls and calls[0] < cutoff:
        calls.popleft()
    if len(calls) >= config.RATE_LIMIT_PER_HOUR:
        return False
    calls.append(now)
    return True


require_password()


@st.cache_resource(show_spinner="Opening the vector store…")
def get_store() -> ChromaVectorStore:
    """One persistent Chroma store per server process.

    On first launch with an empty index, auto-ingest the committed sample docs so
    a fresh clone (and the deployed demo) works with zero setup.
    """
    store = ChromaVectorStore()
    if store.count() == 0 and config.SAMPLES_DIR.is_dir():
        if iter_supported_files(config.SAMPLES_DIR):
            try:
                ingest_paths(config.SAMPLES_DIR, store)
            except Exception as exc:  # pragma: no cover - defensive
                st.warning(f"Could not auto-index sample documents: {exc}")
    return store


@st.cache_resource(show_spinner="Loading the embedding model…")
def ensure_embedder_ready() -> bool:
    """Trigger the one-time sentence-transformers model download / load."""
    from rag import embeddings

    embeddings.embed_query("warm up")
    return True


def api_history() -> list[dict]:
    """Prior turns (role + content only) to send as conversation history."""
    return [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages
    ]


def render_sources(context: list[dict]) -> None:
    if not context:
        return
    with st.expander(f"Sources · {len(context)} chunk(s)"):
        for i, chunk in enumerate(context, start=1):
            location = chunk["source"] or "unknown"
            if chunk.get("page") is not None:
                location += f" · p.{chunk['page']}"
            st.markdown(f"**[{i}] {location}**")
            text = chunk["text"]
            st.caption(text[:PREVIEW_CHARS] + ("…" if len(text) > PREVIEW_CHARS else ""))


def handle_ingest(uploads) -> None:
    config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for upload in uploads:
        dest = config.UPLOADS_DIR / upload.name
        dest.write_bytes(upload.getvalue())
        saved.append(dest)
    with st.spinner("Embedding and indexing…"):
        ensure_embedder_ready()
        report = ingest_paths(saved, get_store())
    st.success(str(report))


# --------------------------------------------------------------------------
# Sidebar: document management
# --------------------------------------------------------------------------
store = get_store()

with st.sidebar:
    st.header("📚 Documents")
    st.metric("Chunks indexed", store.count())

    uploads = st.file_uploader(
        "Add PDF / TXT / Markdown files",
        type=UPLOAD_TYPES,
        accept_multiple_files=True,
    )
    if st.button(
        "Ingest uploaded files",
        disabled=not uploads,
        use_container_width=True,
        type="primary",
    ):
        handle_ingest(uploads)
        st.rerun()

    if st.button("Clear index", use_container_width=True):
        store.reset()
        st.toast("Index cleared.")
        st.rerun()

    st.divider()
    st.caption(
        f"Model `{config.CLAUDE_MODEL}`  \n"
        f"Embeddings `{config.EMBED_MODEL.split('/')[-1]}`  \n"
        f"top_k {config.TOP_K} · chunk {config.CHUNK_SIZE}/{config.CHUNK_OVERLAP}"
    )
    if st.button("Reset chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()


# --------------------------------------------------------------------------
# Main: chat
# --------------------------------------------------------------------------
st.title("Chat with your documents")
st.caption(
    "Answers are grounded only in the indexed documents and cite their sources. "
    "If the answer isn't in your documents, the bot says so."
)

if not config.ANTHROPIC_API_KEY:
    st.warning(
        "`ANTHROPIC_API_KEY` is not set — you can still upload and index documents, "
        "but answering is disabled. Add it to `.env` or Streamlit secrets."
    )

st.session_state.setdefault("messages", [])

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            render_sources(message.get("context", []))

asked = sum(1 for m in st.session_state.messages if m["role"] == "user")
session_full = asked >= config.MAX_MESSAGES_PER_SESSION
if session_full:
    st.info(
        f"You've reached this session's limit of {config.MAX_MESSAGES_PER_SESSION} "
        "questions. Use **Reset chat** in the sidebar to start over."
    )

prompt = st.chat_input(
    "Ask a question about your documents",
    disabled=not config.ANTHROPIC_API_KEY or session_full,
)

if prompt and len(prompt) > config.MAX_QUESTION_CHARS:
    st.warning(
        f"That question is {len(prompt):,} characters; the demo cap is "
        f"{config.MAX_QUESTION_CHARS:,}. Please shorten it and ask again."
    )
elif prompt and not rate_limit_ok():
    st.warning(
        "The shared demo is handling a lot of questions right now — "
        "please try again in a little while."
    )
elif prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    history = api_history()[:-1]  # everything before the question just asked

    with st.chat_message("assistant"):
        try:
            with st.spinner("Retrieving relevant context…"):
                ensure_embedder_ready()
                response = chatbot.answer(prompt, store, history=history)
            answer_text = st.write_stream(response.stream)
            context = [
                {"source": c.source, "page": c.page, "text": c.text}
                for c in response.chunks
            ]
            render_sources(context)
        except Exception as exc:  # surface API/embedding errors in the chat
            answer_text = f"⚠️ {type(exc).__name__}: {exc}"
            context = []
            st.error(answer_text)

    st.session_state.messages.append(
        {"role": "assistant", "content": answer_text, "context": context}
    )

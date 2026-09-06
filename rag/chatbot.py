"""Retrieval + grounded generation with Claude (plan step 7).

``answer()`` retrieves eagerly (so the caller can show sources immediately) and
returns a lazy token ``stream`` that calls the Claude API only when iterated --
which is exactly what ``st.write_stream`` wants.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable, Iterator, Sequence

from rag import config
from rag.vector_store import Retrieved, VectorStore

EmbedQueryFn = Callable[[Sequence[str]], list[list[float]]]

SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions using ONLY the context "
    "provided below, retrieved from the user's own documents.\n"
    "- If the answer is not contained in the context, say you don't know. Never "
    "fall back on outside knowledge.\n"
    "- After each fact, cite the source filename in square brackets, e.g. "
    "[handbook.md].\n"
    "- Be concise, and quote names and figures exactly as they appear.\n"
    "- Do not include internal or system XML tags in your response."
)

NO_CONTEXT_MESSAGE = (
    "I couldn't find anything relevant in the indexed documents, so I can't "
    "answer that. Try rephrasing, or add documents that cover the topic."
)

# Grounded extract-and-cite over a handful of retrieved chunks needs no reasoning
# step, and on current models thinking is *on* unless disabled -- its tokens are
# billed and count against ``MAX_TOKENS``, which would crowd out the visible
# answer. Turning it off keeps the whole budget for the answer the user reads.
THINKING = {"type": "disabled"}


@lru_cache(maxsize=1)
def _client():
    import anthropic

    return anthropic.Anthropic(api_key=config.require_api_key())


@dataclass
class RagResponse:
    """Result of :func:`answer`: retrieved context + a lazy answer stream."""

    question: str
    chunks: list[Retrieved]
    stream: Iterator[str]
    sources: list[str] = field(default_factory=list)


def retrieve(
    question: str,
    store: VectorStore,
    top_k: int | None = None,
    embed_fn: EmbedQueryFn | None = None,
) -> list[Retrieved]:
    """Embed the question and return the nearest chunks from ``store``."""
    if embed_fn is None:
        from rag.embeddings import embed_query

        vector = embed_query(question)
    else:
        vector = embed_fn([question])[0]
    return store.query(vector, top_k or config.TOP_K)


def format_context(chunks: Sequence[Retrieved]) -> str:
    blocks = []
    for i, chunk in enumerate(chunks, start=1):
        location = f"source: {chunk.source or 'unknown'}"
        if chunk.page is not None:
            location += f", page {chunk.page}"
        blocks.append(f"[{i}] ({location})\n{chunk.text.strip()}")
    return "\n\n".join(blocks)


def _trim_history(history: Sequence[dict] | None, max_turns: int) -> list[dict]:
    """Keep only the last ``max_turns`` user/assistant pairs.

    Bounds the tokens re-sent on every question so a long conversation doesn't
    make each call progressively more expensive (plan step 13). The result must
    still start with a ``user`` message for the Claude API.
    """
    if not history or max_turns <= 0:
        return []
    trimmed = list(history)[-2 * max_turns:]
    if trimmed and trimmed[0].get("role") != "user":
        trimmed = trimmed[1:]
    return trimmed


def build_messages(
    question: str,
    chunks: Sequence[Retrieved],
    history: Sequence[dict] | None = None,
) -> list[dict]:
    """Recent prior turns, then a final user turn carrying the retrieved context."""
    messages = _trim_history(history, config.HISTORY_TURNS)
    messages.append(
        {
            "role": "user",
            "content": (
                f"Context from the documents:\n\n{format_context(chunks)}\n\n"
                f"---\nQuestion: {question}"
            ),
        }
    )
    return messages


def _stream_from_claude(messages: list[dict]) -> Iterator[str]:
    with _client().messages.stream(
        model=config.CLAUDE_MODEL,
        max_tokens=config.MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=messages,
        thinking=THINKING,
    ) as stream:
        yield from stream.text_stream


def _static_stream(text: str) -> Iterator[str]:
    yield text


def answer(
    question: str,
    store: VectorStore,
    *,
    history: Sequence[dict] | None = None,
    top_k: int | None = None,
    embed_fn: EmbedQueryFn | None = None,
) -> RagResponse:
    """Retrieve context for ``question`` and prepare a grounded answer stream."""
    chunks = retrieve(question, store, top_k, embed_fn)
    if not chunks:
        return RagResponse(question, [], _static_stream(NO_CONTEXT_MESSAGE), [])

    ordered_sources = list(dict.fromkeys(c.source for c in chunks if c.source))
    messages = build_messages(question, chunks, history)
    return RagResponse(question, chunks, _stream_from_claude(messages), ordered_sources)

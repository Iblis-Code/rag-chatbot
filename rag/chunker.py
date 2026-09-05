"""Text chunking with overlap (plan step 3).

``chunk_text`` splits text on blank-line paragraph boundaries, greedily packs
paragraphs into chunks of at most ``size`` characters, hard-splits any single
paragraph longer than ``size`` on word boundaries, and prepends the tail of the
previous chunk to each following chunk so context survives the boundary.
"""

from __future__ import annotations

import re

from rag import config

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")
_WHITESPACE_RUN = re.compile(r"\s+")


def _normalise(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _split_long_unit(unit: str, size: int) -> list[str]:
    """Break an over-long paragraph into word-aligned pieces of at most ``size``."""
    pieces: list[str] = []
    current = ""
    for word in _WHITESPACE_RUN.split(unit):
        if not word:
            continue
        # A single word longer than the whole budget: hard character-split it.
        while len(word) > size:
            if current:
                pieces.append(current)
                current = ""
            pieces.append(word[:size])
            word = word[size:]
        candidate = f"{current} {word}".strip()
        if len(candidate) <= size:
            current = candidate
        else:
            if current:
                pieces.append(current)
            current = word
    if current:
        pieces.append(current)
    return pieces


def _tail(text: str, overlap: int) -> str:
    """Last ``overlap`` characters of ``text``, trimmed forward to a word start."""
    if overlap <= 0 or not text:
        return ""
    snippet = text[-overlap:]
    if len(snippet) < len(text):
        # Drop a leading partial word so the overlap reads cleanly.
        first_space = snippet.find(" ")
        if first_space != -1:
            snippet = snippet[first_space + 1 :]
    return snippet.strip()


def chunk_text(
    text: str,
    size: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    """Split ``text`` into overlapping chunks.

    Args:
        text: Raw document text.
        size: Maximum characters per chunk, excluding the overlap prefix.
            Defaults to ``config.CHUNK_SIZE``.
        overlap: Characters of the previous chunk prepended to each following
            chunk. Clamped to ``[0, size - 1]``. Defaults to
            ``config.CHUNK_OVERLAP``.

    Returns:
        A list of non-empty chunk strings. Whitespace-only input returns ``[]``.

    Raises:
        ValueError: if ``size`` is not positive.
    """
    size = config.CHUNK_SIZE if size is None else size
    overlap = config.CHUNK_OVERLAP if overlap is None else overlap
    if size <= 0:
        raise ValueError(f"size must be positive, got {size}")
    overlap = max(0, min(overlap, size - 1))

    text = _normalise(text)
    if not text:
        return []

    # 1. Paragraphs -> units, each stripped and no longer than `size`.
    units: list[str] = []
    for para in _PARAGRAPH_SPLIT.split(text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= size:
            units.append(para)
        else:
            units.extend(_split_long_unit(para, size))

    # 2. Greedily pack units into chunks of at most `size`.
    base_chunks: list[str] = []
    current = ""
    for unit in units:
        candidate = f"{current}\n\n{unit}" if current else unit
        if len(candidate) <= size:
            current = candidate
        else:
            if current:
                base_chunks.append(current)
            current = unit
    if current:
        base_chunks.append(current)

    if not base_chunks:
        return []

    # 3. Prepend each previous chunk's tail as overlap context.
    chunks = [base_chunks[0]]
    for i in range(1, len(base_chunks)):
        tail = _tail(base_chunks[i - 1], overlap)
        chunks.append(f"{tail}\n\n{base_chunks[i]}" if tail else base_chunks[i])
    return chunks

"""Unit tests for ``rag.chunker.chunk_text`` (plan step 10)."""

from __future__ import annotations

import re

import pytest

from rag import config
from rag.chunker import chunk_text

PARAGRAPHS = [
    "Retrieval augmented generation grounds a language model in external documents "
    "so that its answers reflect real source material instead of parametric memory.",
    "The ingestion pipeline loads each document, splits it into overlapping chunks, "
    "embeds every chunk with a sentence transformer, and stores the vectors on disk.",
    "At query time the question is embedded with the same model and compared against "
    "the stored vectors so the closest chunks can be pulled back as grounding context.",
    "Those retrieved chunks are inserted into the prompt and the language model is "
    "asked to answer using only that context, citing the source file for each fact.",
    "Chunk size and overlap are the main retrieval knobs: larger chunks carry more "
    "context per hit while smaller chunks localise the answer more precisely.",
    "A small evaluation set of question and expected source pairs measures hit rate "
    "at k, which is enough signal to compare chunking settings without a full harness.",
]
DOC = "\n\n".join(PARAGRAPHS)

_WORD = re.compile(r"\w+")


def _words(text: str) -> list[str]:
    return _WORD.findall(text)


@pytest.mark.parametrize("blank", ["", "   ", "\n\n\n", "\t  \n \n"])
def test_blank_input_returns_empty_list(blank: str) -> None:
    assert chunk_text(blank, size=200, overlap=20) == []


def test_short_single_paragraph_is_one_stripped_chunk() -> None:
    chunks = chunk_text("  a single short paragraph  ", size=200, overlap=20)
    assert chunks == ["a single short paragraph"]


def test_respects_size_when_no_overlap() -> None:
    chunks = chunk_text(DOC, size=200, overlap=0)
    assert len(chunks) > 1
    assert all(len(c) <= 200 for c in chunks)


def test_first_chunk_never_exceeds_size_with_overlap() -> None:
    chunks = chunk_text(DOC, size=200, overlap=40)
    assert len(chunks[0]) <= 200


def test_overlap_prepends_a_slice_of_the_previous_chunk() -> None:
    base = chunk_text(DOC, size=220, overlap=0)
    overlapped = chunk_text(DOC, size=220, overlap=40)

    assert len(base) == len(overlapped) > 1
    assert overlapped[0] == base[0]
    for i in range(1, len(overlapped)):
        # The real content of the chunk is still there, untouched, at the end.
        assert overlapped[i].endswith(base[i])
        # And what was prepended is a contiguous slice of the previous chunk.
        prefix = overlapped[i][: -len(base[i])].strip()
        assert prefix
        assert prefix in base[i - 1]


def test_no_overlap_means_no_added_prefix() -> None:
    chunks = chunk_text(DOC, size=150, overlap=0)
    rejoined_words = _words(" ".join(chunks))
    # Every word appears exactly as often as in the source (nothing duplicated).
    assert rejoined_words == _words(DOC)


def test_no_source_words_are_lost() -> None:
    chunks = chunk_text(DOC, size=120, overlap=30)
    covered = set(_words(" ".join(chunks)))
    assert set(_words(DOC)) <= covered


def test_oversized_paragraph_is_hard_split_on_word_boundaries() -> None:
    para = " ".join(f"token{i}" for i in range(400))  # one paragraph, no blank lines
    chunks = chunk_text(para, size=200, overlap=0)

    assert len(chunks) >= 5
    assert all(len(c) <= 200 for c in chunks)
    assert set(_words(para)) == set(_words(" ".join(chunks)))
    # Word boundaries preserved: no "tokenN" was cut in half.
    assert all(re.fullmatch(r"token\d+", w) for w in _words(" ".join(chunks)))


def test_single_word_longer_than_size_is_character_split() -> None:
    chunks = chunk_text("x" * 500, size=100, overlap=0)
    assert chunks
    assert all(len(c) <= 100 for c in chunks)
    assert "".join(chunks) == "x" * 500


def test_overlap_larger_than_size_is_clamped_not_raised() -> None:
    chunks = chunk_text(DOC, size=100, overlap=999)
    assert len(chunks) > 1
    assert len(chunks[0]) <= 100


def test_non_positive_size_raises() -> None:
    with pytest.raises(ValueError):
        chunk_text("anything", size=0)
    with pytest.raises(ValueError):
        chunk_text("anything", size=-10)


def test_defaults_come_from_config() -> None:
    long_doc = "\n\n".join(PARAGRAPHS * 6)
    chunks = chunk_text(long_doc)
    assert len(chunks) > 1
    assert len(chunks[0]) <= config.CHUNK_SIZE

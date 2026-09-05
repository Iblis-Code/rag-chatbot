"""Tests for ``rag.loaders`` (plan step 2)."""

from __future__ import annotations

import pytest

from rag.loaders import Document, load_document, load_paths


@pytest.fixture
def docs_dir(tmp_path):
    (tmp_path / "alpha.txt").write_text("alpha body text", encoding="utf-8")
    (tmp_path / "beta.md").write_text("# Beta\n\nbeta body", encoding="utf-8")
    (tmp_path / "ignore.log").write_text("not a document", encoding="utf-8")
    (tmp_path / "empty.txt").write_text("   \n\t", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "gamma.markdown").write_text("gamma body", encoding="utf-8")
    return tmp_path


def test_load_text_file_returns_one_document_with_source(docs_dir):
    docs = load_document(docs_dir / "alpha.txt")
    assert len(docs) == 1
    assert docs[0].text == "alpha body text"
    assert docs[0].source == "alpha.txt"
    assert docs[0].page is None


def test_empty_text_file_yields_no_documents(docs_dir):
    assert load_document(docs_dir / "empty.txt") == []


def test_unsupported_extension_raises_value_error(docs_dir):
    with pytest.raises(ValueError):
        load_document(docs_dir / "ignore.log")


def test_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_document(tmp_path / "nope.txt")


def test_load_paths_scans_directory_recursively_and_skips_unsupported(docs_dir):
    docs = load_paths(docs_dir)
    sources = sorted(d.source for d in docs)
    assert sources == ["alpha.txt", "beta.md", "gamma.markdown"]


def test_load_paths_accepts_an_explicit_list(docs_dir):
    docs = load_paths([docs_dir / "alpha.txt", docs_dir / "beta.md"])
    assert [d.source for d in docs] == ["alpha.txt", "beta.md"]


def test_load_paths_accepts_a_single_path(docs_dir):
    docs = load_paths(docs_dir / "alpha.txt")
    assert len(docs) == 1


def test_pdf_pages_become_documents(tmp_path):
    pypdf = pytest.importorskip("pypdf")
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    pdf_path = tmp_path / "blank.pdf"
    with pdf_path.open("wb") as fh:
        writer.write(fh)

    # Blank pages carry no extractable text, so no Documents are produced,
    # but the PDF branch must run without raising.
    assert load_document(pdf_path) == []


def test_document_dataclass_defaults():
    doc = Document(text="x")
    assert doc.metadata == {}
    assert doc.source == ""

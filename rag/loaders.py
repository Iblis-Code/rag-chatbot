"""Document loaders: PDF / txt / md -> list[Document] (plan step 2).

For a PDF there is one :class:`Document` per page (1-indexed ``page`` in
metadata); for a text file there is a single :class:`Document` with no page.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}
PDF_EXTENSIONS = {".pdf"}
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | PDF_EXTENSIONS

PathLike = str | Path


@dataclass
class Document:
    """A unit of source text plus provenance metadata."""

    text: str
    metadata: dict = field(default_factory=dict)

    @property
    def source(self) -> str:
        return self.metadata.get("source", "")

    @property
    def page(self) -> int | None:
        return self.metadata.get("page")


def _load_text_file(path: Path) -> list[Document]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return []
    return [Document(text=text, metadata={"source": path.name})]


def _load_pdf_file(path: Path) -> list[Document]:
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError as exc:  # pragma: no cover - dep is declared
        raise ModuleNotFoundError(
            "Reading PDF files requires 'pypdf' (pip install -r requirements.txt)."
        ) from exc

    reader = PdfReader(str(path))
    docs: list[Document] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            docs.append(
                Document(text=text, metadata={"source": path.name, "page": page_number})
            )
    return docs


def load_document(path: PathLike) -> list[Document]:
    """Load a single file into a list of :class:`Document`.

    Raises:
        FileNotFoundError: if ``path`` does not exist or is not a file.
        ValueError: if the file extension is not supported.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"No such file: {path}")

    ext = path.suffix.lower()
    if ext in TEXT_EXTENSIONS:
        return _load_text_file(path)
    if ext in PDF_EXTENSIONS:
        return _load_pdf_file(path)
    raise ValueError(
        f"Unsupported file type {ext or '(none)'!r} for {path.name}. "
        f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
    )


def iter_supported_files(root: Path) -> list[Path]:
    """Every supported file under ``root`` (recursive), in a stable order."""
    return sorted(
        p
        for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def load_paths(paths: PathLike | Iterable[PathLike]) -> list[Document]:
    """Load one path, a list of paths, or directories (recursively) of files.

    A file passed explicitly with an unsupported extension raises ``ValueError``;
    unsupported files found while scanning a directory are silently skipped.
    """
    if isinstance(paths, (str, Path)):
        paths = [paths]

    documents: list[Document] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            for file in iter_supported_files(path):
                documents.extend(load_document(file))
        else:
            documents.extend(load_document(path))
    return documents

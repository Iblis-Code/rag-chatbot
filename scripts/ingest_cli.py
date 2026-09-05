"""Index documents into the vector store from the command line (plan step 9).

    python -m scripts.ingest_cli data/samples
    python -m scripts.ingest_cli --reset docs/ notes.md

Uses the real embedding model, so the first run downloads it. Store location and
chunk settings come from the environment / ``.env`` via ``rag.config``.
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from rag.ingest import EmbedFn, IngestReport, ingest_paths
from rag.loaders import PathLike
from rag.vector_store import ChromaVectorStore, VectorStore


def run_ingest(
    paths: Sequence[PathLike],
    *,
    reset: bool = False,
    store: VectorStore | None = None,
    embed_fn: EmbedFn | None = None,
) -> IngestReport:
    """Ingest ``paths`` into ``store`` (a fresh ``ChromaVectorStore`` by default)."""
    store = store or ChromaVectorStore()
    if reset:
        store.reset()
    return ingest_paths(list(paths), store, embed_fn)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.ingest_cli",
        description="Chunk, embed, and upsert files or directories into the vector store.",
    )
    parser.add_argument(
        "paths", nargs="+", help="Files or directories to ingest (pdf / txt / md)."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Empty the collection before ingesting.",
    )
    args = parser.parse_args(argv)

    try:
        report = run_ingest(args.paths, reset=args.reset)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(report)
    if report.chunks == 0:
        print(
            "warning: nothing was ingested (no supported files with text found).",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

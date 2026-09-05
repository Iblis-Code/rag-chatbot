"""Shared pytest fixtures.

Keeps every test that builds a real ``ChromaVectorStore`` (the app smoke test in
particular) pointed at a throwaway temp directory, so running the suite never
writes a ``chroma_db/`` into the repo.
"""

from __future__ import annotations

import pytest

from rag import config


@pytest.fixture(autouse=True)
def isolated_chroma_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CHROMA_DIR", tmp_path / "chroma")
    # app.get_store() / ensure_embedder_ready() are @st.cache_resource; clear so
    # each test rebuilds against the patched directory instead of a stale cache.
    try:
        import streamlit as st

        st.cache_resource.clear()
    except Exception:
        pass
    yield

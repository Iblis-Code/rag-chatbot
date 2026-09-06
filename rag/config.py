"""Central configuration: environment variables + constants (plan step 1).

Every value resolves in this order:

1. a real environment variable (this includes anything loaded from a local
   ``.env`` file at import time);
2. ``st.secrets[KEY]`` -- only when the app is already running under Streamlit
   (e.g. Streamlit Community Cloud), so plain CLI use never imports Streamlit;
3. the hard-coded default defined here.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load a local .env if one exists. Variables already present in the real
# environment are left untouched (load_dotenv does not override by default).
# python-dotenv is a declared dependency; degrade gracefully if it is absent so
# real environment variables still work.
try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except ModuleNotFoundError:  # pragma: no cover - exercised only without the dep
    pass


def _from_secrets(key: str) -> str | None:
    """Look ``key`` up in ``st.secrets``; return None unless Streamlit is loaded."""
    if "streamlit" not in sys.modules:
        return None
    try:
        import streamlit as st

        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        # st.secrets raises when no secrets file is configured -- treat as absent.
        return None
    return None


def _get(key: str, default: str | None = None) -> str | None:
    if os.environ.get(key):
        return os.environ[key]
    return _from_secrets(key) or default


def _get_int(key: str, default: int) -> int:
    raw = _get(key)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return int(str(raw).strip())
    except ValueError as exc:
        raise ValueError(f"Config {key!r} must be an integer, got {raw!r}") from exc


# --- Secrets ---------------------------------------------------------------
ANTHROPIC_API_KEY = _get("ANTHROPIC_API_KEY")

# --- Models --------------------------------------------------------------
CLAUDE_MODEL = _get("CLAUDE_MODEL", "claude-sonnet-5")
EMBED_MODEL = _get("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
MAX_TOKENS = _get_int("MAX_TOKENS", 768)

# --- Cost / abuse guardrails (plan step 13) ----------------------------
# The deployed demo answers over a public URL on a single (owner's) API key.
# These bound the blast radius; the hard backstop is a monthly spend limit on
# a dedicated Anthropic Workspace (see README "Cost & abuse controls").
HISTORY_TURNS = _get_int("HISTORY_TURNS", 3)
# 20/hour is far above real reviewer traffic but meaningfully slows a scripted
# client. The safe value is the default rather than a deployment override, so
# losing the override can't silently widen the limit. See docs/CONFIGURATION.md.
RATE_LIMIT_PER_HOUR = _get_int("RATE_LIMIT_PER_HOUR", 20)
MAX_MESSAGES_PER_SESSION = _get_int("MAX_MESSAGES_PER_SESSION", 20)
MAX_QUESTION_CHARS = _get_int("MAX_QUESTION_CHARS", 600)
APP_PASSWORD = _get("APP_PASSWORD")

# --- Vector store ------------------------------------------------------
COLLECTION_NAME = _get("COLLECTION_NAME", "documents")
_chroma_dir = Path(_get("CHROMA_DIR", "./chroma_db"))
if not _chroma_dir.is_absolute():
    _chroma_dir = (PROJECT_ROOT / _chroma_dir).resolve()
CHROMA_DIR = _chroma_dir

# --- Retrieval / chunking -------------------------------------------
CHUNK_SIZE = _get_int("CHUNK_SIZE", 800)
CHUNK_OVERLAP = _get_int("CHUNK_OVERLAP", 150)
TOP_K = _get_int("TOP_K", 4)

# --- Paths ------------------------------------------------------------
DATA_DIR = PROJECT_ROOT / "data"
SAMPLES_DIR = DATA_DIR / "samples"
UPLOADS_DIR = DATA_DIR / "uploads"

# --- Validation ----------------------------------------------------
if CHUNK_SIZE <= 0:
    raise ValueError(f"CHUNK_SIZE must be positive, got {CHUNK_SIZE}")
if CHUNK_OVERLAP < 0:
    raise ValueError(f"CHUNK_OVERLAP must be >= 0, got {CHUNK_OVERLAP}")
if CHUNK_OVERLAP >= CHUNK_SIZE:
    raise ValueError(
        f"CHUNK_OVERLAP ({CHUNK_OVERLAP}) must be smaller than CHUNK_SIZE ({CHUNK_SIZE})"
    )
if TOP_K < 1:
    raise ValueError(f"TOP_K must be >= 1, got {TOP_K}")
if MAX_TOKENS < 1:
    raise ValueError(f"MAX_TOKENS must be >= 1, got {MAX_TOKENS}")
if HISTORY_TURNS < 0:
    raise ValueError(f"HISTORY_TURNS must be >= 0, got {HISTORY_TURNS}")
if RATE_LIMIT_PER_HOUR < 1:
    raise ValueError(f"RATE_LIMIT_PER_HOUR must be >= 1, got {RATE_LIMIT_PER_HOUR}")
if MAX_MESSAGES_PER_SESSION < 1:
    raise ValueError(
        f"MAX_MESSAGES_PER_SESSION must be >= 1, got {MAX_MESSAGES_PER_SESSION}"
    )
if MAX_QUESTION_CHARS < 1:
    raise ValueError(f"MAX_QUESTION_CHARS must be >= 1, got {MAX_QUESTION_CHARS}")


def require_api_key() -> str:
    """Return the Anthropic API key, or raise a clear error if it is unset."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key, "
            "or set it in your environment / Streamlit secrets."
        )
    return ANTHROPIC_API_KEY

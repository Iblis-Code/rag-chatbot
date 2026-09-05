"""Local embeddings via sentence-transformers (plan step 4).

The model is loaded lazily on first use and cached for the process, so importing
this module stays cheap (no torch import until an embedding is actually needed).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Sequence

from rag import config

_DEFAULT_BATCH_SIZE = 64


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(config.EMBED_MODEL)


def embedding_dim() -> int:
    """Dimensionality of the vectors this model produces."""
    return int(_model().get_sentence_embedding_dimension())


def embed_texts(
    texts: Sequence[str], batch_size: int = _DEFAULT_BATCH_SIZE
) -> list[list[float]]:
    """Embed a batch of texts into unit-normalised (cosine-ready) vectors."""
    texts = list(texts)
    if not texts:
        return []
    vectors = _model().encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return [vector.tolist() for vector in vectors]


def embed_query(text: str) -> list[float]:
    """Embed a single query string."""
    return embed_texts([text])[0]

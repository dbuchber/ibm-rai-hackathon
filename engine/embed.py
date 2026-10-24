"""Local embeddings (fastembed) for seed finding, frontier pre-ranking and the RAG baseline."""

from __future__ import annotations

from functools import lru_cache

import numpy as np

MODEL = "BAAI/bge-small-en-v1.5"


@lru_cache(maxsize=1)
def _model():
    from fastembed import TextEmbedding

    return TextEmbedding(MODEL)


def embed(texts: list[str]) -> np.ndarray:
    vecs = np.array(list(_model().embed(texts)), dtype=np.float32)
    return vecs / np.linalg.norm(vecs, axis=1, keepdims=True)


def rank(question: str, texts: list[str]) -> list[float]:
    """Cosine similarity of each text to the question."""
    if not texts:
        return []
    q = embed([question])[0]
    return (embed(texts) @ q).tolist()

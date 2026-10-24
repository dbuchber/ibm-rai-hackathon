"""Local embeddings (fastembed) for seed finding, frontier pre-ranking and the RAG baseline."""

from __future__ import annotations

import threading
from functools import lru_cache

import numpy as np

MODEL = "BAAI/bge-small-en-v1.5"


_LOAD = threading.Lock()   # parallel live runs: load the model once, not once per thread


@lru_cache(maxsize=1)
def _load():
    from fastembed import TextEmbedding

    return TextEmbedding(MODEL)


def _model():
    with _LOAD:
        return _load()


_CACHE: dict[str, np.ndarray] = {}   # text -> unit vector; keyed by the text itself, so edited nodes re-embed


_COMPUTE = threading.Lock()   # one thread embeds at a time; the others then find their texts cached


def embed(texts: list[str]) -> np.ndarray:
    if any(t not in _CACHE for t in texts):
        with _COMPUTE:
            missing = list(dict.fromkeys(t for t in texts if t not in _CACHE))
            if missing:
                vecs = np.array(list(_model().embed(missing)), dtype=np.float32)
                vecs = vecs / np.linalg.norm(vecs, axis=1, keepdims=True)
                _CACHE.update(zip(missing, vecs))
    return np.array([_CACHE[t] for t in texts], dtype=np.float32)


def warm(store) -> None:
    """Embed what every live run needs (seed candidates, baseline passages) before the first question arrives."""
    from engine.seeds import SEED_CLASSES_EXCLUDED, _node_text

    nodes = store.export({"approved"}).nodes
    embed([_node_text(n) for n in nodes if n.cls not in SEED_CLASSES_EXCLUDED])
    embed([n.text for n in nodes if n.cls == "Chunk" and n.text])


def rank(question: str, texts: list[str]) -> list[float]:
    """Cosine similarity of each text to the question."""
    if not texts:
        return []
    q = embed([question])[0]
    return (embed(texts) @ q).tolist()

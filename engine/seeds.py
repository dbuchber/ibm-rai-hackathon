"""Entry nodes: embedding similarity over node labels/descriptions, merged with the store's lexical search."""

from __future__ import annotations

from contracts.ids import local_name
from contracts.models import ScoredNode, SeedsPayload
from contracts.store import GraphStore
from engine import embed

# Chunks are reached through the graph (has_chunk / mentions), not used as entry points.
SEED_CLASSES_EXCLUDED = {"Chunk"}
EXACT_BONUS = 1.0
MIN_SCORE = 0.5   # below this a node is not a plausible entry point (bge-small cosine)


def _node_text(n) -> str:
    return " — ".join(filter(None, [n.label, n.cls, n.description]))


def find(question: str, store: GraphStore, k: int = 3) -> SeedsPayload:
    nodes = [n for n in store.export({"approved"}).nodes if n.cls not in SEED_CLASSES_EXCLUDED]
    scores = embed.rank(question, [_node_text(n) for n in nodes])
    scored = {n.id: s for n, s in zip(nodes, scores)}
    # exact mention of a node's label/local id in the question is the strongest signal
    q = question.lower()
    for n in nodes:
        if n.label.lower() in q or local_name(n.id).lower() in q:
            scored[n.id] += EXACT_BONUS
    by_id = {n.id: n for n in nodes}
    top = [i for i in sorted(scored, key=lambda i: -scored[i])[:k] if scored[i] >= MIN_SCORE]
    return SeedsPayload(nodes=[ScoredNode(**by_id[i].model_dump(), score=round(scored[i], 4)) for i in top])

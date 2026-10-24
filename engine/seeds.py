"""Entry nodes: embedding similarity over node labels/descriptions, merged with the store's lexical search."""

from __future__ import annotations

from contracts.ids import local_name
from contracts.models import ScoredNode, SeedsPayload
from contracts.store import GraphStore
from engine import embed
from engine.history import Turn, entities

# Chunks are reached through the graph (has_chunk / mentions), not used as entry points.
SEED_CLASSES_EXCLUDED = {"Chunk"}
EXACT_BONUS = 1.0
MIN_SCORE = 0.5   # below this a node is not a plausible entry point (bge-small cosine)
CARRY_OVER = 2    # extra seeds a follow-up takes from the previous answer's evidence


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


def carry_over(question: str, store: GraphStore, turns: list[Turn], seeds: SeedsPayload) -> SeedsPayload:
    """Follow-ups ("who supplies it?") name no entity: add the most recent answer's entities as extra seeds.

    Entities the answer text names come first, then by similarity to the question. The question's own seeds stay
    first and untouched, so a new topic still enters the graph where it names it."""
    if not turns:
        return seeds
    last = turns[-1]
    have = {n.id for n in seeds.nodes}
    cands = [n for n in entities(last, store) if n.id not in have]
    if not cands:
        return seeds
    sims = embed.rank(question, [_node_text(n) for n in cands])
    named = [n.label.lower() in last.answer.lower() for n in cands]
    ranked = sorted(zip(named, sims, cands), key=lambda t: (not t[0], -t[1]))[:CARRY_OVER]
    extra = [ScoredNode(**n.model_dump(), score=round(s, 4)) for _, s, n in ranked]
    return SeedsPayload(nodes=[*seeds.nodes, *extra])

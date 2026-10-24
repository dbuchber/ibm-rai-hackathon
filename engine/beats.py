"""Stage directions for the animated demo: one beat before each event worth showing.

Deterministic and derived only from the run itself, so replays and live runs get the same beats.
"""

from __future__ import annotations

from contracts.models import (
    AnswerPayload, BaselinePayload, BeatPayload, EvidencePayload, RunStarted, SeedsPayload, StepPayload,
    StrategyPayload,
)


def _n(k: int, word: str) -> str:
    return f"{k} {word}" + ("" if k == 1 else "s")


class Director:
    """Remembers walked edges so the answer beat can frame the endpoints of cited triples."""

    def __init__(self) -> None:
        self.edges: dict[str, tuple[str, str]] = {}

    def beat(self, payload) -> BeatPayload | None:
        if isinstance(payload, RunStarted):
            return BeatPayload(act="question", focus=[], caption=payload.question)
        if isinstance(payload, StrategyPayload):
            return BeatPayload(act="strategy", focus=[], caption=(
                f"Plan first: {payload.question_type}. "
                f"Only {_n(len(payload.allowed_predicates), 'relation')} may be followed, at most {_n(payload.max_depth, 'hop')}."))
        if isinstance(payload, SeedsPayload):
            labels = ", ".join(n.label for n in payload.nodes[:3])
            return BeatPayload(act="seeds", focus=[n.id for n in payload.nodes], caption=(
                f"Entry points in the approved graph: {labels}." if payload.nodes
                else "No entry point in the approved graph matches the question."))
        if isinstance(payload, StepPayload):
            for e in payload.frontier:
                self.edges[e.id] = (e.s, e.o)
            followed = [d.edge_id for d in payload.decisions if d.verdict == "follow"]
            pruned = len(payload.decisions) - len(followed)
            focus = sorted({x for eid in followed for x in self.edges.get(eid, ())}) or [n.id for n in payload.nodes]
            emphasis = "enough" if payload.sufficient else "follow" if followed else "prune"
            caption = f"Hop {payload.n}: {len(followed)} followed, {pruned} pruned."
            if payload.sufficient:
                caption += " Enough evidence, the walk stops here."
            return BeatPayload(act="traverse", focus=focus, caption=caption, emphasis=emphasis, step=payload.n)
        if isinstance(payload, AnswerPayload):
            focus = {c.chunk_id for c in payload.citations if c.chunk_id}
            focus |= {x for c in payload.citations if c.edge_id for x in self.edges.get(c.edge_id, ())}
            focus |= {x for k in payload.contradictions for x in (k.a, k.b)}
            caption = f"Answer, backed by {_n(len(payload.citations), 'citation')}."
            emphasis = None
            if payload.contradictions:
                emphasis = "contradiction"
                caption += f" {_n(len(payload.contradictions), 'contradiction')} between sources, shown instead of hidden."
            if payload.canary:
                emphasis = "canary"
            return BeatPayload(act="answer", focus=sorted(focus), caption=caption, emphasis=emphasis)
        if isinstance(payload, EvidencePayload):
            return BeatPayload(act="evidence", focus=[n.id for n in payload.nodes], caption=(
                f"Exactly what the model was given: {_n(len(payload.nodes), 'node')}, {_n(len(payload.edges), 'edge')}."))
        if isinstance(payload, BaselinePayload):
            return BeatPayload(act="contrast", focus=[c.id for c in payload.chunks], caption=(
                f"The same question through plain vector search: top {len(payload.chunks)} similar text chunks, no graph."))
        return None

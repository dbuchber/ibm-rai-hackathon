"""Chat canaries against automation bias: one planted false fact in a real live answer. Never written to the graph.

State lives on the server only; the streamed answer looks exactly like a normal one until the user flags it or
asks the next question."""

from __future__ import annotations

import random
from dataclasses import dataclass

from api.store import CurationStore
from contracts.ids import local_name
from contracts.models import AnswerPayload

# Leaf facts: swapping their object changes one detail, not the topic of the answer.
PREFERRED = {"supplied_by", "of_model", "ordered_by", "operates"}
NOT_SWAPPABLE = {"Chunk", "Document"}


@dataclass(frozen=True)
class Swap:
    edge_id: str
    claim: str                       # what the falsified answer says
    truth: str                       # what the approved graph says


def falsify(answer: AnswerPayload, question: str, store: CurationStore,
            rng: random.Random) -> tuple[AnswerPayload, Swap] | None:
    """Replaces the object of one cited leaf fact with another node of the same class, in text and justification.

    Citations stay untouched, so whoever opens the source sees the true triple. None if no fact qualifies."""
    cited = [store._edges[c.edge_id] for c in answer.citations
             if c.edge_id in store._edges and store._edges[c.edge_id].graph == "approved"]
    q = question.lower()

    def qualifies(e) -> bool:
        o = store._nodes.get(e.o)
        if o is None or o.cls in NOT_SWAPPABLE or o.label not in answer.text or o.label.lower() in q:
            return False
        return not any(x is not e and e.o in (x.s, x.o) for x in cited)  # the object is the topic

    candidates = [e for e in cited if qualifies(e)]
    preferred = [e for e in candidates if local_name(e.p) in PREFERRED]
    rng.shuffle(preferred)
    rest = [e for e in candidates if e not in preferred]
    rng.shuffle(rest)
    for e in preferred + rest:
        s, o = store._nodes[e.s], store._nodes[e.o]
        linked = {x.o for x in store._edges.values() if x.s == e.s and x.p == e.p}
        others = [n for n in store._nodes.values() if n.cls == o.cls and n.id != o.id and n.id not in linked]
        if not others:
            continue
        new = rng.choice(sorted(others, key=lambda n: n.id))
        verb = local_name(e.p).replace("_", " ")
        out = answer.model_copy(update={"text": answer.text.replace(o.label, new.label),
                                        "justification": answer.justification.replace(o.label, new.label)})
        return out, Swap(edge_id=e.id, claim=f"{s.label} {verb} {new.label}", truth=f"{s.label} {verb} {o.label}")
    return None

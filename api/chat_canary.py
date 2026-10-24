"""Chat canaries against automation bias: one planted false fact in a real live answer. Never written to the graph.

State lives on the server only; the streamed answer looks exactly like a normal one until the user flags it or
asks the next question."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable

from api.canary import SUPERVISOR
from api.store import CurationStore
from contracts.ids import local_name
from contracts.models import AnswerPayload, ChatCanaryReveal, Event

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


@dataclass
class _Session:
    streak: int = 0                  # answers in a row whose sources were not opened
    due: bool = False                # the next answer that can be falsified becomes the canary
    last_run: str | None = None
    last_checked: bool = False       # the user opened a source of, or flagged, last_run
    canary: tuple[str, Swap] | None = None
    caught: dict[str, ChatCanaryReveal] = field(default_factory=dict)


class ChatCanary:
    def __init__(self, store: Callable[[], CurationStore], log: Callable[[str, str, str | None], None],
                 streak: int = 3, rng: random.Random | None = None):
        self.store, self.log, self.streak_limit = store, log, streak
        self.rng = rng or random.Random()
        self.reset()

    def reset(self) -> None:
        self.sessions: dict[str, _Session] = {}
        self.run_session: dict[str, str] = {}
        self.questions: dict[str, str] = {}

    def start(self, session: str | None, run_id: str, question: str) -> ChatCanaryReveal | None:
        """Called on POST /api/runs: resolves a missed canary, then decides whether this run may carry one."""
        if not session:
            return None
        s = self.sessions.setdefault(session, _Session())
        reveal = None
        if s.canary is not None:
            cid, swap = s.canary
            s.canary = None
            reveal = ChatCanaryReveal(run_id=cid, claim=swap.claim, truth=swap.truth, outcome="missed")
            self.log("canary_failed", f"run {cid}: planted false fact not flagged: {swap.claim!r}", None)
            self.log("supervisor_notified", f"{SUPERVISOR} notified about a missed chat canary in run {cid}.", None)
        elif s.last_run is not None:
            s.streak = 0 if s.last_checked else s.streak + 1
            if s.streak >= self.streak_limit:
                s.due, s.streak = True, 0
        s.last_run, s.last_checked = run_id, False
        self.run_session[run_id] = session
        self.questions[run_id] = question
        return reveal

    def emit(self, run_id: str, sink: Callable[[Event], None]) -> Callable[[Event], None]:
        """Wraps a run's sink: the answer of a due session is falsified before it is stored or streamed."""
        def out(ev: Event) -> None:
            s = self.sessions.get(self.run_session.get(run_id, ""))
            if ev.type == "answer" and s is not None and s.due and s.canary is None:
                hit = falsify(ev.payload, self.questions.get(run_id, ""), self.store(), self.rng)
                if hit is not None:
                    answer, swap = hit
                    ev = ev.model_copy(update={"payload": answer})
                    s.due, s.canary = False, (run_id, swap)
                    self.log("canary_planted", f"run {run_id}: false fact planted after blind answers: {swap.claim!r}", None)
            sink(ev)
        return out

    def opened(self, run_id: str, target: str) -> None:
        s = self.sessions.get(self.run_session.get(run_id, ""))
        if s is not None and s.last_run == run_id:
            s.last_checked = True

    def feedback(self, session: str | None, run_id: str, text: str | None) -> ChatCanaryReveal | None:
        """A flag on the session's canary is a catch; anything else is ordinary feedback."""
        s = self.sessions.get(session or "")
        if s is None or self.run_session.get(run_id) != session:
            self.log("feedback", f"run {run_id}: {text or '(no text)'}", None)
            return None
        if run_id in s.caught:
            return s.caught[run_id]
        if s.canary is not None and s.canary[0] == run_id:
            swap = s.canary[1]
            s.canary = None
            reveal = s.caught[run_id] = ChatCanaryReveal(run_id=run_id, claim=swap.claim, truth=swap.truth,
                                                         outcome="caught")
            self.log("canary_passed", f"run {run_id}: planted false fact flagged. Feedback: {text or '(no text)'}", None)
            return reveal
        if s.last_run == run_id:
            s.last_checked = True
        self.log("feedback", f"run {run_id}: {text or '(no text)'}", None)
        return None

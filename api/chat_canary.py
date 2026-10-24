"""Chat canaries against automation bias: one planted false fact in a real live answer. Never written to the graph.

State lives on the server only; the streamed answer looks exactly like a normal one until the user flags it or
asks the next question."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
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


def _label_re(label: str) -> re.Pattern:
    """The label as a whole token: ST02_SEALING must not match inside ST02_SEALING_TMP."""
    return re.compile(rf"(?<![\w-]){re.escape(label)}(?![\w-])")


def _family(label: str) -> str | None:
    """Code-like labels (TMP-2210, VIB-4480) only swap within their family, so a temperature model stays one."""
    m = re.match(r"^([A-Z]{2,})[-_]?\d", label)
    return m.group(1) if m else None


def falsify(answer: AnswerPayload, question: str, store: CurationStore,
            rng: random.Random) -> tuple[AnswerPayload, Swap] | None:
    """Replaces the object of one cited leaf fact with another plausible object of the same predicate.

    Citations stay untouched, so whoever opens the source sees the true triple. None if no fact qualifies."""
    cited = [store._edges[c.edge_id] for c in answer.citations
             if c.edge_id in store._edges and store._edges[c.edge_id].graph == "approved"]
    q = question.lower()
    in_text = [n.label for n in store._nodes.values() if _label_re(n.label).search(answer.text)]

    def qualifies(e) -> bool:
        o = store._nodes.get(e.o)
        if o is None or o.cls in NOT_SWAPPABLE or o.label.lower() in q or not _label_re(o.label).search(answer.text):
            return False
        if any(o.label != t and o.label in t for t in in_text):  # e.g. a station named inside its sensor ids
            return False
        return not any(x is not e and e.o in (x.s, x.o) for x in cited)  # the object is the topic

    candidates = [e for e in cited if qualifies(e)]
    preferred = [e for e in candidates if local_name(e.p) in PREFERRED]
    rng.shuffle(preferred)
    rest = [e for e in candidates if e not in preferred]
    rng.shuffle(rest)
    edges = list(store._edges.values())
    for e in preferred + rest:
        s, o = store._nodes[e.s], store._nodes[e.o]
        linked = {x.o for x in edges if x.s == e.s and x.p == e.p}
        # the predicate's actual range: things that really are supplied, monitored, ... by someone else
        others = {x.o for x in edges if x.p == e.p and x.graph == "approved"} - linked - {o.id}
        others = [store._nodes[i] for i in others if i in store._nodes and store._nodes[i].cls == o.cls
                  and store._nodes[i].label not in in_text]
        if (fam := _family(o.label)) is not None:
            others = [n for n in others if _family(n.label) == fam]
        if not others:
            continue
        new = rng.choice(sorted(others, key=lambda n: n.id))
        swap = lambda t: _label_re(o.label).sub(new.label, t)
        out = answer.model_copy(update={"text": swap(answer.text), "justification": swap(answer.justification)})
        if s.label != o.label and s.label in answer.text and s.label not in out.text:
            continue
        verb = local_name(e.p).replace("_", " ")
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
                 streak: int = 3, rng: random.Random | None = None,
                 record: Callable[[dict], None] = lambda r: None):
        """`log` writes the public audit; `record` keeps feedback text, which visitors must not see."""
        self.store, self.log, self.streak_limit, self.record = store, log, streak, record
        self.rng = rng or random.Random()
        self.reset()

    def reset(self) -> None:
        self.sessions: dict[str, _Session] = {}
        self.run_session: dict[str, str] = {}
        self.questions: dict[str, str] = {}
        self.marks: dict[str, str] = {}      # run id -> audit detail of its planted entry, while still open
        self.planted = 0

    def hidden(self, detail: str) -> bool:
        """An open canary's planted entry stays out of the public audit, or it would point at the answer."""
        return detail in self.marks.values()

    def _resolve(self, run_id: str) -> None:
        self.marks.pop(run_id, None)

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
            self._resolve(cid)
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
                try:
                    hit = falsify(ev.payload, self.questions.get(run_id, ""), self.store(), self.rng)
                except Exception:  # never lose the real answer over a canary; the session stays due
                    hit = None
                if hit is not None:
                    answer, swap = hit
                    ev = ev.model_copy(update={"payload": answer})
                    s.due, s.canary = False, (run_id, swap)
                    self.planted += 1
                    # no run id or claim here: the entry exists before the user decides
                    self.marks[run_id] = f"Chat canary #{self.planted} planted after blind answers."
                    self.log("canary_planted", self.marks[run_id], None)
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
            self._feedback(run_id, text, canary=False)
            return None
        if run_id in s.caught:
            return s.caught[run_id]
        if s.canary is not None and s.canary[0] == run_id:
            swap = s.canary[1]
            s.canary = None
            reveal = s.caught[run_id] = ChatCanaryReveal(run_id=run_id, claim=swap.claim, truth=swap.truth,
                                                         outcome="caught")
            self._resolve(run_id)
            self.log("canary_passed", f"run {run_id}: planted false fact flagged: {swap.claim!r}", None)
            self.record({"ts": _now(), "run_id": run_id, "text": text, "canary": True})
            return reveal
        if s.last_run == run_id:
            s.last_checked = True
        self._feedback(run_id, text, canary=False)
        return None

    def _feedback(self, run_id: str, text: str | None, canary: bool) -> None:
        self.log("feedback", f"run {run_id}: answer flagged" + (" with a comment" if text else ""), None)
        self.record({"ts": _now(), "run_id": run_id, "text": text, "canary": canary})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

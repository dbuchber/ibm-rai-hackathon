"""Wires strategy -> seeds -> walk -> answer -> evidence -> baseline into C3 events."""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path
from typing import Callable, Literal

from contracts.models import Event, EvidencePayload, RunFinished, RunStarted, SeedsPayload
from contracts.store import GraphStore
from engine import answer as answer_mod, baseline, evidence as evidence_mod, llm, seeds as seeds_mod, strategy, traverse
from engine.answer import INSUFFICIENT
from engine.events import Emitter
from contracts.models import AnswerPayload


def run_question(question: str, store: GraphStore, *, model: str, mode: Literal["replay", "live"],
                 emit: Callable[[Event], None], run_id: str | None = None, mock: bool = False) -> None:
    em = Emitter(run_id or uuid.uuid4().hex[:8], emit)
    em(RunStarted(question=question, model=model, mode=mode, mock=mock))
    try:
        strat = strategy.plan(question, store.predicates(), model)
        em(strat)
        sd = seeds_mod.find(question, store)
        em(sd)
        w = traverse.walk(question, store, strat, sd, model, em)
        if sd.nodes:
            ans = answer_mod.answer(question, w, store, model)
            ev = evidence_mod.evidence(w, ans)
        else:
            ans = AnswerPayload(text=INSUFFICIENT, justification="No entry node in the approved graph matched the question.",
                                citations=[])
            ev = EvidencePayload(nodes=[], edges=[])
        em(ans)
        em(ev)
        em(baseline.rag(question, store, model))
        em(RunFinished(status="ok"))
    except Exception as e:  # the run must always terminate with run.finished
        em(RunFinished(status="error", error=f"{type(e).__name__}: {e}"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--out", required=True)
    ap.add_argument("--graph", default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--mode", default="replay")
    a = ap.parse_args()
    llm.load_env()
    import os
    from contracts.rdf_store import RdfGraphStore
    store = RdfGraphStore(a.graph or os.environ.get("RAI_GRAPH", "data/graph/kg.trig"))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        run_question(a.question, store, model=a.model or llm.default_model(), mode=a.mode,
                     emit=lambda ev: (f.write(ev.model_dump_json() + "\n"), f.flush()), run_id=out.stem)


if __name__ == "__main__":
    main()

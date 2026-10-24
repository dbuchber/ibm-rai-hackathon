import pytest

from contracts.ids import node_iri
from contracts.models import AnswerPayload, Citation, ScoredNode, SeedsPayload, StrategyPayload
from contracts.rdf_store import RdfGraphStore
from engine import answer as ans_mod, evidence as ev_mod, run, traverse
from engine.traverse import Walk, _Dec, _StepOut
import re


@pytest.fixture
def store():
    return RdfGraphStore("contracts/fixtures/mini_graph.trig")


def follow_all(messages, model, schema):
    if schema is traverse._StepOut:
        ids = re.findall(r"^\[([0-9a-f]{12})\]", messages[-1]["content"], re.M)
        return _StepOut(decisions=[_Dec(edge_id=i, verdict="follow", reason="x") for i in ids], sufficient=False)
    ids = re.findall(r"^\[([0-9a-f]{12})\]", messages[-1]["content"], re.M)
    return ans_mod._Out(text="a", justification="j", citations=ids[:1] + ["deadbeef0000"])


def make_walk(store, monkeypatch):
    monkeypatch.setattr(traverse.llm, "complete_json", follow_all)
    st = StrategyPayload(question_type="t", rationale="r", prompt="p", max_depth=3,
                         allowed_predicates=[i for i, _ in store.predicates()])
    seed = store.node(node_iri("Station", "ST02_SEALING"))
    return traverse.walk("q", store, st, SeedsPayload(nodes=[ScoredNode(**seed.model_dump(), score=1)]), "m", lambda p: None)


def test_foreign_citation_dropped(store, monkeypatch):
    w = make_walk(store, monkeypatch)
    monkeypatch.setattr(ans_mod.llm, "complete_json", follow_all)
    a = ans_mod.answer("q", w, store, "m")
    assert all(c.edge_id in w.followed for c in a.citations if c.edge_id)
    assert len(a.citations) == 1
    ev = ev_mod.evidence(w, AnswerPayload(text="", justification="", citations=[Citation(edge_id="deadbeef0000")] + a.citations))
    assert all(e.id in w.followed for e in ev.edges)


def test_evidence_includes_path_to_seed(store, monkeypatch):
    w = make_walk(store, monkeypatch)
    target = next(e for e in w.followed if w.edges[e].o == node_iri("Supplier", "ThermoSense"))
    ev = ev_mod.evidence(w, AnswerPayload(text="", justification="", citations=[Citation(edge_id=target)]))
    assert len(ev.edges) == 3   # station <- sensor -> model -> supplier


def test_no_seeds_answers_insufficient(store, monkeypatch):
    monkeypatch.setattr(run.seeds_mod, "find", lambda q, s: SeedsPayload(nodes=[]))
    monkeypatch.setattr(run.strategy, "plan", lambda q, p, m, **k: StrategyPayload(question_type="t", rationale="r", prompt="p", max_depth=2, allowed_predicates=[]))
    monkeypatch.setattr(run.baseline, "rag", lambda *a, **k: __import__("contracts.models", fromlist=["x"]).BaselinePayload(chunks=[], answer="-"))
    events = []
    run.run_question("zzz", store, model="m", mode="live", emit=events.append, run_id="t")
    beats = [e.payload for e in events if e.type == "beat"]
    events = [e for e in events if e.type != "beat"]
    types = [e.type for e in events]
    assert types == ["run.started", "strategy", "seeds", "answer", "evidence", "baseline", "run.finished"]
    assert [b.act for b in beats] == ["question", "strategy", "seeds", "answer", "evidence", "contrast"]
    assert beats[0].caption == "zzz" and "No entry point" in beats[2].caption
    assert events[3].payload.text == ans_mod.INSUFFICIENT and events[4].payload.nodes == []

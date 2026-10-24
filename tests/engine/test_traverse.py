import pytest

from contracts.ids import KG, node_iri, pred_iri
from contracts.models import ScoredNode, SeedsPayload, StrategyPayload
from contracts.rdf_store import RdfGraphStore
from engine import traverse
from engine.traverse import _StepOut, _Dec


@pytest.fixture
def store():
    return RdfGraphStore("contracts/fixtures/mini_graph.trig")


def strategy(store, depth=3):
    return StrategyPayload(question_type="t", rationale="r", prompt="p", max_depth=depth,
                           allowed_predicates=[i for i, _ in store.predicates()])


def seeds(store, iri):
    return SeedsPayload(nodes=[ScoredNode(**store.node(iri).model_dump(), score=1.0)])


def follow_all(monkeypatch):
    import re
    def fake(messages, model, schema):
        ids = re.findall(r"^\[([0-9a-f]{12})\]", messages[-1]["content"], re.M)
        return _StepOut(decisions=[_Dec(edge_id=i, verdict="follow", reason="x") for i in ids], sufficient=False)
    monkeypatch.setattr(traverse.llm, "complete_json", fake)


def test_walk_on_fixture(store, monkeypatch):
    follow_all(monkeypatch)
    events = []
    w = traverse.walk("q", store, strategy(store), seeds(store, node_iri("Station", "ST02_SEALING")), "m", events.append)
    assert node_iri("Supplier", "ThermoSense") in w.nodes
    assert len(events) <= 3
    assert all(e.n == i + 1 for i, e in enumerate(events))


def test_malformed_step_falls_back(store, monkeypatch):
    def boom(*a, **k):
        raise traverse.LLMFormatError("x")
    monkeypatch.setattr(traverse.llm, "complete_json", boom)
    events = []
    w = traverse.walk("q", store, strategy(store), seeds(store, node_iri("Station", "ST02_SEALING")), "m", events.append)
    assert len(events) == 1 and events[0].sufficient and w.followed == []
    assert all(d.verdict == "prune" for d in events[0].decisions)


def test_predicate_whitelist_respected(store, monkeypatch):
    follow_all(monkeypatch)
    st = strategy(store).model_copy(update={"allowed_predicates": [pred_iri("monitors")]})
    events = []
    w = traverse.walk("q", store, st, seeds(store, node_iri("Station", "ST02_SEALING")), "m", events.append)
    assert all(e.p == pred_iri("monitors") for e in w.edges.values())

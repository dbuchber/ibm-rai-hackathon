import json
from pathlib import Path

import pytest

from contracts.ids import edge_id, node_iri, pred_iri
from contracts.models import CreateProposal, EventAdapter, GraphExport, Proposal
from contracts.rdf_store import RdfGraphStore

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "contracts" / "fixtures"
ORDER = ["run.started", "strategy", "seeds", "step", "answer", "evidence", "baseline", "run.finished"]


def _check_run(path: Path) -> None:
    events = [EventAdapter.validate_json(line) for line in path.read_text().splitlines() if line.strip()]
    assert [e.seq for e in events] == list(range(len(events)))
    # every event except run.finished is introduced by its beat: beat, run.started, beat, strategy, ...
    assert [e.type == "beat" for e in events[:-1]] == [i % 2 == 0 for i in range(len(events) - 1)]
    kinds = [e.type for e in events if e.type != "beat"]
    assert [k for i, k in enumerate(kinds) if i == 0 or k != kinds[i - 1]] == ORDER
    walked = {d.edge_id for e in events if e.type == "step" for d in e.payload.decisions if d.verdict == "follow"}
    evidence = next(e for e in events if e.type == "evidence").payload
    assert {e.id for e in evidence.edges} <= walked, "evidence may only contain walked edges"
    ids = {n.id for n in evidence.nodes}
    assert all(e.s in ids and e.o in ids for e in evidence.edges)


@pytest.fixture(scope="module")
def store():
    return RdfGraphStore(FIX / "mini_graph.trig")


def test_store_loads_named_graphs(store):
    export = store.export({"approved", "proposed", "rejected"})
    assert {e.graph for e in export.edges} == {"approved", "proposed", "rejected"}
    assert len(export.nodes) == 13


def test_neighbors_only_approved(store):
    chunk = node_iri("Chunk", "SOP-001-s2")
    assert all(e.graph == "approved" for e in store.neighbors(chunk))
    assert pred_iri("contradicts") not in {e.p for e in store.neighbors(chunk)}


def test_neighbors_filtered_by_predicate(store):
    station = node_iri("Station", "ST02_SEALING")
    only = store.neighbors(station, {pred_iri("monitors")})
    assert [e.s for e in only] == [node_iri("Sensor", "ST02_SEALING_TMP")]


def test_edge_ids_are_hashes(store):
    for e in store.export({"approved"}).edges:
        assert e.id == edge_id(e.s, e.p, e.o)


def test_search_finds_order(store):
    assert store.search("order PO-1003")[0][0].id == node_iri("ProductionOrder", "PO-1003")


def test_search_prefers_exact_ids_over_long_chunks(store):
    hits = [n.id for n, _ in store.search("Can order PO-1003 run at the sealing temperature limit of ST02_SEALING?", k=2)]
    assert set(hits) == {node_iri("ProductionOrder", "PO-1003"), node_iri("Station", "ST02_SEALING")}


def test_predicates_from_ontology(store):
    preds = dict(store.predicates())
    assert pred_iri("contradicts") in preds and pred_iri("supplied_by") in preds


def test_fixture_run_validates():
    _check_run(FIX / "run_demo.jsonl")
    _check_run(FIX / "run_canary_chat.jsonl")


def test_chat_canary_fixture_is_marked():
    events = [EventAdapter.validate_json(l) for l in (FIX / "run_canary_chat.jsonl").read_text().splitlines()]
    answer = next(e for e in events if e.type == "answer").payload
    assert answer.canary and "Velora" in answer.canary.claim
    assert next(e for e in events if e.type == "run.started").payload.mock


def test_runs_validate():
    for path in sorted((ROOT / "runs").glob("*.jsonl")):
        if path.name.startswith("live-"):   # runtime output of live mode, gitignored
            continue
        _check_run(path)


def test_fixture_json_validates():
    GraphExport.model_validate_json((FIX / "graph_export.json").read_text())
    for p in json.loads((FIX / "proposals.json").read_text()):
        Proposal.model_validate(p)


def test_fixture_has_every_proposal_kind():
    kinds = {Proposal.model_validate(p).kind for p in json.loads((FIX / "proposals.json").read_text())}
    assert kinds == {"edge", "node", "predicate"}


def test_proposal_payload_must_match_kind():
    with pytest.raises(ValueError):
        CreateProposal(kind="node", triple={"s": "a", "p": "b", "o": "c"}, rationale="x")
    ok = CreateProposal(kind="predicate", predicate={"name": "certified_by", "description": "Supplier certified_by Document."}, rationale="x")
    assert ok.triple is None


def test_real_proposals_validate():
    path = ROOT / "data" / "proposals.json"
    if path.exists():
        for p in json.loads(path.read_text()):
            Proposal.model_validate(p)


def test_real_graph_loads_if_present():
    path = ROOT / "data" / "graph" / "kg.trig"
    if not path.exists():
        pytest.skip("stream A has not produced kg.trig yet")
    store = RdfGraphStore(path)
    assert store.export({"approved"}).edges

import json
import shutil
from pathlib import Path

import httpx
import pytest

from api.main import create_app
from contracts.models import EventAdapter, GraphExport, Proposal

pytestmark = pytest.mark.asyncio

FIX = Path(__file__).resolve().parents[2] / "contracts" / "fixtures"


@pytest.fixture
def app(tmp_path):
    runs = tmp_path / "runs"
    runs.mkdir()
    shutil.copy(FIX / "run_demo.jsonl", runs / "demo-po1003.jsonl")
    return create_app(
        graph_path=FIX / "mini_graph.trig",
        runs_dir=runs,
        proposals_path=tmp_path / "proposals.json",
        proposals_seed=FIX / "proposals.json",
        web_dist=tmp_path / "nodist",
        stub_delay=0.0,
    )


@pytest.fixture
def client(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


async def test_healthz(client):
    r = await client.get("/healthz")
    assert r.json() == {"ok": True}


async def test_graph_export_validates(client):
    r = await client.get("/api/graph")
    assert r.status_code == 200
    g = GraphExport.model_validate(r.json())
    assert g.nodes and {e.graph for e in g.edges} >= {"approved", "proposed"}
    assert "rejected" not in {e.graph for e in g.edges}


async def test_list_and_get_runs(client):
    runs = (await client.get("/api/runs")).json()
    assert [r["run_id"] for r in runs] == ["demo-po1003"]
    assert runs[0]["mock"] is True
    events = (await client.get("/api/runs/demo-po1003")).json()
    assert [EventAdapter.validate_python(e).seq for e in events] == list(range(len(events)))
    assert (await client.get("/api/runs/nope")).status_code == 404


async def test_live_run_streams_events_in_order(client):
    rid = (await client.post("/api/runs", json={"question": "Who supplies the sensor?"})).json()["run_id"]
    types, seqs = [], []
    async with client.stream("GET", f"/api/runs/{rid}/stream") as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        async for line in r.aiter_lines():
            if line.startswith("data:"):
                ev = EventAdapter.validate_python(json.loads(line[5:]))
                assert ev.run_id == rid
                types.append(ev.type)
                seqs.append(ev.seq)
    assert seqs == list(range(len(seqs)))
    assert types[0] == "run.started" and types[-1] == "run.finished"
    # stored afterwards, retrievable, but not listed as a demo run
    assert len((await client.get(f"/api/runs/{rid}")).json()) == len(seqs)
    assert rid not in [r["run_id"] for r in (await client.get("/api/runs")).json()]


async def test_stored_run_stream_replays(client):
    n = len((await client.get("/api/runs/demo-po1003")).json())
    got = 0
    async with client.stream("GET", "/api/runs/demo-po1003/stream") as r:
        async for line in r.aiter_lines():
            got += line.startswith("data:")
    assert got == n


async def test_decide_moves_edge_to_approved(client, app):
    props = [Proposal.model_validate(p) for p in (await client.get("/api/proposals")).json()]
    p = props[0]
    assert p.status == "proposed"
    r = await client.post(f"/api/proposals/{p.id}", json={"decision": "approve"})
    assert r.json()["status"] == "approved"
    g = GraphExport.model_validate((await client.get("/api/graph")).json())
    assert next(e for e in g.edges if e.id == p.id).graph == "approved"
    assert app.state.store.neighbors(p.triple.s)  # traversable now
    # persisted
    saved = json.loads(app.state.proposals_path.read_text())
    assert saved[0]["status"] == "approved"


async def test_reject_removes_edge(client):
    p = (await client.get("/api/proposals")).json()[0]
    r = await client.post(f"/api/proposals/{p['id']}", json={"decision": "reject"})
    assert r.json()["status"] == "rejected"
    g = GraphExport.model_validate((await client.get("/api/graph")).json())
    assert p["id"] not in {e.id for e in g.edges}
    assert (await client.post("/api/proposals/zzz", json={"decision": "reject"})).status_code == 404


async def _by_kind(client, kind):
    return next(p for p in (await client.get("/api/proposals")).json() if p["kind"] == kind)


async def test_approve_node_creates_approved_node(client, app):
    p = await _by_kind(client, "node")
    r = await client.post(f"/api/proposals/{p['id']}", json={"decision": "approve"})
    assert r.json()["status"] == "approved"
    n = app.state.store.node("https://rai-hackathon.bbger.at/kg/sensormodel/RTD-2400")
    assert (n.cls, n.label) == ("SensorModel", "RTD-2400 (Series 2400 Pt100)")
    assert n.description.startswith("Pt100")
    g = GraphExport.model_validate((await client.get("/api/graph")).json())
    assert n.id in {x.id for x in g.nodes}


async def test_reject_node_adds_nothing(client, app):
    p = await _by_kind(client, "node")
    await client.post(f"/api/proposals/{p['id']}", json={"decision": "reject"})
    assert "https://rai-hackathon.bbger.at/kg/sensormodel/RTD-2400" not in app.state.store._nodes


async def test_approve_predicate_available_to_strategy(client, app):
    iri = "https://rai-hackathon.bbger.at/ont#recommended_replacement"
    assert iri not in dict(app.state.store.predicates())
    p = await _by_kind(client, "predicate")
    await client.post(f"/api/proposals/{p['id']}", json={"decision": "approve"})
    assert dict(app.state.store.predicates())[iri].startswith("SensorModel recommended_replacement")


async def test_create_user_proposals_of_each_kind(client, app):
    ont = "https://rai-hackathon.bbger.at/ont#"
    kg = "https://rai-hackathon.bbger.at/kg/"
    node = {"kind": "node", "node": {"cls": "Supplier", "local_id": "Acme", "label": "Acme AG"}, "rationale": "x"}
    r = await client.post("/api/proposals", json=node)
    assert r.status_code == 200, r.text
    p = Proposal.model_validate(r.json())
    assert (p.proposed_by, p.status, p.confidence) == ("user", "proposed", None)
    assert (await client.post("/api/proposals", json=node)).status_code == 409
    await client.post(f"/api/proposals/{p.id}", json={"decision": "approve"})
    assert kg + "supplier/Acme" in app.state.store._nodes

    pred = {"kind": "predicate", "predicate": {"name": "audited_by", "description": "Supplier audited_by Company."}, "rationale": "x"}
    p2 = (await client.post("/api/proposals", json=pred)).json()
    await client.post(f"/api/proposals/{p2['id']}", json={"decision": "approve"})
    assert ont + "audited_by" in dict(app.state.store.predicates())

    edge = {"kind": "edge", "triple": {"s": kg + "supplier/Acme", "p": ont + "governs", "o": kg + "supplier/Acme"}, "rationale": "x"}
    p3 = (await client.post("/api/proposals", json=edge)).json()
    g = GraphExport.model_validate((await client.get("/api/graph")).json())
    assert next(e for e in g.edges if e.id == p3["id"]).graph == "proposed"
    await client.post(f"/api/proposals/{p3['id']}", json={"decision": "approve"})
    assert app.state.store.neighbors(kg + "supplier/Acme")


async def test_create_validates(client):
    bad = {"kind": "node", "node": {"cls": "Nope", "local_id": "x", "label": "x"}, "rationale": "x"}
    assert (await client.post("/api/proposals", json=bad)).status_code == 422
    mismatch = {"kind": "node", "triple": {"s": "a", "p": "b", "o": "c"}, "rationale": "x"}
    assert (await client.post("/api/proposals", json=mismatch)).status_code == 422
    kg = "https://rai-hackathon.bbger.at/kg/"
    ghost = {"kind": "edge", "triple": {"s": kg + "x/none", "p": "https://rai-hackathon.bbger.at/ont#governs", "o": kg + "x/none"}, "rationale": "x"}
    assert (await client.post("/api/proposals", json=ghost)).status_code == 422


async def test_decisions_survive_restart(client, app, tmp_path):
    p = await _by_kind(client, "node")
    await client.post(f"/api/proposals/{p['id']}", json={"decision": "approve"})
    pred = await _by_kind(client, "predicate")
    await client.post(f"/api/proposals/{pred['id']}", json={"decision": "approve"})
    app2 = create_app(graph_path=FIX / "mini_graph.trig", runs_dir=tmp_path / "runs",
                      proposals_path=app.state.proposals_path, web_dist=tmp_path / "nodist")
    assert "https://rai-hackathon.bbger.at/kg/sensormodel/RTD-2400" in app2.state.store._nodes
    assert "https://rai-hackathon.bbger.at/ont#recommended_replacement" in dict(app2.state.store.predicates())

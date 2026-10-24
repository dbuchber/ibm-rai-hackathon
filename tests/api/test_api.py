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

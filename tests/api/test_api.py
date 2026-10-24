import asyncio
import json
import shutil
from pathlib import Path

import httpx
import pytest

from api.main import create_app
from contracts.models import EventAdapter, GraphExport, Proposal

pytestmark = pytest.mark.asyncio

FIX = Path(__file__).resolve().parents[2] / "contracts" / "fixtures"


class Clock:
    """Manual clock: each reading advances `step` seconds (slow human by default)."""
    def __init__(self, step=10.0):
        self.t, self.step = 0.0, step

    def __call__(self):
        self.t += self.step
        return self.t


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def app(tmp_path, clock):
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
        clock=clock,
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


# --- canaries ----------------------------------------------------------------

async def _make_proposals(client, n, prefix="S"):
    ids = []
    for i in range(n):
        body = {"kind": "node", "node": {"cls": "Supplier", "local_id": f"{prefix}{i}", "label": f"{prefix}{i}"}, "rationale": "x"}
        ids.append((await client.post("/api/proposals", json=body)).json()["id"])
    return ids


async def _approve(client, pid):
    return (await client.post(f"/api/proposals/{pid}", json={"decision": "approve"})).json()


async def _canary_in(client):
    items = (await client.get("/api/proposals")).json()
    c = [p for p in items if p["proposed_by"].startswith("llm:") and p["triple"]
         and p["triple"]["p"].endswith("supplied_by") and "customer" in p["triple"]["o"]]
    return items, c


async def test_no_canary_before_streak(client):
    ids = await _make_proposals(client, 3)
    for pid in ids:
        await _approve(client, pid)
    items, c = await _canary_in(client)
    assert not c and all(p["alert"] is None for p in items)


async def test_canary_after_streak_among_first_three(client):
    for pid in await _make_proposals(client, 4):
        await _approve(client, pid)
    items, c = await _canary_in(client)
    assert len(c) == 1
    assert [p["id"] for p in items].index(c[0]["id"]) < 3
    assert c[0]["status"] == "proposed" and "canary" not in json.dumps(c[0]).lower()
    # stays the same canary on refetch, never duplicated
    _, c2 = await _canary_in(client)
    assert [x["id"] for x in c2] == [c[0]["id"]]


async def test_canary_after_fast_average(app, client, clock):
    ids = await _make_proposals(client, 3)
    clock.step = 1.0  # 1 s per decision, mixed decisions: no streak of 4
    await client.get("/api/proposals")
    await client.post(f"/api/proposals/{ids[0]}", json={"decision": "approve"})
    await client.post(f"/api/proposals/{ids[1]}", json={"decision": "reject"})
    await client.post(f"/api/proposals/{ids[2]}", json={"decision": "approve"})
    _, c = await _canary_in(client)
    assert len(c) == 1


async def test_reject_or_flag_canary_passes(app, client):
    approved = []
    for rnd, decision in enumerate(("reject", "flag")):
        ids = await _make_proposals(client, 4, prefix=f"R{rnd}_")
        for pid in ids:
            await _approve(client, pid)
        approved += ids
        _, c = await _canary_in(client)
        r = (await client.post(f"/api/proposals/{c[0]['id']}", json={"decision": decision})).json()
        assert r["alert"] is None and r["status"] == "rejected"
        assert c[0]["id"] not in app.state.store._edges
    kinds = [a["kind"] for a in (await client.get("/api/audit")).json()]
    assert kinds.count("canary_passed") == 2 and "canary_failed" not in kinds
    # the earlier approvals stand
    status = {p["id"]: p["status"] for p in (await client.get("/api/proposals")).json()}
    assert all(status[i] == "approved" for i in approved)


async def test_approving_canary_fails_reverts_and_notifies(app, client):
    ids = await _make_proposals(client, 4)
    for pid in ids:
        await _approve(client, pid)
    assert "https://rai-hackathon.bbger.at/kg/supplier/S0" in app.state.store._nodes
    _, c = await _canary_in(client)
    t = c[0]["triple"]
    r = await _approve(client, c[0]["id"])
    a = r["alert"]
    assert a["reverted"] == ids and a["supervisor_notified"] == "Quality lead (mock)"
    assert r["status"] == "proposed"
    # canary never written, approvals set back
    g = GraphExport.model_validate((await client.get("/api/graph")).json())
    assert all(e.id != c[0]["id"] for e in g.edges)
    assert not any(n.id.endswith("/supplier/S0") for n in g.nodes)
    items = (await client.get("/api/proposals")).json()
    assert all(p["status"] == "proposed" for p in items if p["id"] in ids)
    assert not any(p["id"] == c[0]["id"] for p in items)  # canary is consumed
    saved = json.loads(app.state.proposals_path.read_text())
    assert all(p["status"] == "proposed" for p in saved if p["id"] in ids)
    kinds = [a["kind"] for a in (await client.get("/api/audit")).json()]
    assert kinds.count("reverted") == 4
    for k in ("canary_planted", "canary_failed", "supervisor_notified", "decision"):
        assert k in kinds
    assert (await client.get("/api/audit")).json()[0].keys() >= {"ts", "kind", "proposal_id", "detail"}


# --- runtime state outside the tracked files ------------------------------------

def test_state_initialised_from_seed_and_seed_untouched(tmp_path):
    seed = tmp_path / "proposals.json"
    shutil.copy(FIX / "proposals.json", seed)
    before = seed.read_bytes()
    state = tmp_path / "state" / "proposals.json"
    (tmp_path / "state").mkdir()
    state.write_text("")  # empty state falls back to the seed
    kw = dict(graph_path=FIX / "mini_graph.trig", runs_dir=tmp_path / "runs", web_dist=tmp_path / "x",
              proposals_path=state, proposals_seed=seed, clock=Clock())
    app = create_app(**kw)

    async def go():
        c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")
        items = (await c.get("/api/proposals")).json()
        assert len(items) == 4
        await c.post(f"/api/proposals/{items[0]['id']}", json={"decision": "approve"})
    asyncio.run(go())
    assert seed.read_bytes() == before                      # tracked file never written
    assert json.loads(state.read_text())[0]["status"] == "approved"
    assert (tmp_path / "state" / "audit.jsonl").read_text().count("\n") == 1
    app2 = create_app(**kw)                                 # restart: state wins over seed, audit reloads
    assert app2.state.proposals_path == state
    async def go2():
        c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app2), base_url="http://t")
        assert [p["status"] for p in (await c.get("/api/proposals")).json()][0] == "approved"
        assert len((await c.get("/api/audit")).json()) == 1
    asyncio.run(go2())

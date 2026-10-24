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
        invite_codes=["pitch-2026"],
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
    rid = (await client.post("/api/runs", json={"question": "Who supplies the sensor?"},
                               headers={"X-Invite-Code": "pitch-2026"})).json()["run_id"]
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
    assert types[:2] == ["beat", "run.started"] and types[-1] == "run.finished"
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


# --- hardening ---------------------------------------------------------------------

def _app(tmp_path, **kw):
    base = dict(graph_path=FIX / "mini_graph.trig", runs_dir=tmp_path / "runs",
                proposals_path=tmp_path / "state" / "proposals.json", proposals_seed=FIX / "proposals.json",
                web_dist=tmp_path / "x", stub_delay=0.0, clock=Clock(),
                invite_codes=["pitch-2026"])
    return create_app(**{**base, **kw})


def _client(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t",
                             headers={"X-Invite-Code": "pitch-2026"})


async def _wait_idle(app, c, rid):
    async with c.stream("GET", f"/api/runs/{rid}/stream") as r:
        async for _ in r.aiter_lines():
            pass
    await asyncio.sleep(0.1)


async def test_question_length_limit(tmp_path):
    c = _client(_app(tmp_path))
    assert (await c.post("/api/runs", json={"question": "x" * 501})).status_code == 422
    assert (await c.post("/api/runs", json={"question": "x" * 500})).status_code == 200


async def test_only_one_live_run_at_a_time(tmp_path):
    c = _client(_app(tmp_path, stub_delay=0.05))
    first = await c.post("/api/runs", json={"question": "a"})
    assert first.status_code == 200
    second = await c.post("/api/runs", json={"question": "b"})
    assert second.status_code == 429 and "retry-after" in second.headers
    await _wait_idle(None, c, first.json()["run_id"])
    assert (await c.post("/api/runs", json={"question": "c"})).status_code == 200


async def test_run_rate_limit_per_ip_with_retry_after(tmp_path):
    t = [0.0]
    c = _client(_app(tmp_path, run_limit=2, limit_clock=lambda: t[0]))
    h = {"CF-Connecting-IP": "1.1.1.1"}
    for _ in range(2):
        r = await c.post("/api/runs", json={"question": "a"}, headers=h)
        assert r.status_code == 200
        await _wait_idle(None, c, r.json()["run_id"])
    r = await c.post("/api/runs", json={"question": "a"}, headers=h)
    assert r.status_code == 429 and int(r.headers["retry-after"]) == 3600
    # another client is unaffected (first X-Forwarded-For entry is used without CF header)
    r = await c.post("/api/runs", json={"question": "a"}, headers={"X-Forwarded-For": "2.2.2.2, 10.0.0.1"})
    assert r.status_code == 200
    await _wait_idle(None, c, r.json()["run_id"])
    t[0] = 3601.0   # window passed
    assert (await c.post("/api/runs", json={"question": "a"}, headers=h)).status_code == 200


async def test_strict_model_has_own_tight_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("RAI_STRICT_IP_LIMIT", "1")
    monkeypatch.setenv("RAI_STRICT_GLOBAL_LIMIT", "2")
    c = _client(_app(tmp_path))
    haiku = {"question": "a", "model": "openai/claude-haiku-5-5"}

    async def post(body, ip):
        r = await c.post("/api/runs", json=body, headers={"CF-Connecting-IP": ip})
        if r.status_code == 200:
            await _wait_idle(None, c, r.json()["run_id"])
        return r.status_code

    assert await post(haiku, "1.1.1.1") == 200
    assert await post(haiku, "1.1.1.1") == 429           # per IP and model
    assert await post({"question": "a"}, "1.1.1.1") == 200   # default model unaffected
    assert await post(haiku, "2.2.2.2") == 200
    assert await post(haiku, "3.3.3.3") == 429           # global budget for the model


async def test_write_rate_limit(tmp_path):
    app = _app(tmp_path, write_limit=3)
    c = _client(app)
    pid = (await c.get("/api/proposals")).json()[0]["id"]
    codes = [(await c.post(f"/api/proposals/{pid}", json={"decision": "reject"})).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    assert (await c.get("/api/proposals")).status_code == 200   # reads stay free


async def test_admin_reset(tmp_path, monkeypatch):
    seed = tmp_path / "seed.json"
    shutil.copy(FIX / "proposals.json", seed)
    app = _app(tmp_path, proposals_seed=seed)
    c = _client(app)
    pid = next(p for p in (await c.get("/api/proposals")).json() if p["kind"] == "node")["id"]
    await c.post(f"/api/proposals/{pid}", json={"decision": "approve"})
    assert (tmp_path / "state" / "proposals.json").exists()
    node = "https://rai-hackathon.bbger.at/kg/sensormodel/RTD-2400"
    assert node in app.state.store._nodes

    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    assert (await c.post("/api/admin/reset", headers={"X-Admin-Token": "s3"})).status_code == 403  # disabled
    monkeypatch.setenv("ADMIN_TOKEN", "s3")
    assert (await c.post("/api/admin/reset")).status_code == 403
    assert (await c.post("/api/admin/reset", headers={"X-Admin-Token": "nope"})).status_code == 403
    assert node in app.state.store._nodes

    assert (await c.post("/api/admin/reset", headers={"X-Admin-Token": "s3"})).json()["ok"] is True
    assert node not in app.state.store._nodes
    assert all(p["status"] == "proposed" for p in (await c.get("/api/proposals")).json())
    assert (await c.get("/api/audit")).json() == []
    assert not (tmp_path / "state" / "proposals.json").exists()
    assert json.loads(seed.read_text())[1]["status"] == "proposed"   # seed untouched


async def test_live_run_needs_invite_code(client):
    for headers in ({}, {"X-Invite-Code": "wrong"}):
        r = await client.post("/api/runs", json={"question": "q"}, headers=headers)
        assert r.status_code == 403 and r.json()["detail"] == "invite code required"
    assert (await client.get("/api/runs/demo-po1003")).status_code == 200  # replay stays open


async def test_live_closed_without_configured_codes(tmp_path):
    app = create_app(graph_path=FIX / "mini_graph.trig", runs_dir=tmp_path / "runs", proposals_path=tmp_path / "p.json",
                     proposals_seed=FIX / "proposals.json", web_dist=tmp_path / "nodist", invite_codes=[])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/runs", json={"question": "q"}, headers={"X-Invite-Code": ""})
        assert r.status_code == 403


async def test_check_order_invite_before_busy_before_rate(tmp_path):
    c = _client(_app(tmp_path, stub_delay=0.05, run_limit=1))
    first = await c.post("/api/runs", json={"question": "a"})
    assert first.status_code == 200
    # busy AND over budget: no invite -> 403; with invite -> "busy" (5 s) wins over the hourly budget
    assert (await c.post("/api/runs", json={"question": "a"}, headers={"X-Invite-Code": "x"})).status_code == 403
    busy = await c.post("/api/runs", json={"question": "a"})
    assert busy.status_code == 429 and busy.headers["retry-after"] == "5"
    await _wait_idle(None, c, first.json()["run_id"])
    over = await c.post("/api/runs", json={"question": "a"})
    assert over.status_code == 429 and int(over.headers["retry-after"]) > 5


# --- chat canary -------------------------------------------------------------------

def _chat_app(tmp_path):
    from api.main import _stub_runner
    app = _app(tmp_path, runner=_stub_runner(0.0), chat_streak=1)
    from tests.api.test_chat_canary import _with_second_supplier
    _with_second_supplier(app.state.store)
    return app


async def _live(c, session):
    """Posts a question in a chat session and drains its stream. Returns (response json, events)."""
    r = (await c.post("/api/runs", json={"question": "Who supplies the sensor?"},
                      headers={"X-Chat-Session": session})).json()
    events = []
    async with c.stream("GET", f"/api/runs/{r['run_id']}/stream") as s:
        async for line in s.aiter_lines():
            if line.startswith("data:"):
                events.append(json.loads(line[5:]))
    return r, events


async def test_chat_canary_end_to_end(tmp_path):
    async with _client(_chat_app(tmp_path)) as c:
        first, ev1 = await _live(c, "s1")                 # blind answer
        second, ev2 = await _live(c, "s1")                # due -> canary
        assert first["reveal"] is None and second["reveal"] is None
        answer = next(e for e in ev2 if e["type"] == "answer")["payload"]
        assert "Sensorik Nord GmbH" in answer["text"] and answer["canary"] is None
        assert [e["type"] for e in ev2] == [e["type"] for e in ev1]
        third, _ = await _live(c, "s1")
        assert third["reveal"]["outcome"] == "missed" and third["reveal"]["run_id"] == second["run_id"]
        audit = {e["kind"] for e in (await c.get("/api/audit")).json()}
        assert {"canary_planted", "canary_failed", "supervisor_notified"} <= audit


async def test_chat_canary_caught_by_flag(tmp_path):
    async with _client(_chat_app(tmp_path)) as c:
        await _live(c, "s1")
        canary, _ = await _live(c, "s1")
        r = await c.post(f"/api/runs/{canary['run_id']}/feedback", json={"text": "wrong supplier"},
                         headers={"X-Chat-Session": "s1"})
        assert r.json()["reveal"]["outcome"] == "caught"


async def test_feedback_and_opened_endpoints(tmp_path):
    async with _client(_chat_app(tmp_path)) as c:
        rid = (await _live(c, "s1"))[0]["run_id"]
        assert (await c.post(f"/api/runs/{rid}/opened", json={"target": "evidence"})).status_code == 204
        r = await c.post(f"/api/runs/{rid}/feedback", json={"text": "hm"}, headers={"X-Chat-Session": "s1"})
        assert r.json() == {"reveal": None}
        assert (await c.post("/api/runs/nope/feedback", json={})).status_code == 404
        assert (await c.post("/api/runs/nope/opened", json={"target": "x"})).status_code == 404
        assert (await c.post(f"/api/runs/{rid}/feedback", json={"text": "x" * 2001})).status_code == 422
        assert any(e["kind"] == "feedback" for e in (await c.get("/api/audit")).json())


async def test_opened_is_not_write_limited(tmp_path):
    from api.main import _stub_runner
    async with _client(_app(tmp_path, runner=_stub_runner(0.0), write_limit=1)) as c:
        rid = (await _live(c, "s1"))[0]["run_id"]
        for _ in range(3):
            assert (await c.post(f"/api/runs/{rid}/opened", json={"target": "evidence"})).status_code == 204


async def test_public_audit_hides_open_chat_canary(tmp_path):
    async with _client(_chat_app(tmp_path)) as c:
        await _live(c, "s1")
        await _live(c, "s1")                              # canary planted, still open
        audit = (await c.get("/api/audit")).json()
        assert "canary_planted" not in {e["kind"] for e in audit}
        assert "Sensorik" not in json.dumps(audit)


async def test_hung_run_is_closed_after_timeout(tmp_path):
    app = _app(tmp_path, stub_delay=5.0, run_timeout=0.0)   # worker sleeps; watchdog fires on the next request
    c = _client(app)
    first = (await c.post("/api/runs", json={"question": "a"})).json()["run_id"]
    second = await c.post("/api/runs", json={"question": "b"})
    assert second.status_code == 200                         # not blocked by the hung run
    evs = (await c.get(f"/api/runs/{first}")).json()
    assert evs[-1]["type"] == "run.finished" and evs[-1]["payload"]["status"] == "error"
    assert "timed out" in evs[-1]["payload"]["error"]


# --- model choice ----------------------------------------------------------------

async def test_models_allowlist(tmp_path, monkeypatch):
    monkeypatch.setenv("RAI_MODEL", "openai/mistral-large-4-openrouter")
    c = _client(_app(tmp_path))
    ms = (await c.get("/api/models")).json()
    assert ms[0] == {"id": "openai/mistral-large-4-openrouter", "label": "Mistral Large 4", "provider": "gateway"}
    assert {m["id"] for m in ms[1:]} == {"openai/ibm/granite-4-h-small", "openai/watsonx/mistralai/mistral-medium-2505",
                                         "openai/meta-llama/llama-3-3-70b-instruct", "openai/claude-haiku-5-5", "openai/gpt-6-luna"}
    assert all(m["provider"] == "ibm-ica" for m in ms[1:])


async def test_models_ica_default_listed_once_first(tmp_path, monkeypatch):
    monkeypatch.setenv("RAI_MODEL", "openai/ibm/granite-4-h-small")
    ms = (await _client(_app(tmp_path)).get("/api/models")).json()
    assert ms[0] == {"id": "openai/ibm/granite-4-h-small", "label": "IBM Granite 4 H Small", "provider": "ibm-ica"}
    assert [m["id"] for m in ms].count("openai/ibm/granite-4-h-small") == 1
    assert "openai/mistral-large-4-openrouter" in [m["id"] for m in ms]


async def test_run_model_choice(tmp_path, monkeypatch):
    monkeypatch.setenv("RAI_MODEL", "openai/mistral-large-4-openrouter")
    c = _client(_app(tmp_path))
    bad = await c.post("/api/runs", json={"question": "q", "model": "openai/evil-model"})
    assert bad.status_code == 422
    rid = (await c.post("/api/runs", json={"question": "q", "model": "openai/ibm/granite-4-h-small"})).json()["run_id"]
    await _wait_idle(None, c, rid)
    started = next(e for e in (await c.get(f"/api/runs/{rid}")).json() if e["type"] == "run.started")
    assert started["payload"]["model"] == "openai/ibm/granite-4-h-small"
    rid2 = (await c.post("/api/runs", json={"question": "q"})).json()["run_id"]   # default stays RAI_MODEL
    await _wait_idle(None, c, rid2)
    started2 = next(e for e in (await c.get(f"/api/runs/{rid2}")).json() if e["type"] == "run.started")
    assert started2["payload"]["model"] == "openai/mistral-large-4-openrouter"
    # invite still required
    assert (await c.post("/api/runs", json={"question": "q", "model": "openai/ibm/granite-4-h-small"},
                         headers={"X-Invite-Code": "no"})).status_code == 403


def test_route_ica_vs_gateway(monkeypatch):
    from engine.models import ICA_BASE, route
    monkeypatch.setenv("ICA_API_KEY", "ica-k")
    monkeypatch.setenv("LITELLM_API_KEY", "gw-k")
    monkeypatch.setenv("LITELLM_BASE_URL", "http://gw/v1")
    assert route("openai/ibm/granite-4-h-small") == {"api_base": ICA_BASE, "api_key": "ica-k"}
    assert route("openai/mistral-large-4-openrouter") == {"api_base": "http://gw/v1", "api_key": "gw-k"}


def test_temperature_per_model_reaches_litellm(monkeypatch):
    import sys, types
    from engine import llm
    from engine.models import temperature
    assert temperature("openai/claude-haiku-5-5") == 1.0 and temperature("openai/gpt-6-luna") == 1.0
    assert temperature("openai/ibm/granite-4-h-small") == 0.0 and temperature("openai/mistral-large-4-openrouter") == 0.0
    seen = {}

    def fake_completion(**kw):
        seen[kw["model"]] = kw["temperature"]
        msg = types.SimpleNamespace(content='{"ok": true}')
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])
    monkeypatch.setitem(sys.modules, "litellm", types.SimpleNamespace(completion=fake_completion))
    for m in ("openai/claude-haiku-5-5", "openai/gpt-6-luna", "openai/ibm/granite-4-h-small"):
        llm._raw([{"role": "user", "content": "x"}], m)
    assert seen == {"openai/claude-haiku-5-5": 1.0, "openai/gpt-6-luna": 1.0, "openai/ibm/granite-4-h-small": 0.0}

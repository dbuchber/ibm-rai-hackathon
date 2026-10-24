"""Finding 1: curation writes need a reviewer code, enforced in the application."""

import json
import shutil
from pathlib import Path

import httpx
import pytest

from api.main import create_app

pytestmark = pytest.mark.asyncio
FIX = Path(__file__).resolve().parents[2] / "contracts" / "fixtures"
NODE = {"kind": "node", "node": {"cls": "Supplier", "local_id": "Acme", "label": "Acme AG"}, "rationale": "x"}


def make(tmp_path, **kw):
    state = tmp_path / "state" / "proposals.json"
    app = create_app(graph_path=FIX / "mini_graph.trig", runs_dir=tmp_path / "runs", proposals_path=state,
                     proposals_seed=FIX / "proposals.json", web_dist=tmp_path / "x", **kw)
    return app, state


def client(app, code=None):
    h = {} if code is None else {"X-Reviewer-Code": code}
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t", headers=h)


@pytest.mark.parametrize("code", ["", "wrong", "rev-tes"])
async def test_decide_and_create_forbidden_without_valid_code(tmp_path, code):
    app, state = make(tmp_path)
    c = client(app, code)
    before = app.state.store.export({"approved"})
    pid = (await c.get("/api/proposals")).json()[0]["id"]
    assert (await c.post(f"/api/proposals/{pid}", json={"decision": "approve"})).status_code == 403
    assert (await c.post("/api/proposals", json=NODE)).status_code == 403
    assert not state.exists()                       # nothing persisted
    assert next(p for p in (await c.get("/api/proposals")).json() if p["id"] == pid)["status"] == "proposed"
    assert app.state.store.export({"approved"}) == before


async def test_missing_header_forbidden(tmp_path):
    app, _ = make(tmp_path)
    c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t", headers={"X-Reviewer-Code": "x"})
    del c.headers["X-Reviewer-Code"]
    assert (await c.post("/api/proposals", json=NODE)).status_code == 403


async def test_valid_code_writes(tmp_path):
    app, state = make(tmp_path)
    c = client(app, "rev-test")
    pid = (await c.get("/api/proposals")).json()[0]["id"]
    r = await c.post(f"/api/proposals/{pid}", json={"decision": "approve"})
    assert r.status_code == 200 and r.json()["status"] == "approved"
    assert (await c.post("/api/proposals", json=NODE)).status_code == 200
    assert any(p["status"] == "approved" for p in json.loads(state.read_text()))


async def test_reads_stay_open(tmp_path):
    app, _ = make(tmp_path)
    c = client(app, "")
    for path in ("/api/proposals", "/api/graph", "/api/audit", "/api/runs"):
        assert (await c.get(path)).status_code == 200


async def test_no_codes_configured_means_read_only(tmp_path, monkeypatch):
    monkeypatch.delenv("RAI_REVIEWER_CODES")
    app, state = make(tmp_path)
    c = client(app, "anything")
    pid = (await c.get("/api/proposals")).json()[0]["id"]
    assert (await c.post(f"/api/proposals/{pid}", json={"decision": "approve"})).status_code == 403
    assert (await c.get("/api/curation")).json() == {"writable": False}
    assert not state.exists()


async def test_curation_status_endpoint(tmp_path):
    app, _ = make(tmp_path)
    assert (await client(app).get("/api/curation")).json() == {"writable": True}


async def test_admin_reset_still_needs_admin_token_not_reviewer_code(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "adm")
    app, _ = make(tmp_path)
    c = client(app, "rev-test")
    assert (await c.post("/api/admin/reset")).status_code == 403
    assert (await c.post("/api/admin/reset", headers={"X-Admin-Token": "adm"})).status_code == 200

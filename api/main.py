"""FastAPI over the C4 endpoints. Runs are JSONL files in `runs/`; live runs stream while they are written."""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import hmac
import secrets

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from api.canary import CanaryGuard
from api.chat_canary import ChatCanary
from engine.models import allowed_models
from api.limits import RateLimiter, client_ip
from api.store import CurationStore
from contracts.ids import edge_id, node_iri, pred_iri, proposal_id
from contracts.models import (ModelInfo, RunFinished, RunFinishedEvent, CreateProposal, CreateRun, CreateRunResponse,
                              EventAdapter, Feedback, FeedbackResponse, GraphExport, SourceOpened,
                              AuditEntry, Proposal, ProposalDecision, RunSummary)

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "contracts" / "fixtures"

Emit = Callable[[object], None]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _stub_runner(delay: float):
    """Stand-in for the engine: replays the fixture run with 400 ms between events."""
    def run(question: str, store, *, model: str, mode: str, emit: Emit) -> None:
        for line in (FIXTURES / "run_demo.jsonl").read_text().splitlines():
            ev = EventAdapter.validate_json(line)
            if ev.type == "run.started":
                ev = ev.model_copy(update={"payload": ev.payload.model_copy(
                    update={"question": question, "mode": "live", "mock": True, "model": model})})
            elif ev.type == "beat" and ev.payload.act == "question":
                ev = ev.model_copy(update={"payload": ev.payload.model_copy(update={"caption": question})})
            emit(ev)
            time.sleep(delay)
    return run


def _real_runner():
    try:
        from engine.run import run_question  # stream B
        return run_question
    except Exception:
        return None


class LiveRun:
    def __init__(self, run_id: str, path: Path):
        self.run_id, self.path = run_id, path
        self.events: list[dict] = []
        self.done = False
        self.started = time.monotonic()
        self.lock = threading.Lock()

    def add(self, ev, close: bool = False) -> None:
        with self.lock:
            if self.done:  # run was closed (finished or timed out): drop late events from the worker thread
                return
            ev = ev.model_copy(update={"run_id": self.run_id, "seq": len(self.events)})
            d = json.loads(ev.model_dump_json())
            self.events.append(d)
            with self.path.open("a") as f:
                f.write(json.dumps(d) + "\n")
            if close:
                self.done = True


def create_app(graph_path: Path | None = None, runs_dir: Path | None = None,
               proposals_path: Path | None = None, proposals_seed: Path | None = None,
               web_dist: Path | None = None, stub_delay: float = 0.4,
               clock: Callable[[], float] | None = None,
               limit_clock: Callable[[], float] = time.monotonic,
               run_limit: int = 15, write_limit: int = 120, max_question: int = 500, run_timeout: float = 300.0,
               invite_codes: list[str] | None = None, runner: Callable | None = None,
               chat_streak: int | None = None) -> FastAPI:
    env = os.environ.get
    kg = ROOT / "data" / "graph" / "kg.trig"
    graph_path = Path(graph_path or env("RAI_GRAPH") or kg)
    if not graph_path.exists():  # stream A's kg.trig not landed yet
        graph_path = FIXTURES / "mini_graph.trig"
    runs_dir = Path(runs_dir or env("RAI_RUNS") or ROOT / "runs")
    # Runtime state lives in data/state/ (gitignored); data/proposals.json stays the versioned starting point.
    proposals_path = Path(proposals_path or env("RAI_PROPOSALS") or ROOT / "data" / "state" / "proposals.json")
    tracked = ROOT / "data" / "proposals.json"
    proposals_seed = Path(proposals_seed or (tracked if tracked.exists() else FIXTURES / "proposals.json"))
    web_dist = Path(web_dist or ROOT / "web" / "dist")
    runs_dir.mkdir(parents=True, exist_ok=True)
    # Live runs cost LLM calls, so they need an invitation. No codes configured = live mode closed.
    if invite_codes is None:
        invite_codes = [c.strip() for c in env("RAI_INVITE_CODES", "").split(",") if c.strip()]

    app = FastAPI(title="Graph Anchor API")
    proposals: dict[str, Proposal] = {}
    store: CurationStore
    guard: CanaryGuard

    def apply(p: Proposal, status: str) -> None:
        """Mirror a proposal's status into the in-memory graph/ontology."""
        if p.kind == "edge":
            t = p.triple
            if status != "proposed" or edge_id(t.s, t.p, t.o) not in store._edges:
                store.add_edge(t.s, t.p, t.o, status)
        elif status == "approved" and p.kind == "node":
            store.add_node(p.node)
        elif status == "approved" and p.kind == "predicate":
            store.add_predicate(p.predicate)

    def load_state() -> None:
        """(Re)build graph, proposals and canary guard from data/state, falling back to the seed."""
        nonlocal store, guard
        store = CurationStore(graph_path)
        state_ok = proposals_path.exists() and json.loads(proposals_path.read_text() or "[]")
        src = proposals_path if state_ok else proposals_seed
        proposals.clear()
        proposals.update({p.id: p for p in (Proposal.model_validate(x) for x in json.loads(src.read_text()))})
        for p in proposals.values():  # replay persisted decisions after a restart
            if p.status == "approved" or p.kind == "edge":
                apply(p, p.status)
        guard = CanaryGuard(store, env("RAI_MODEL", "stub"), audit_path=proposals_path.parent / "audit.jsonl",
                            streak=int(env("RAI_CANARY_STREAK", "4")), clock=clock)
        app.state.store = store

    load_state()
    live: dict[str, LiveRun] = {}
    # lambdas: load_state() rebuilds store and guard, chat canaries share the curation audit log
    feedback_path = proposals_path.parent / "feedback.jsonl"   # feedback text: never served

    def keep_feedback(rec: dict) -> None:
        feedback_path.parent.mkdir(parents=True, exist_ok=True)
        with feedback_path.open("a") as f:
            f.write(json.dumps(rec) + "\n")

    chat = ChatCanary(lambda: store, lambda kind, detail, pid=None: guard.log(kind, detail, pid),
                      streak=chat_streak or int(env("RAI_CHAT_CANARY_STREAK", "3")), record=keep_feedback)
    run_rl = RateLimiter(run_limit, clock=limit_clock)
    write_rl = RateLimiter(write_limit, clock=limit_clock)

    def too_many(retry: int, what: str) -> HTTPException:
        return HTTPException(429, what, headers={"Retry-After": str(retry)})

    def write_limited(request: Request) -> None:
        ip = client_ip(request)
        if (retry := write_rl.retry_after(ip)) is not None:
            raise too_many(retry, "too many changes, slow down")
        write_rl.record(ip)
    runner = runner or _real_runner() or _stub_runner(stub_delay)
    model = env("RAI_MODEL", "stub")

    app.state.proposals_path = proposals_path

    def read_run(run_id: str) -> list[dict]:
        if run_id in live:
            with live[run_id].lock:
                return list(live[run_id].events)
        f = runs_dir / f"{run_id}.jsonl"
        if "/" in run_id or not f.exists():
            raise HTTPException(404, "unknown run")
        return [json.loads(l) for l in f.read_text().splitlines() if l.strip()]

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.get("/api/graph")
    def graph() -> GraphExport:
        return store.export({"approved", "proposed"})

    @app.get("/api/models")
    def models() -> list[ModelInfo]:
        return [ModelInfo(id=m.id, label=m.label, provider=m.provider) for m in allowed_models()]

    @app.get("/api/runs")
    def runs() -> list[RunSummary]:
        out = []
        for f in sorted(runs_dir.glob("*.jsonl")):
            first = next((l for l in f.read_text().splitlines()[:2] if '"run.started"' in l), None)
            if not first:
                continue
            ev = EventAdapter.validate_json(first)  # line 0 is its beat
            if ev.type == "run.started" and ev.payload.mode != "live":
                out.append(RunSummary(run_id=f.stem, question=ev.payload.question, mock=ev.payload.mock))
        return out

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> list[dict]:
        return read_run(run_id)

    @app.post("/api/runs")
    async def create_run(body: CreateRun, request: Request, x_invite_code: str = Header(""),
                         x_chat_session: str | None = Header(None)) -> CreateRunResponse:
        # order: invite code, then input size, then one run at a time, then per-IP hourly budget
        if not any(secrets.compare_digest(x_invite_code.encode(), c.encode()) for c in invite_codes):
            raise HTTPException(403, "invite code required")
        run_model = body.model or model
        if body.model and body.model not in {m.id for m in allowed_models()}:
            raise HTTPException(422, "model not allowed")
        if len(body.question) > max_question:
            raise HTTPException(422, f"question longer than {max_question} characters")
        for r in live.values():  # a hung LLM call must not block live mode for everyone
            if not r.done and time.monotonic() - r.started > run_timeout:
                r.add(RunFinishedEvent(run_id=r.run_id, seq=0, ts=_now(), payload=RunFinished(
                    status="error", error=f"run timed out after {int(run_timeout)} s")), close=True)
        if any(not r.done for r in live.values()):
            raise too_many(5, "another live run is in progress")
        ip = client_ip(request)
        if (retry := run_rl.retry_after(ip)) is not None:
            raise too_many(retry, "run limit reached for this client")
        run_rl.record(ip)
        run_id = "live-" + uuid.uuid4().hex[:8]
        lr = LiveRun(run_id, runs_dir / f"{run_id}.jsonl")
        live[run_id] = lr
        reveal = chat.start(x_chat_session, run_id, body.question)
        emit = chat.emit(run_id, lr.add)

        def work():
            try:
                runner(body.question, store, model=run_model, mode="live", emit=emit)
            except Exception as e:  # keep the stream well-formed
                lr.add(RunFinishedEvent(run_id=run_id, seq=0, ts=_now(),
                                        payload=RunFinished(status="error", error=str(e))))
            finally:
                lr.done = True
        threading.Thread(target=work, daemon=True).start()
        return CreateRunResponse(run_id=run_id, reveal=reveal)

    @app.post("/api/runs/{run_id}/feedback", dependencies=[Depends(write_limited)])
    def feedback(run_id: str, body: Feedback, x_chat_session: str | None = Header(None)) -> FeedbackResponse:
        read_run(run_id)  # 404
        return FeedbackResponse(reveal=chat.feedback(x_chat_session, run_id, body.text))

    # not write-limited: a silent 429 would make a user who checked look blind; it only flips a flag
    @app.post("/api/runs/{run_id}/opened", status_code=204)
    def opened(run_id: str, body: SourceOpened) -> Response:
        read_run(run_id)  # 404
        chat.opened(run_id, body.target)
        return Response(status_code=204)

    @app.get("/api/runs/{run_id}/stream")
    async def stream(run_id: str):
        read_run(run_id)  # 404 early

        async def gen():
            i = 0
            while True:
                evs = read_run(run_id)
                while i < len(evs):
                    yield {"data": json.dumps(evs[i])}
                    i += 1
                if run_id not in live or live[run_id].done and i >= len(read_run(run_id)):
                    return
                await asyncio.sleep(0.05)
        return EventSourceResponse(gen())

    @app.get("/api/proposals")
    def list_proposals() -> list[Proposal]:
        return guard.listing(list(proposals.values()))

    def revert(pid: str) -> None:
        p = proposals[pid].model_copy(update={"status": "proposed"})
        proposals[pid] = p
        if p.kind == "edge":
            store.set_edge_graph(pid, "proposed")
        elif p.kind == "node":
            store.remove_node(node_iri(p.node.cls, p.node.local_id))
        else:
            store.remove_predicate(p.predicate.name)
        save()

    @app.get("/api/audit")
    def audit() -> list[AuditEntry]:
        return [e for e in guard.audit if not chat.hidden(e.detail)]

    def save() -> None:
        proposals_path.parent.mkdir(parents=True, exist_ok=True)
        proposals_path.write_text(json.dumps([x.model_dump() for x in proposals.values()], indent=2))

    @app.post("/api/proposals", dependencies=[Depends(write_limited)])
    def create_proposal(body: CreateProposal) -> Proposal:
        if body.kind == "edge":
            t = body.triple
            pid = proposal_id("edge", triple=(t.s, t.p, t.o))
            if t.s not in store._nodes or t.o not in store._nodes:
                raise HTTPException(422, "triple endpoints must be existing nodes")
            if t.p not in {iri for iri, _ in store.predicates()}:
                raise HTTPException(422, "unknown predicate")
        elif body.kind == "node":
            n = body.node
            if not store.has_class(n.cls):
                raise HTTPException(422, "unknown class")
            pid = proposal_id("node", iri=node_iri(n.cls, n.local_id))
            if node_iri(n.cls, n.local_id) in store._nodes:
                raise HTTPException(409, "node already exists")
        else:
            iri = pred_iri(body.predicate.name)
            pid = proposal_id("predicate", iri=iri)
            if iri in {i for i, _ in store.predicates()}:
                raise HTTPException(409, "predicate already exists")
        if pid in proposals:
            raise HTTPException(409, "proposal already exists")
        p = Proposal(**body.model_dump(), id=pid, proposed_by="user", status="proposed")
        proposals[pid] = p
        apply(p, "proposed")  # edges show up dashed in the graph
        save()
        return p

    @app.post("/api/proposals/{pid}", dependencies=[Depends(write_limited)])
    def decide(pid: str, body: ProposalDecision) -> Proposal:
        if guard.is_canary(pid):
            return guard.decide_canary(body.decision, revert)
        p = proposals.get(pid)
        if p is None:
            raise HTTPException(404, "unknown proposal")
        guard.note_decision(pid, body.decision)
        status = "approved" if body.decision == "approve" else "rejected"  # flag = reject
        p = p.model_copy(update={"status": status})
        proposals[pid] = p
        apply(p, status)
        save()
        return p

    @app.post("/api/admin/reset")
    def admin_reset(x_admin_token: str | None = Header(default=None)) -> dict:
        expected = env("ADMIN_TOKEN", "")
        if not expected or not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
            raise HTTPException(403, "forbidden")
        for f in (proposals_path, proposals_path.parent / "audit.jsonl"):
            f.unlink(missing_ok=True)
        load_state()
        chat.reset()
        return {"ok": True, "proposals": len(proposals)}

    if web_dist.is_dir():
        app.mount("/", StaticFiles(directory=web_dist, html=True), name="web")
    return app


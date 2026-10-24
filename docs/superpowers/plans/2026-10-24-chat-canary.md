# Chat Canary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The live chat plants one falsified graph fact into a real answer after blind trust, and resolves it on flag (caught) or on the next question (missed).

**Architecture:** A new `api/chat_canary.py` holds per-session state and a pure `falsify()` function. `api/main.py` asks it at `POST /api/runs` whether the run is a canary and wraps the run's emitter, so the `answer` event is falsified before it is stored or streamed. Two new endpoints (`feedback`, `opened`). Audit goes through the curation `CanaryGuard.log`, so both canaries share one log.

**Tech Stack:** Python 3.12, FastAPI, pydantic v2, pytest + httpx ASGI; TypeScript (only `web/src/data.ts`).

**Spec:** `docs/superpowers/specs/2026-10-24-chat-canary-design.md`

## Global Constraints

- Trigger: `RAI_CHAT_CANARY_STREAK` (default `3`) answers in a row whose sources were not opened.
- Session header: `X-Chat-Session`. Missing header = never a canary.
- The stream of a canary run is indistinguishable from a normal run: `answer.canary` stays `null`, same event types and count, citations/evidence/beats unchanged.
- A canary is never written to the graph (`urn:g:approved` / `urn:g:proposed`).
- Supervisor string: `"Quality lead (mock)"` (reuse `api.canary.SUPERVISOR`).
- `mock-canary-chat` and all recorded runs stay unchanged.
- `web/` belongs to the UI/UX team. This plan touches only `web/src/data.ts`, the generated `web/src/contracts.ts`, and `web/FRONTEND.md`.
- Only the orchestrator changes `contracts/`. After changing `contracts/models.py`: `PYTHONPATH=. uv run python scripts/export_schema.py`, then `cd web && npm run types`.

## Review Focus

- A flag on a run of **another** session must be treated as normal feedback, with no reveal (no canary leak). Test in Task 3.
- `feedback` / `opened` on an unknown run id → 404. Test in Task 4.
- A canary run that ends in `run.finished` error before the answer must not plant anything; the session stays due. Test in Task 3.
- Flagging the canary twice writes `canary_passed` once and returns the same reveal. Test in Task 3.
- Feedback text longer than 2000 characters → 422 (abuse of a public endpoint). Test in Task 4.

---

### Task 1: Base on D's branch, extend the contract

**Files:**
- Modify: `contracts/models.py` (C3 `AuditEntry.kind`, C4 `CreateRunResponse`, new models)
- Modify: `scripts/export_schema.py` (register new schemas)
- Regenerate: `contracts/schema/*.json`, `web/src/contracts.ts`
- Test: `tests/test_contracts.py`

**Interfaces:**
- Produces:
  - `ChatCanaryReveal(run_id: str, claim: str, truth: str, outcome: Literal["caught", "missed"])`
  - `CreateRunResponse(run_id: str, reveal: ChatCanaryReveal | None = None)`
  - `Feedback(text: str | None = Field(None, max_length=2000))`
  - `FeedbackResponse(reveal: ChatCanaryReveal | None = None)`
  - `SourceOpened(target: str)`: edge id, chunk IRI or `"evidence"`
  - `AuditEntry.kind` gains `"feedback"`

- [ ] **Step 1: Merge D's branch into main**

```bash
git fetch hetzner && git merge --no-edit hetzner/stream/d-api
PYTHONPATH=. uv run pytest -q
```
Expected: all green. If there are conflicts in `api/main.py`, stop and ask the orchestrator.

- [ ] **Step 2: Write the failing test**

```python
def test_chat_canary_contract():
    assert CreateRunResponse(run_id="r").reveal is None
    r = ChatCanaryReveal(run_id="r", claim="a", truth="b", outcome="missed")
    assert CreateRunResponse(run_id="r", reveal=r).reveal.outcome == "missed"
    with pytest.raises(ValueError):
        Feedback(text="x" * 2001)
    AuditEntry(ts="t", kind="feedback", detail="run live-1: wrong supplier")
```

- [ ] **Step 3: Run it, expect ImportError** — `PYTHONPATH=. uv run pytest tests/test_contracts.py::test_chat_canary_contract -v`

- [ ] **Step 4: Add the models** (C4 section, docstrings name the endpoint as in the spec), register `ChatCanaryReveal`, `Feedback`, `FeedbackResponse`, `SourceOpened` in `SCHEMAS`, run export + `npm run types`.

- [ ] **Step 5: Run tests and the web build** — `PYTHONPATH=. uv run pytest -q` and `cd web && npm run build`. Expected: green, build succeeds.

- [ ] **Step 6: Commit** — `feat(contracts): chat canary reveal, feedback and source-opened shapes`

---

### Task 2: `falsify()`, the fact swap

**Files:**
- Create: `api/chat_canary.py`
- Test: `tests/api/test_chat_canary.py`

**Interfaces:**
- Consumes: `CurationStore` (`_nodes: dict[str, Node]`, `_edges: dict[str, Edge]`, `add_node(NodeSpec)`), `AnswerPayload`.
- Produces: `falsify(answer: AnswerPayload, question: str, store: CurationStore, rng: random.Random) -> tuple[AnswerPayload, Swap] | None` and `@dataclass Swap(edge_id: str, claim: str, truth: str)`.

Algorithm (from the spec, decided here):
1. Candidates = cited `edge_id`s whose edge exists in `store._edges` with `graph == "approved"` and whose object label occurs verbatim in `answer.text`.
2. Drop a candidate if the object label occurs in `question` (case-insensitive), or the object is an endpoint of another cited edge, or the object is a Chunk/Document.
3. Prefer predicates whose local name is in `{"supplied_by", "of_model", "ordered_by", "operates"}`; else any remaining. Pick with `rng.choice` from the preferred group.
4. Replacement = approved node with the same `cls`, `!= object`, with no edge `(subject, p, replacement)`. `rng.choice`. None available → try the next candidate; none left → return `None`.
5. Replace every occurrence of the old label in `text` and `justification`. `claim = f"{subject.label} {pred.replace('_', ' ')} {new.label}"`, `truth` the same with the old label. Citations untouched.

- [ ] **Step 1: Write the failing tests** (fixture: `CurationStore(FIX / "mini_graph.trig")` plus `store.add_node(NodeSpec(cls="Supplier", local_id="SensorikNord", label="Sensorik Nord GmbH"))`; answer = the `answer` payload from `contracts/fixtures/run_demo.jsonl`)

```python
def test_swaps_leaf_supplier(store, answer):
    out, swap = falsify(answer, "Who supplies the sensor?", store, random.Random(0))
    assert "Sensorik Nord GmbH" in out.text and "ThermoSense GmbH" not in out.text
    assert out.citations == answer.citations and out.canary is None
    assert swap.claim == "TMP-2210 supplied by Sensorik Nord GmbH"
    assert swap.truth == "TMP-2210 supplied by ThermoSense GmbH"

def test_never_swaps_the_topic(store, answer):
    assert falsify(answer, "What does ThermoSense GmbH supply?", store, random.Random(0)) is None

def test_none_without_same_class_alternative(answer):
    bare = CurationStore(FIX / "mini_graph.trig")  # only one Supplier
    assert falsify(answer, "Who supplies the sensor?", bare, random.Random(0)) is None
```

- [ ] **Step 2: Run, expect ImportError** — `PYTHONPATH=. uv run pytest tests/api/test_chat_canary.py -v`
- [ ] **Step 3: Implement `falsify` and `Swap`** in `api/chat_canary.py`. Module docstring in the style of `api/canary.py`.
- [ ] **Step 4: Run, expect PASS**
- [ ] **Step 5: Commit** — `feat(api): chat canary fact swap`

---

### Task 3: `ChatCanary`, session state and outcomes

**Files:**
- Modify: `api/chat_canary.py`
- Test: `tests/api/test_chat_canary.py`

**Interfaces:**
- Consumes: `falsify`, `Swap` (Task 2), `ChatCanaryReveal` (Task 1), `api.canary.SUPERVISOR`.
- Produces:

```python
class ChatCanary:
    def __init__(self, store: Callable[[], CurationStore], log: Callable[[str, str, str | None], None],
                 streak: int = 3, rng: random.Random | None = None): ...
    def start(self, session: str | None, run_id: str, question: str) -> ChatCanaryReveal | None
        # evaluates the session's previous run, returns a "missed" reveal if its canary is open,
        # then marks run_id as canary-due when the counter reached `streak`
    def emit(self, run_id: str, sink: Callable[[Event], None]) -> Callable[[Event], None]
        # wraps the run's sink; on a due run's AnswerEvent applies falsify(), on success stores
        # the planted canary and logs "canary_planted"; on None the session stays due
    def opened(self, run_id: str, target: str) -> None
    def feedback(self, session: str | None, run_id: str, text: str | None) -> ChatCanaryReveal | None
    def reset(self) -> None
```

State per session: `streak: int`, `last_run: str | None`, `last_opened: bool`, `due: bool`, `canary: (run_id, Swap) | None`, `caught: set[run_id]`. `run_session: dict[run_id, session]`.

Audit (`log(kind, detail, None)`, run id in `detail`): `canary_planted` on plant, `canary_passed` with feedback text on catch, `canary_failed` + `supervisor_notified` on miss, `feedback` for normal flags.

- [ ] **Step 1: Write the failing tests** (drive with a fake run: `start` → `emit(...)(AnswerEvent with the fixture answer)`; `log` collects into a list)

```python
def test_three_blind_answers_then_canary(cc, log):
    for i in range(3): ask(cc, "s", f"r{i}")
    ask(cc, "s", "r3")
    assert planted(cc, "r3") and [k for k, *_ in log].count("canary_planted") == 1

def test_opened_source_resets_counter(cc):
    for i in range(3):
        ask(cc, "s", f"r{i}"); cc.opened(f"r{i}", "evidence")
    ask(cc, "s", "r3")
    assert not planted(cc, "r3")

def test_flag_on_normal_answer_resets_counter(cc, log):
    for i in range(3): ask(cc, "s", f"r{i}")
    assert cc.feedback("s", "r2", "unclear") is None   # r2 was the 3rd blind answer
    ask(cc, "s", "r3")
    assert not planted(cc, "r3") and ("feedback" in {k for k, *_ in log})

def test_flag_on_canary_is_caught_once(cc, log):
    plant(cc, "s", "rc")
    r1 = cc.feedback("s", "rc", "wrong supplier"); r2 = cc.feedback("s", "rc", None)
    assert r1.outcome == "caught" and r1 == r2
    assert [k for k, *_ in log].count("canary_passed") == 1

def test_next_question_reveals_missed(cc, log):
    plant(cc, "s", "rc")
    reveal = cc.start("s", "rn", "next?")
    assert reveal.outcome == "missed" and reveal.run_id == "rc"
    assert {"canary_failed", "supervisor_notified"} <= {k for k, *_ in log}

def test_flag_from_other_session_leaks_nothing(cc, log):
    plant(cc, "s", "rc")
    assert cc.feedback("other", "rc", "x") is None
    assert cc.start("s", "rn", "q").outcome == "missed"

def test_no_session_never_canary(cc):
    for i in range(5): ask(cc, None, f"r{i}")
    assert not any(planted(cc, f"r{i}") for i in range(5))

def test_failed_run_keeps_session_due(cc):
    for i in range(3): ask(cc, "s", f"r{i}")
    cc.start("s", "r3", "q")  # no answer event: run ended in error
    ask(cc, "s", "r4")
    assert planted(cc, "r4")
```

`ask`, `plant`, `planted` are small helpers in the test file.

- [ ] **Step 2: Run, expect FAIL** — `PYTHONPATH=. uv run pytest tests/api/test_chat_canary.py -v`
- [ ] **Step 3: Implement `ChatCanary`**
- [ ] **Step 4: Run, expect PASS**
- [ ] **Step 5: Commit** — `feat(api): chat canary session state, caught and missed outcomes`

---

### Task 4: Wire into the API

**Files:**
- Modify: `api/main.py` (`create_app`, `create_run`, `admin_reset`, two new routes)
- Modify: `.env.example` (`RAI_CHAT_CANARY_STREAK=3`)
- Test: `tests/api/test_api.py`

**Interfaces:**
- Consumes: `ChatCanary` (Task 3), models (Task 1).
- Produces:
  - `POST /api/runs`, extra header `X-Chat-Session`, response `CreateRunResponse` with `reveal`.
  - `POST /api/runs/{run_id}/feedback`, body `Feedback`, header `X-Chat-Session` → `FeedbackResponse`; 404 unknown run.
  - `POST /api/runs/{run_id}/opened`, body `SourceOpened` → 204; 404 unknown run.
  - `create_app(..., chat_streak: int | None = None)`, default from env `RAI_CHAT_CANARY_STREAK`, `"3"`.

Wiring: `chat = ChatCanary(lambda: store, lambda k, d, p=None: guard.log(k, d, p), streak=...)` (lambdas, because `load_state()` rebuilds `store` and `guard`). In `create_run`, call `chat.start(...)` **after** the invite/size/concurrency/rate-limit checks, and pass `emit=chat.emit(run_id, lr.add)` to the runner. `admin_reset` calls `chat.reset()`.

- [ ] **Step 1: Write the failing tests** (existing `app` fixture with `stub_delay=0.0`, `chat_streak=1`; the stub runner replays `run_demo.jsonl` on `mini_graph.trig`; add the second Supplier via `app.state.store.add_node(...)`; helper `live(client, session)` posts and drains the stream)

```python
async def test_chat_canary_end_to_end(client, app):
    first = await live(client, "s1")                     # blind answer
    second = await live(client, "s1")                    # due -> canary
    answer = next(e for e in second.events if e["type"] == "answer")["payload"]
    assert "Sensorik Nord GmbH" in answer["text"] and answer["canary"] is None
    assert [e["type"] for e in second.events] == [e["type"] for e in first.events]
    third = await client.post("/api/runs", json={"question": "q"},
                              headers={"X-Invite-Code": "pitch-2026", "X-Chat-Session": "s1"})
    assert third.json()["reveal"]["outcome"] == "missed"

async def test_feedback_and_opened_endpoints(client):
    rid = (await live(client, "s1")).run_id
    assert (await client.post(f"/api/runs/{rid}/opened", json={"target": "evidence"})).status_code == 204
    r = await client.post(f"/api/runs/{rid}/feedback", json={"text": "hm"}, headers={"X-Chat-Session": "s1"})
    assert r.json() == {"reveal": None}
    assert (await client.post("/api/runs/nope/feedback", json={})).status_code == 404
    assert (await client.post("/api/runs/nope/opened", json={"target": "x"})).status_code == 404
    assert (await client.post(f"/api/runs/{rid}/feedback", json={"text": "x" * 2001})).status_code == 422
    assert any(e["kind"] == "feedback" for e in (await client.get("/api/audit")).json())
```

- [ ] **Step 2: Run, expect FAIL** — `PYTHONPATH=. uv run pytest tests/api -v`
- [ ] **Step 3: Implement the wiring and routes**
- [ ] **Step 4: Full suite** — `PYTHONPATH=. uv run pytest -q`. Expected: all green, recorded runs unchanged (`git diff --stat runs/` empty).
- [ ] **Step 5: Commit** — `feat(api): live chat canary endpoints (feedback, opened, reveal on next question)`

---

### Task 5: `data.ts` and the UI handoff

**Files:**
- Modify: `web/src/data.ts`
- Modify: `web/FRONTEND.md` (new section "Chat canary")

**Interfaces:**
- Consumes: endpoints from Task 4, generated types.
- Produces on `DataSource`:
  - `startRun(question: string, invite?: string): Promise<CreateRunResponse>`
  - `feedback(runId: string, text?: string): Promise<FeedbackResponse>`
  - `opened(runId: string, target: string): Promise<void>`

Session id: `crypto.randomUUID()`, kept in `sessionStorage` under `ga-chat-session` (read/write in try/catch, fall back to an in-memory id). Sent as `X-Chat-Session` on all three calls. Static mode: `feedback` resolves `{ reveal: null }` and writes `localAudit` `"feedback"`, `opened` resolves. The existing click mock in `App.tsx` stays untouched.

FRONTEND.md section (for the UI team; exact wording is theirs): flag action + optional text per assistant message → `feedback`; show `reveal` (`caught`: quiet toast + false/true; `missed` from `startRun`: show before the new run, link to `reveal.run_id`); call `opened` whenever a citation, passage or the evidence graph is shown; never hint which answer is a canary.

- [ ] **Step 1: Implement**
- [ ] **Step 2: Verify** — `cd web && npm run build`. Expected: build succeeds (the UI branch `chore/hackathon` calls `startRun(q, invite)` and destructures `run_id`, which still works).
- [ ] **Step 3: Commit** — `feat(web): data.ts chat canary calls, FRONTEND.md handoff`

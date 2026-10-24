# Graph Anchor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement your stream task by task. Steps use checkbox (`- [ ]`) syntax for tracking. You own exactly one stream (A, B, C or D). Never edit `contracts/`; if a contract is wrong, stop and tell the user (the coordinator changes it).

**Goal:** A 3-minute-pitch-ready web app that shows how a human-curated enterprise knowledge graph (iMAKS plant + fictional company + linked documents) grounds LLM answers. It shows a per-question traversal strategy, an LLM verdict on every step, and the evidence subgraph that led to the answer. It also shows a vector-RAG contrast and a curation mock.

**Architecture:** Contract-first. `contracts/` (Pydantic models, ID function, GraphStore protocol plus an rdflib implementation, fixtures) is frozen before the streams start. Stream A produces `data/graph/*` and the curation proposals. Stream B produces run JSONL files through `engine`. Stream D serves graph, runs and proposals over FastAPI and deploys. Stream C is a React/Vite UI that works from static fixture JSON first and from the API later.

**Tech Stack:** Python 3.12, uv, pydantic 2, rdflib 7, litellm (OpenRouter), fastembed (local embeddings), FastAPI + uvicorn + sse-starlette; React 18 + Vite + TypeScript, Cytoscape.js; Docker.

**Spec:** `docs/superpowers/specs/2026-10-24-graph-anchor-design.md`. Read it first. It holds the why, the pitch flow, the anti-goals and the BA reuse pointers.

## Global Constraints

- UI and all user-visible copy are in English. Apple-like look: load the `apple-design` skill before writing UI (stream C).
- Anything not produced by the real engine or real data is visibly labelled `mock` (or `illustrative` for the RAG contrast).
- The engine traverses **only** `urn:g:approved`.
- The pitch must work offline: `web` builds to static files that replay `runs/*.jsonl` without the API.
- Edge IDs come only from `contracts.ids.edge_id`. Citations join by ID, never by text.
- Secrets live only in `.env` (gitignored): `OPENROUTER_API_KEY`, `RAI_MODEL` (default `openrouter/google/gemma-4-31b-it`; switch to an IBM Granite model on OpenRouter if one is listed).
- Hosting: `https://rai-hackathon.bbger.at`; repo on Hetzner at `/data/projects/ibm-rai-hackathon`.
- Do not touch other services on the Hetzner node. Caddy/NPM changes only after the user approves.
- Deadline: 15:30 feature freeze, pitch at 16:00.

## Review Focus

- A question that leads to no seeds, or to seeds with no approved neighbours: the run must finish with an `answer` that says "not enough evidence in the approved graph" plus an empty `evidence`. It must not crash or hallucinate (B: `test_no_seeds_answers_insufficient`).
- The LLM returns malformed JSON in the strategy or step step: retry once, then fall back (strategy: all predicates, depth 3; step: prune all, sufficient=true). The run still finishes (B: `test_malformed_llm_json_falls_back`).
- The LLM chooses `allowed_predicates` that are not in the ontology: drop the unknown ones and keep the rest (B: `test_unknown_predicates_dropped`).
- A citation naming an edge ID that is not in the walked set: drop it from `answer.citations` and from `evidence` (B: `test_foreign_citation_dropped`).
- The live run stream disconnects mid-run: the UI shows the events so far plus a "connection lost" state, and replay of stored runs still works (C: manual check).

---

## Phase 0: Contracts (coordinator, before streams start)

### Task 0: Repo skeleton and contracts

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.env.example`, `README.md`
- Create: `contracts/__init__.py`, `contracts/models.py`, `contracts/ids.py`, `contracts/store.py`, `contracts/rdf_store.py`
- Create: `data/graph/ontology.ttl`
- Create: `scripts/make_fixtures.py`, `scripts/export_schema.py`
- Create: `contracts/fixtures/mini_graph.trig`, `contracts/fixtures/run_demo.jsonl`, `contracts/fixtures/proposals.json`, `contracts/fixtures/graph_export.json`, `contracts/schema/*.json`
- Test: `tests/test_contracts.py`

**Produces:** all shapes in the spec section "Interfaces (contracts)". The authoritative definitions are the files themselves. Read `contracts/models.py` and `contracts/store.py` before starting any stream.

- [x] Write the contract files and fixtures (`uv run python -m scripts.make_fixtures`, `uv run python -m scripts.export_schema`).
- [x] `uv run pytest tests/test_contracts.py -q` → all pass.
- [ ] Commit `feat(contracts): freeze interfaces and fixtures`.

---

## Stream A: Knowledge graph (`rai-A-kg`)

Owns `kg/`, `data/graph/kg.trig`, `data/graph/provenance.jsonl`, `data/proposals.json`, `data/docs/`. Raw iMAKS goes to `data/raw/imaks/` (gitignored; downloaded with `kg/download.py` from `https://zenodo.org/records/20075430/files/iMAKS_dataset.zip?download=1`).

**Interfaces:**
- Consumes: `contracts.ids.edge_id`, `contracts.ids.node_iri(cls, local_id)`, ontology `data/graph/ontology.ttl`, `contracts.models.Provenance`, `contracts.models.Proposal`.
- Produces: `data/graph/kg.trig` loadable by `contracts.rdf_store.RdfGraphStore("data/graph/kg.trig")`; `data/proposals.json` = `list[Proposal]`; CLI `uv run python -m kg.build` rebuilds everything.

### Task A1: Layer 1, iMAKS CSV → RDF
- [ ] Test `tests/kg/test_layer1.py::test_counts`: after build, the approved graph has 115 iMAKS nodes (`System`, `Zone`, `Component`→`Station`, `Sensor`, `Person`, `AnomalyEvent`, `SafetyEvent`, `Maintenance`) and 319 edges: the 341 rows of `edges.csv` minus the 22 `Component monitors Sensor` reverse duplicates (canonical direction is `Sensor monitors Station`). Edge `type` maps 1:1 to `ont:<type>`.
- [ ] Implement `kg/layer1_imaks.py::build(raw_dir: Path) -> rdflib.Dataset`. Local IDs: `name` for System/Zone/Station/Sensor (e.g. `kg:station/ST02_SEALING`, `kg:sensor/ST02_SEALING_TMP`, `kg:system/iMAKS`, exactly as in `contracts/fixtures/mini_graph.trig`), `personId`/`eventId` (or `nodeId` as fallback) for the rest. Non-empty CSV columns become `ont:<column>` literals. `name` → `rdfs:label`, `description` → `rdfs:comment`. Every edge gets a `Provenance(source="imaks:edges.csv#<row>", creator="script", status="approved")`.
- [ ] Commit.

### Task A2: Layer 2, documents and chunks
- [ ] Test `test_layer2.py::test_sop_chunks_link_stations`: SOP-003 yields chunks; the chunk containing `MAINT-01` has `ont:mentions kg:station/ST04_PACKAGING`; `RULE-ST02-01` is `ont:defined_in` a chunk of `kg:document/SOP-001`.
- [ ] Implement `kg/layer2_docs.py::build(raw_dir, ds)`. PDF text via `pypdf`. One chunk per numbered section, and per table row where a row ID (`MAINT-xx`, `RULE-...`, parameter row) is present. Chunk IRIs `kg:chunk/<DOC-ID>-s<n>`. Mentions come only from exact ID matches against existing node local IDs and sensor type codes. Rules from `ground_truth.csv` become `Rule` nodes with `ont:applies_to` station and sensor.
- [ ] Commit.

### Task A3: Layer 3, fictional company overlay
- [ ] Write `data/company.yaml` (~40 nodes): company **Kelvara Packaging GmbH** (fictional), plant = the iMAKS system node, 2 customers, 3 suppliers (incl. **ThermoSense GmbH**, the vendor of datasheet DS-THERM-2200), sensor models (`TMP-2210`, `HUM-2250`, … from the datasheets) with `ont:of_model` from each iMAKS sensor by type code, production orders `PO-1001…PO-1006` with `ont:executed_at` stations and `ont:ordered_by` customers, roles for iMAKS persons, and 2 short company documents in `data/docs/*.md` (supplier quality agreement with ThermoSense; maintenance contract), chunked like layer 2.
- [ ] Test `test_layer3.py::test_supplier_path`: a path exists `PO-1003 → executed_at → ST02_SEALING ← monitors … sensor → of_model → TMP-2210 → supplied_by → ThermoSense GmbH`. The exact predicate directions follow the ontology.
- [ ] Commit.

### Task A4: Layer 4, LLM proposals (curation)
- [ ] Implement `kg/propose.py::propose(store, chunks: list[Node], model: str) -> list[Proposal]`. The LLM reads chunk pairs (SOP chunk × datasheet chunk sharing a sensor type) and proposes `contradicts` / `governs` / `mentions` edges with quote, rationale and confidence. Output goes to `urn:g:proposed` and `data/proposals.json`.
- [ ] It must find at least `SOP-001 (ST02 TMP critHi 210 °C) contradicts DS-THERM-2200 (200 °C continuous)`. If the LLM misses it, add it by hand with `proposed_by="analyst-seed"`. Keep 3–5 proposals total.
- [ ] Commit, then run `uv run python -m kg.build` and commit `data/graph/*`.

---

## Stream B: Engine (`rai-B-engine`)

Owns `engine/`, `runs/`, `tests/engine/`. Port ideas and prompts from `/data/projects/ba/ba_evaluation/experiments/06_kg_hybrid`, `07_kg_subagent_traversal`, `12_kg_hybrid_lexical` and `ba_evaluation/prompts/` (read only; copy, never import).

**Interfaces:**
- Consumes: `contracts.store.GraphStore`; develop against `RdfGraphStore("contracts/fixtures/mini_graph.trig")` and switch to `data/graph/kg.trig` when stream A lands. Event models in `contracts.models`.
- Produces: `engine.run.run_question(question: str, store: GraphStore, *, model: str, mode: Literal["replay","live"], emit: Callable[[Event], None]) -> None`; CLI `uv run python -m engine.run "<question>" --out runs/<run_id>.jsonl`. Every event is a `contracts.models.Event`, `seq` starts at 0, order: `run.started`, `strategy`, `seeds`, `step`×n, `answer`, `evidence`, `baseline`, `run.finished`.

### Task B1: LLM helper and strategy
- [ ] `engine/llm.py::complete_json(messages, model, schema: type[BaseModel]) -> BaseModel` via `litellm.completion`, JSON mode, one retry, raises `LLMFormatError`.
- [ ] `engine/strategy.py::plan(question, predicates: list[tuple[str,str]], model) -> StrategyPayload`. Tests: `test_unknown_predicates_dropped`, `test_malformed_llm_json_falls_back` (monkeypatch `complete_json`).
- [ ] Commit.

### Task B2: Seeds and stepwise traversal
- [ ] `engine/traverse.py::walk(question, store, strategy, seeds, model, emit) -> Walk`. Each step: frontier = approved neighbours of the current nodes, restricted to `allowed_predicates`, minus edges already seen. The LLM returns a verdict per edge plus `sufficient`. Stop when sufficient, the frontier is empty or `max_depth` is reached. Cap the frontier at 25 edges per step; above that, pre-rank by fastembed similarity to the question.
- [ ] `Walk` holds the walked edge IDs, all nodes and all edges (explored).
- [ ] Test `test_walk_on_fixture` (stub LLM follows everything): it reaches `kg:supplier/ThermoSense` from the seed `kg:station/ST02_SEALING` within 3 steps on the mini graph.
- [ ] Commit.

### Task B3: Answer, evidence, baseline, run writer
- [ ] `engine/answer.py::answer(question, walk, store, model) -> AnswerPayload`. Triples are serialised as `[edge_id] s — p — o` plus chunk texts. The LLM must cite edge and chunk IDs and report contradictions.
- [ ] `engine/evidence.py::evidence(walk, answer) -> EvidencePayload`: the cited edges plus the walked edges on the shortest path from a seed to each cited edge's endpoints; the nodes are their endpoints. Tests: `test_foreign_citation_dropped`, `test_no_seeds_answers_insufficient`.
- [ ] `engine/baseline.py::rag(question, store, k=3) -> BaselinePayload`: fastembed (`BAAI/bge-small-en-v1.5`) over all `Chunk` texts, top-k=3, same model answers from the chunks only. `illustrative=False`.
- [ ] `engine/run.py` wires it all up. Generate the demo runs for the 3 questions in `runs/questions.yaml` (pick them with the user; one must cross company → plant → document, one must hit the SOP/datasheet contradiction). Validate with `tests/test_contracts.py::test_runs_validate`.
- [ ] Commit `runs/*.jsonl`.

---

## Stream C: UI (`rai-C-ui`), starts first

Owns `web/`. Load the `apple-design` skill first, then `artifact-design`/frontend-design guidance if available. The base may be ported from `/data/projects/ba/ba_kgqa-ui/webui` (graph animation and event handling); if that takes more than 45 minutes, start fresh with Vite + React + TS + Cytoscape.js.

**Interfaces:**
- Consumes: TS types generated from `contracts/schema/*.json` into `web/src/contracts.ts` (`npx json-schema-to-typescript`). Data source abstraction `web/src/data.ts`:
  - `getGraph(): Promise<GraphExport>`
  - `listRuns(): Promise<RunSummary[]>`
  - `getRun(id): Promise<Event[]>`
  - `startRun(question): Promise<{run_id}>` + `streamRun(id, onEvent)` (SSE)
  - `listProposals(): Promise<Proposal[]>`
  - `decide(id, decision): Promise<Proposal>`

  Two implementations, selected by `VITE_DATA=static|api`. `static` reads `public/data/graph_export.json`, `public/data/runs/*.jsonl` and `public/data/proposals.json` (copied from `contracts/fixtures/` now and from real outputs later), and decisions stay in memory.
- Produces: `npm run build` → `web/dist/` (static, works offline with `VITE_DATA=static`).

### Task C1: Shell and twin view
- [ ] A full-screen graph of `GraphExport` with class-based soft colours, calm layout (fcose or concentric by layer), labels on hover/zoom, and a search-free minimal chrome. Proposed edges dashed, rejected hidden.

### Task C2: Run player (the pitch core)
- [ ] Question picker (demo runs) plus a free-text input (live; disabled in static mode).
- [ ] Playback with play/pause and step. `strategy` appears as a card (question type + allowed-predicate chips); `seeds` pulse; each `step` animates the frontier and shows follow/prune verdicts with reasons; `answer` card with citations clickable to the graph; **`evidence` is drawn as the highlighted result graph, everything else explored is dimmed**; contradictions shown as a distinct badge.
- [ ] A `mock` run shows a small persistent "mock" tag.

### Task C3: Contrast and curation
- [ ] Contrast view: graph answer and evidence vs `baseline` chunks and answer, side by side; `illustrative` label when set.
- [ ] Curation view: the proposal list with quote, rationale and confidence; approve/reject animates the edge from dashed to solid (or removes it).
- [ ] Commit; `npm run build` works with `VITE_DATA=static`.

---

## Stream D: API and deploy (`rai-D-api`)

Owns `api/`, `deploy/`, `tests/api/`.

**Interfaces:**
- Consumes: `contracts.models` (all), `RdfGraphStore`, `engine.run.run_question` (stub it until stream B lands: replay `contracts/fixtures/run_demo.jsonl` with 400 ms delays and new IDs).
- Produces: the C4 endpoints exactly as in the spec, plus `GET /healthz`. Static files from `web/dist` are served at `/`. Runs are stored in `runs/<run_id>.jsonl`. Proposal decisions are written to `data/proposals.json` and move the triple between named graphs in memory.

### Task D1: API
- [ ] Tests with `httpx.AsyncClient`: `test_graph_export_validates`, `test_list_and_get_runs`, `test_live_run_streams_events_in_order`, `test_decide_moves_edge_to_approved`.
- [ ] `api/main.py` FastAPI app. SSE via `sse-starlette`, one event = one JSON-serialised `Event`.
- [ ] Commit.

### Task D2: Deploy
- [ ] `deploy/Dockerfile` (multi-stage: node build of `web/` → python slim with uv) and `deploy/compose.yml` (port `127.0.0.1:17080:8000`, `.env`, volume for `runs/` and `data/`).
- [ ] Prepare a Caddy/NPM route for `rai-hackathon.bbger.at` → `localhost:17080` and **ask the user before applying it**. Check how other `*.bbger.at` hosts are routed in `/data/projects/caddy/Caddyfile` and NPM.
- [ ] Verify `curl -s https://rai-hackathon.bbger.at/healthz` → `{"ok":true}`.

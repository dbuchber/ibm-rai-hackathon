# Graph Anchor: Design

IBM Responsible AI Hackathon (WU & UNIVIE), 24.10.2026. Build window 10:30 to 16:00, pitch 3 minutes.

## Intent and why

LLM assistants in companies answer from text chunks that are *semantically similar* to the question. They ignore how knowledge items *relate*. In industry this matters: two SOPs can both mention "conveyor", but only one is linked to the station that actually failed. A datasheet and an SOP can contradict each other.

The idea carries over the bachelor thesis ("Reducing Hallucinations in LLM-Based QA through Hybrid Multi-Agent KG Traversal", proposal in `~/Desktop/tmp.nosync/vscode/BA_Thesis_Proposal/MyMaintext.tex`) to an enterprise setting:

- A **human-curated knowledge graph is the central grounding anchor** of an enterprise digital twin. LLMs only *propose* entities and edges. Analysts approve them. Hallucination risk therefore stays out of the graph substrate. This is the thesis' "curated source instead of LLM extraction" argument, with Wikidata replaced by analyst review.
- Agents and chatbots **traverse** the graph to build their context. The path is recorded, so it is traceable *which knowledge the model was given*. We claim no more than that. We do not claim to know what the model internally used.

Responsible AI angle: reliability (correct source, contradictions surfaced) and transparency (every answer carries its graph path plus document passages).

## What the jury sees (3 minutes)

A **click prototype** with an Apple-like look. The pitch replays **precomputed runs**, so it needs no live LLM calls and does not depend on venue Wi-Fi. A **live mode** on the same UI also answers free-text questions through the real engine. The pitch never depends on it.

1. **The twin.** A calm, full-screen graph of the fictional company. The iMAKS plant sits inside it, with documents attached as nodes.
2. **Ask.** A question is picked from 3 curated example questions. The engine first shows its **traversal strategy**: a short plan plus the *allowed predicates* chosen for this question type.
3. **Traverse.** The run plays step by step. At every hop the LLM's verdict is shown (follow / prune / enough evidence), and the path lights up in the graph.
4. **Answer.** The answer comes with a justification, the cited path (triples) and the linked document passages. Where iMAKS contains an SOP-vs-datasheet contradiction, the answer **flags the contradiction** instead of picking one silently.
5. **Contrast.** The same question goes through plain vector RAG, which retrieves a similar-but-wrong passage. One side-by-side view. The first version is an **illustrative example**, visibly labelled. Afterwards we try candidate questions against the real baseline (fair, top-k=3) until one fails naturally, and that one replaces the illustration.
6. **Curate.** A new document arrives. The LLM proposes 3 to 5 edges, the analyst clicks approve or reject, and the graph updates. This step is mocked and labelled as such.
7. **Roadmap** (last screen, after Curate; pitch only, nothing of it runs today): **local models of different sizes with intelligent routing**. A model ladder from small to large, all runnable on-prem (e.g. Ministral 3B/8B/14B → Gemma/Granite mid-size → Mistral Large). A router assigns each task to the smallest model that is good enough: the many per-step traversal verdicts go to small models, the strategy step and the final answer go to large ones, and contradictions or low confidence escalate. This gives sovereignty (company data stays in-house), cost and latency control, and through LiteLLM a config-only switch to IBM watsonx/Granite. Further roadmap items on the same screen: **guardrails** on input and output (e.g. IBM Granite Guardian: prompt injection, PII, ungrounded claims); **feedback in the chat window** (thumbs, corrections) that flows back into the curation queue as proposals; **forward navigation** from an answer citation → the document chunk → a deep link into the source system (DMS, ERP, SharePoint); **RBAC on two levels**: on vector level via payload filters on chunks, and on node level in the KG (per-node/per-graph ACL, traversal and seed search only over nodes the user may see). The screen is labelled "roadmap".

## Goals

- Real data: iMAKS (Zenodo record 20075430, `iMAKS_dataset.zip`, 20 MB). It ships a structured graph in `kg_seed/`: `nodes.csv` (115 nodes: system, zones, stations, sensors, persons, rules, events), `edges.csv` (341 edges: `authorized_for`, `monitors`, `triggers`, `contains`, `resolves`, `detected_in`, `part_of`, `feeds_into`, …) and `ground_truth.csv` (86 rules, each with station, sensor, thresholds and the source SOP). It also contains 4 SOP PDFs, 3 datasheet PDFs, sensor time series and human/access logs. The kg_seed graph plus the rule→SOP links count as the **analyst-approved base graph**, so no LLM extraction is needed to build it.
- A fictional company wraps around it: suppliers, materials, production orders, employees/roles, and the documents linked to entities. Names are invented and the data is synthetic.
- A real traversal engine (thesis concept, adapted):
  1. **Strategy step:** the LLM classifies the question and fixes a traversal strategy, made of a system prompt fragment plus a whitelist of predicates it may follow, and optionally a max depth.
  2. **Seeds:** entry nodes found via embedding similarity over node labels/descriptions. Optionally the question is decomposed into parts first, as in the thesis.
  3. **Stepwise evaluation:** at **every** step, the LLM sees the current subgraph plus the candidate edges (restricted to allowed predicates) and decides which to follow, which to prune, and whether the evidence is sufficient.
  4. **Answer:** a paired output (answer + short justification) that cites triples and document chunks. This mirrors the thesis' dual output for faithfulness.
- Vector-RAG baseline over the same document chunks, used only for the contrast screen.
- A precompute script runs the engine for the demo questions and stores the full run traces as JSON. The UI replays them.
- Live mode: a FastAPI endpoint runs the engine on a free-text question and streams the same event format the replay uses, so one UI serves both.
- Deployed at `https://rai-hackathon.bbger.at` on the Hetzner node (`hetzner-wikidata`, host `wikidata-kg`). The repo will later live under `/data/projects/` there; heavier computation such as embeddings and batch runs can happen on the server. Public entry point: Caddy (`/data/projects/caddy/Caddyfile`), routing `*.bbger.at` via NPM.

## Reuse from the bachelor thesis

The thesis code lives on the Hetzner node under `/data/projects/ba/` (map: `/data/projects/ba/CLAUDE.md`). Reuse as much as possible by **porting**, not by importing. The BA arms are bound to Wikidata (QIDs/PIDs, Fuseki, Qdrant), and the hackathon repo must stay standalone.

- `ba_evaluation/experiments/06_kg_hybrid`, `07_kg_subagent_traversal`, `12_kg_hybrid_lexical`: seed finding, `hybrid_traverse`, `frontier_candidates`, `relevance_check`, `score_subgraphs`, and the prompts in `ba_evaluation/prompts/`. Port the traversal loop and the prompts to the enterprise RDF graph. Add the new **strategy step** (allowed predicates) and **per-step LLM evaluation** on top.
- `ba_kgqa-ui`: a FastAPI + React/Vite chat whose grounding is the KG. It shows the graph building up during traversal, driven by an event stream (`app/events.py`, `app/graph_events.py`, `app/runner.py`, runs stored as `runs/<id>.jsonl` and replayed). Use its event model and graph-animation front end as the base. **Restyle Apple-like** with the `apple-design` skill, replacing the WU Clarendon/Montserrat look. Drop Keycloak, Langfuse links and the arm/parameter panel.
- `ba_main/ba_sparql-mcp` (local): tool-style graph functions, if useful.
- Models: OpenRouter through LiteLLM, as in the BA (`ba_evaluation/src/models.csv`). Prefer an **IBM Granite** model on OpenRouter if one is available, to suit the IBM jury; otherwise use an open-weight row from the BA set (e.g. gemma-4-31b, qwen3.6-35b). The key and gateway setup is checked on the server at build time.

## Evidence graph (required)

Every answer shows **the graph that led to the result**: the *evidence subgraph*. It contains only the nodes and edges the answer cites, plus the walked path that connects them to the seeds. It is drawn visibly distinct from the merely *explored* graph (everything the traversal looked at), which is shown dimmed. The evidence subgraph is part of the run contract below, so it is never reconstructed afterwards in the UI.

## Knowledge graph construction

Four layers. Only layer 4 uses an LLM, and its output is never used for answers until an analyst approves it.

| Layer | Source | How | Status |
|---|---|---|---|
| 1 | iMAKS `kg_seed/nodes.csv`, `edges.csv` | Deterministic CSV → RDF script | approved |
| 2 | iMAKS SOP + datasheet PDFs, `ground_truth.csv` | PDF → `Document` + `Chunk` nodes (one per section/table row). `Chunk mentions Station/Sensor` by exact ID match (e.g. `ST04_PACKAGING`). `Rule definedIn Chunk` via the SOP named in `ground_truth.csv` | approved |
| 3 | Fictional company overlay (hand-written YAML, ~40 nodes) | Company, plant (= iMAKS system), customers, suppliers (incl. *ThermoSense GmbH* from the datasheet) → sensor models → sensors, production orders → stations, roles → iMAKS persons, 2–3 short company documents | approved |
| 4 | LLM reading chunks | Proposes edges that the ID match cannot find, each with a quote and a rationale. Example from iMAKS: SOP-001 allows 210 °C critical at `ST02_SEALING`; the TMP-2210 datasheet rates 200 °C continuous → `SOP-001 contradicts DS-THERM-2200` | proposed → analyst approves or rejects |

Every triple carries provenance: source (file + row/page), creator (`script` / `analyst` / `llm:<model>`) and status. The engine traverses **only the approved graph**.

## Interfaces (contracts), so work can run in parallel

Method: **contract-first.** The first commit, before any parallel work starts, is `contracts/`:

- `contracts/models.py`: Pydantic models, the single source of truth for every shape below.
- `contracts/schema/*.json`: JSON Schema exported from the models. TypeScript types for the UI are generated from it (`json-schema-to-typescript`), so nobody hand-types them.
- `contracts/fixtures/`: `mini_graph.trig` (~12 nodes covering every class and named graph), `run_demo.jsonl` (one complete run, including a `mock` flag), `proposals.json`.
- `tests/test_contracts.py`: validates the fixtures and every producer's real output against the models.

Each workstream builds against the fixtures, never against another stream's unfinished code. Changing a contract means changing `contracts/` first, regenerating the schemas and types, and telling the other streams.

### C1: Graph files (KG → engine, KG → API)

- One TriG file `data/graph/kg.trig` with three named graphs: `urn:g:approved`, `urn:g:proposed`, `urn:g:rejected`.
- Namespaces: `kg: <https://rai-hackathon.bbger.at/kg/>` (instances), `ont: <https://rai-hackathon.bbger.at/ont#>` (classes, predicates, defined in `data/graph/ontology.ttl`).
- Node IRIs: `kg:{class-lowercase}/{localId}`, e.g. `kg:station/ST02_SEALING`, `kg:sensor/ST02_SEALING_TMP`, `kg:document/SOP-001`, `kg:chunk/SOP-001-s3`.
- Every node has `rdf:type`, `rdfs:label`, optionally `rdfs:comment`. Chunks also have `ont:text` and `ont:page`.
- The class and predicate lists are fixed in `ontology.ttl`. A new predicate is a contract change.
- Edge ID: `sha1("{s}|{p}|{o}")[:12]`. One function in `contracts/ids.py`, used everywhere, so citations join by ID and never by rendered text.
- Provenance: `data/graph/provenance.jsonl`, one line per edge ID: `{edge_id, source, creator, status, created_at}`.

### C2: GraphStore Python API (implemented by KG, used by engine)

```python
class Node(BaseModel):   id: str; cls: str; label: str; description: str | None; text: str | None
class Edge(BaseModel):   id: str; s: str; p: str; o: str; graph: Literal["approved","proposed","rejected"]

class GraphStore(Protocol):
    def node(self, id: str) -> Node
    def search(self, text: str, k: int = 5) -> list[tuple[Node, float]]          # seeds
    def neighbors(self, id: str, predicates: set[str] | None = None) -> list[Edge]  # approved only, both directions
    def predicates(self) -> list[tuple[str, str]]                                  # (iri, description)
    def export(self, graphs: set[str]) -> GraphExport                              # nodes + edges for the UI
```

A `FixtureGraphStore` over `mini_graph.trig` ships with the contracts, so the engine can be built before the real KG exists.

### C3: Run events (engine → API → UI; identical for replay and live)

A run is a JSONL file of events: `{run_id, seq, ts, type, payload}`. Node and edge objects are embedded in full, so the UI never needs graph lookups to draw a run.

| `type` | `payload` |
|---|---|
| `run.started` | `question, model, mode: replay\|live, mock: bool` |
| `strategy` | `question_type, rationale, allowed_predicates: [iri], max_depth, prompt` |
| `seeds` | `nodes: [Node + score]` |
| `step` | `n, frontier: [Edge], decisions: [{edge_id, verdict: follow\|prune, reason}], sufficient: bool` |
| `answer` | `text, justification, citations: [{edge_id \| chunk_id}], contradictions: [{a, b, note}]` |
| `evidence` | `nodes: [Node], edges: [Edge]`: **the graph that led to the result** (see above) |
| `baseline` | `chunks: [Node + score], answer, illustrative: bool` |
| `run.finished` | `status: ok\|error, error?` |

### C4: HTTP API (API → UI)

| Method and path | Returns |
|---|---|
| `GET /api/graph` | `GraphExport` (approved + proposed, with status) |
| `GET /api/runs` | demo runs: `[{run_id, question, mock}]` |
| `GET /api/runs/{id}` | all events of a stored run |
| `POST /api/runs` `{question}` | `{run_id}`, live mode |
| `GET /api/runs/{id}/stream` | Server-Sent Events, one C3 event each |
| `GET /api/proposals` | `[Proposal]` (may contain one canary, see Canaries) |
| `GET /api/audit` | `[AuditEntry]` |
| `POST /api/proposals` `CreateProposal` | new `Proposal` (`proposed_by="user"`, `status=proposed`) |
| `POST /api/proposals/{id}` `{decision: approve\|reject\|flag}` | updated `Proposal`. Approving an edge moves it to `urn:g:approved`, a node adds it to the approved graph, a predicate makes it available to strategy and curation |

### C5: Proposal (curation)

Three kinds, listed together in the curation screen: **edge** (`triple`), **node** (`node: {cls, local_id, label, description}`), **predicate** (`predicate: {name, description, domain, range}`). Common fields: `{id, kind, rationale, evidence_chunk_id?, quote?, confidence?, proposed_by: llm:<model>|analyst-seed|user, status}`. Users can add their own proposals of any kind in the curation screen (`CreateProposal`); they go through the same approve/reject step. IDs: `contracts.ids.proposal_id`.

### Workstreams

| Stream | Builds | Against |
|---|---|---|
| A: KG | layers 1–4, `GraphStore` implementation, `kg.trig` | C1, C2, C5 |
| B: Engine | strategy, seeds, stepwise traversal, answer, evidence, baseline, run writer | C2 (fixture store), C3 |
| C: UI | twin view, replay player, evidence graph, contrast, curation mock | C3 + C4 via fixtures (static JSON first) |
| D: API + deploy | FastAPI over C4, Docker, Caddy/NPM route | C3, C4, C5 |

Build order is UI first, so stream C starts immediately on the fixtures.

## Canaries against automation bias

People who approve many proposals or accept many answers in a row stop checking (automation bias, EU AI Act Art. 14). Canaries are planted, **obviously false** items. Missing one raises an alarm. Canaries are never written to the graph.

**Curation (real, streams D + C):**
- The server tracks consecutive approvals (single demo user, in memory). After `RAI_CANARY_STREAK` (default 4) approvals in a row, or once the average decision time drops below 3 s, the next `GET /api/proposals` contains one canary among the first three items. Canaries look like normal proposals (e.g. `ST02_SEALING supplied_by Velora Foods AG`, a station "supplied" by a customer, with a plausible rationale and quote). Generate them from the approved graph by swapping an endpoint to a node of an implausible class, or use a small hand-written pool. Whether an item is a canary is stored server-side only and never sent before the decision.
- `reject` or the new `flag` decision on a canary = **passed**: a quiet toast "Good catch, that was a test proposal" plus an audit entry.
- `approve` on a canary = **failed**: the canary is not written. The response carries `alert: CanaryAlert`. Every approval since the last passed canary goes back to `proposed` (removed from `urn:g:approved`). A supervisor notification is recorded ("Quality lead (mock)"). The UI shows a calm but unmistakable alert with the reverted items, and an audit log drawer.
- New endpoint `GET /api/audit` → `[AuditEntry]`. Static mode implements the same logic in the browser.

**Chat (click mock, stream C):** fixture run `contracts/fixtures/run_canary_chat.jsonl`, where `answer.canary` holds the false claim and the truth. The answer card has a "Report" action. If the user reports, it shows "Good catch". If the user moves on (next question or screen) without reporting, the alert appears: user notice, audit entry, supervisor notified (mock). The run is labelled `mock`.

**Pitch:** in the curation screen, approve quickly 4 times, then approve the canary → alert → reverted items. This is the Responsible AI moment for human oversight.

## Non-goals (today)

- Tracing/logging (Langfuse, MLflow): explicitly out.
- Parallel sub-agents and the parameter study from the thesis. One traversal agent with per-step evaluation is enough. The parallel version is mentioned in the pitch as the thesis' next step.
- A real curation backend, persistence, auth.
- A quantitative evaluation over many questions. Accuracy/faithfulness may appear as "how we would measure it" in the pitch only.
- watsonx/Granite: no credentials, and Granite is not in the BA gateway. Today's runs use `gemma-4-31b-it-openrouter`. **Granite appears only on the roadmap** (pitch + README): because everything goes through LiteLLM, switching to watsonx/Granite is a config change.

## Anti-goals (failure even if it works)

- A pitch that needs a live LLM call or the venue network to succeed.
- Claiming the system knows what the model "thought". We only show what context it was given.
- Mocked parts that are not visibly labelled as mock.
- A visual that looks like a dev dashboard (Streamlit-style). The look must be Apple-like: restraint, whitespace, SF-style typography, soft depth, fluid motion.
- Spending the build window on infrastructure (Blazegraph stack, Docker debugging) instead of the story.

## Constraints

- About 5.5 hours of build time. One coder (the user, assisted by Claude). Teammates do the pitch and business side.
- The event and UI are in English.
- Must run on a laptop offline (replay mode), and on the Hetzner node behind the existing reverse proxy (Caddy → Nginx Proxy Manager for `*.bbger.at`).

## Decided by the user

- Domain: iMAKS merged with a fictional company.
- Traversal: the LLM evaluates every step, and a per-question strategy restricts prompt and predicates.
- Demo: click prototype with precomputed answers, 3-minute pitch, Apple-like optics (use the `apple-design` skill and related design skills).
- Live mode for free-text questions on the hosted site, in addition to replay.
- Curation (LLM proposes, analyst approves): shown minimally.
- No tracing or logging.
- Own repo at `~/Desktop/tmp.nosync/vscode/ibm-rai-hackathon`, hosted at `rai-hackathon.bbger.at`.
- Reuse as much of the bachelor thesis as possible.
- LLM access through OpenRouter (no watsonx credentials).
- Vector-RAG contrast: start with a labelled illustrative example, then pick real questions until the baseline fails naturally.
- **Build order: UI first.** If time runs short, the UI and story must be finished. Run JSONs may then be hand-curated or partly synthetic, but must be labelled `mock` in the UI. Next priority is the real engine, then live mode. The curation screen is a click mock in any case.

## Claude's calls (the user may override)

- Graph format is RDF (Turtle), loaded in-process with `rdflib`. It stays close to the thesis' SPARQL world without needing a triplestore container. Tool-style functions (neighbours, describe node, filtered by predicate) can borrow from `ba_main/ba_sparql-mcp`.
- Python with `uv`, FastAPI backend (as in `ba_kgqa-ui`). Front end: React + Vite, taken from `ba_kgqa-ui/webui` and restyled. If porting it costs more than about 45 minutes, fall back to a fresh Vite app that keeps only its graph and event logic.
- Embeddings via OpenRouter/LiteLLM if an embedding model is reachable; otherwise a small local sentence-transformer. The graph is small (~200 nodes), so the choice is cheap.
- Deployment: a single Docker container on the Hetzner node, plus a Caddy/NPM route for `rai-hackathon.bbger.at`. The API key lives only in the server `.env`.

## Left to the builder

- Exact ontology and namespaces, and how iMAKS nodes map in.
- Which 3 demo questions to use. They must include one that crosses company → plant → document, and one that hits an iMAKS contradiction.
- Chunking of the iMAKS PDFs.
- Front-end structure and animation details, within the anti-goals above.

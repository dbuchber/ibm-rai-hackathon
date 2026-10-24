# Frontend handoff

You own `web/`. The backend owns `api/`, `engine/`, `kg/` and `contracts/`. The two meet in one place: the
**event stream** defined in `contracts/models.py` (JSON Schema in `contracts/schema/`, TypeScript in
`web/src/contracts.ts`).

You need neither Python nor an LLM key to work on the UI.

## Start

```bash
cd web
npm ci
npm run dev            # http://127.0.0.1:5180, offline replay of the recorded runs (VITE_DATA=static)
```

Against the real API (backend running on port 17080): `VITE_DATA=api npm run dev`.

## What to build

**1. Animated demo.** Plays a recorded run. Used on the projector during the pitch (presenter steps through it)
and on the website (plays alone, so the captions must carry the story).

**2. Chat.** Visitors type their own question and watch the same animation run live. Needs an invitation code.

Both draw the same event stream. Build one renderer, put a text field in front of it for the chat.

## The event stream

A run is a list of events, each `{run_id, seq, ts, type, payload}`. `seq` starts at 0 and has no gaps.

```
beat  run.started   the question
beat  strategy      question type, allowed relations, max depth
beat  seeds         entry nodes in the graph
beat  step          one per hop: frontier edges, follow/prune verdict per edge, `sufficient`
...   (more steps)
beat  answer        text, justification, citations, contradictions
beat  evidence      the subgraph the model was given
beat  baseline      plain vector RAG with the same question, for contrast
      run.finished  status ok | error
```

Each content event is introduced by a **`beat`**. A beat carries no new facts. It is the stage direction:

| field | meaning |
|---|---|
| `act` | `question` · `strategy` · `seeds` · `traverse` · `answer` · `evidence` · `contrast` |
| `focus` | node IRIs to frame with the camera. May contain chunk IRIs: map them with `fold().mapId` like any highlight |
| `caption` | one plain sentence for viewers without a presenter |
| `emphasis` | `follow` · `prune` · `enough` · `contradiction` · `canary` · `null`, use it to pick the motion |
| `step` | hop number for `act: traverse` |

Example, from `public/data/runs/demo-contradiction.jsonl`:

```json
{"type": "beat", "payload": {"act": "answer", "emphasis": "contradiction",
  "caption": "Answer, backed by 13 citations. 1 contradiction between sources, shown instead of hidden.",
  "focus": ["https://rai-hackathon.bbger.at/kg/chunk/SOP-003-s1", "..."], "step": null}}
```

Timing is yours. Beats say *what* happens and *where to look*, not how long. `ts` holds wall-clock time and is
useless for pacing replays.

## Data access

Never `fetch` directly. Use `data` from `src/data.ts`:

- `listRuns()`, `getRun(id)`: recorded runs
- `startRun(question, invite)`, then `streamRun(id, onEvent, onLost)`: live run over SSE
- `getGraph()`: the whole graph (nodes, edges), for the backdrop

`startRun` without a valid invite code rejects with `invite code required` (HTTP 403). Show a code field.
Where you keep the code is up to you; it is not a secret worth protecting from the visitor who typed it.

In static mode `startRun` always rejects ("Live mode needs the API"). Use the recorded
`demo-canary-chat` run to design the chat without a backend.

## Chat canary (live chat)

After a visitor trusted three live answers in a row without looking at a source, the server plants **one false
fact** into the next real answer (it swaps one cited detail, e.g. the supplier). The citations still show the
true triple. The visitor is expected to flag the answer. Spec:
`docs/superpowers/specs/2026-10-24-chat-canary-design.md`.

What the chat needs, all through `data` (the session header is added for you):

| UI | call | then |
|---|---|---|
| Flag on every assistant message (thumbs down) + optional text, like ChatGPT/Claude | `feedback(runId, text)` | `reveal == null`: "Thanks, an analyst will review this answer." `reveal.outcome == "caught"`: quiet "Good catch" + false vs. true fact |
| Visitor opens a citation, a passage or the evidence graph | `opened(runId, target)` (edge id, chunk IRI or `"evidence"`), fire and forget | nothing visible |
| Next question | `startRun(question, invite)` returns `{run_id, reveal}` | `reveal?.outcome == "missed"`: show it **before** the new run: "Your last answer contained a deliberately false fact", false vs. true, link to `reveal.run_id` |

Rules:

- Nothing in the stream tells a canary apart from a normal answer. Do not try to, and never hint at it.
- Use the same visual family as the curation canary alert: calm, unmistakable.
- Static mode: `feedback` answers `{reveal: null}`, `opened` does nothing. The recorded `demo-canary-chat` run and
  its click mock in `App.tsx` stay as they are for the pitch.

## Rules

- `src/contracts.ts` is generated (`npm run types`). Never edit it.
- Need another field or event? Open an issue or PR against `contracts/models.py`; the backend adds it and
  regenerates the runs. Do not derive it in the UI from guesses.
- Keep the Responsible-AI parts visible in any redesign: contradiction badge, cited triples and passages,
  "proposed" edges drawn differently from approved ones, the canary in the chat.
- Respect `prefers-reduced-motion`: the demo must still work as a sequence of still frames.

## Existing code worth reusing

| file | does |
|---|---|
| `src/run.ts` | events to frames, graph highlight state per frame |
| `src/fold.ts` | hides chunks one level below documents |
| `src/Graph.tsx` | cytoscape graph |
| `src/canary.ts` | click mock for the chat canary |

Replace freely. The contract is fixed, the components are not.

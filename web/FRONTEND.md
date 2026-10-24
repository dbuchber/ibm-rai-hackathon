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

## Presentation UI

The frontend opens with the logo, a five-scene walkthrough, and the interactive workspace from
`demo.html` / `demo.app.html`. Click, use the presentation dots, or use arrow keys to move
through the first two screens. Auto-play advances every 3.5 seconds through each walkthrough scene; Escape returns from
the workspace to the last walkthrough scene. The scaled preview uses real events from
`demo-contradiction`, with no new engine run or changes to the interactive workspace.
The first walkthrough scene shows only chat. The question and search scenes keep that chat-only layout. The graph and evidence trail
reveal when the answer arrives, with a staggered entrance and a chat position transition.
The interactive workspace follows the same rule; recorded questions are available in chat
before an answer. Exploring earlier evidence keeps the answer and panels available.
Its captions describe existing question, traversal and evidence features; the design’s
alarm/fix-plan/checklist concept is represented by the current evidence trail.

The workspace has a collapsible graph, an evidence trail, and the answer chat.
The trail groups discovered entities, relevant relationships, excluded evidence, source
conflicts and supporting passages. Selecting a graph entity shows its connected facts.
It uses the existing `frames()` / `viewAt()` state: selecting a step pauses replay
and updates the graph to that frame. Node and relation buttons focus the graph; citations
still open source passages. The trail comes from the selected run rather than a fixed tutorial. Recorded questions replay through the existing engine events; selecting an evidence item
pauses playback and focuses that information. Mock canary runs remain available for manual
exploration. Static mode uses the recorded runs; live questions use the existing API and invitation-code field.

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

### Rebuilt maintenance data and recorded examples

The current graph includes the ST01 pressure, ST02 temperature and ST04 vibration scenarios
from commit `28e8516`. These are independent synthetic incident snapshots, not live machine
streams. The stored runs predate that rebuild and retain their original answers and embedded
evidence. Replay is labelled accordingly; it does not imply a newly generated maintenance
checklist. Live questions continue to use the configured engine API against the current graph.

Recorded questions remain on their final answer instead of automatically changing scenarios.
While the graph is hidden, replay advances quickly to the answer with status updates. Earlier
source chunks embedded in a recording remain inspectable even when their parent document
is no longer present in the rebuilt graph.

The Emergency Checklist opens on its first entity item once the answer is available.
Playback and navigation do not mark items complete. Each item has an independent checkbox
that the user explicitly checks or unchecks; completion does not change the graph selection.

A light/dark toggle is available on every screen. Its selection is saved locally and
updates the graph palette without resetting the current question or checklist state.

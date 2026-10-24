# Chat canary: from click mock to working prototype

Status: draft, 24 October 2026. Extends "Canaries against automation bias" in
`2026-10-24-graph-anchor-design.md`, whose chat part was a click mock.

## Why

People who get several good answers in a row stop checking the sources (automation bias, EU AI Act Art. 14).
The curation screen already tests this for real (`api/canary.py`). The chat only shows a hand-written run.
The live chat should test it for real: after a user trusted several answers blindly, one real answer gets one
deliberately false fact. The user is expected to flag it, the way one flags a message in ChatGPT or Claude.

## Goals

- In live chat (API mode, invite code), the server plants a falsified fact into a real engine answer when the
  user has shown blind trust.
- Users flag a message (thumbs down, optional free-text feedback). Flagging the canary counts as caught.
- If the user asks the next question without flagging, the chat first reveals the canary: false vs. true fact.
- Every outcome is in the audit log (`GET /api/audit`), next to the curation canaries.

## Non-goals

- No observability stack (Grafana, Langfuse, ...). The audit log in memory plus the run files are enough.
- No persistence across server restarts. Chat sessions and open canaries live in memory.
- No user accounts. A chat session is a browser tab.
- Checking whether the feedback text names the right fact. Flagging the message is enough.

## Anti-goals (a failure even if it works)

- The client can tell a canary before deciding (field in the stream, different timing, different event count).
- A canary is written to the graph or shown as approved knowledge anywhere else.
- The false fact is absurd or off-topic, so nobody would ever believe it. It must fit the question.
- The recorded demo changes. `mock-canary-chat` stays as it is, labelled Mock, for the pitch and static mode.

## Behaviour

### Chat session

The browser creates a random session id once per tab and sends it as header `X-Chat-Session` on every chat
call. All canary state is per session, so a room full of visitors sharing one invite code does not share one
counter. Missing header = no canary for that request (the run still works).

### Blind trust

A session counts *answers in a row whose sources were not opened*:

- The UI reports every time the user opens a source of an answer: a cited triple, a passage, the evidence
  graph (`POST /api/runs/{id}/opened`).
- When the session asks its next question, the previous answer is evaluated: opened → counter 0, not opened →
  counter + 1. Flagging a normal answer also resets the counter (the user is checking).
- When the counter reaches `RAI_CHAT_CANARY_STREAK` (default 3), the run about to start becomes a canary run.
  The counter resets.
- At most one open canary per session.

### Falsifying the answer

Server-side, after the engine produced the `answer` event and before it is stored or streamed:

1. Take the cited edges of the answer (`citations[].edge_id`) whose object label appears verbatim in
   `answer.text`. *(Builder's call:)* exclude edges whose object is the topic: its label appears in the
   question, or it is an endpoint of another cited edge. Swapping such a node would turn the whole answer into
   one about something the user never asked about.
2. Pick one (prefer leaf facts such as `supplied_by → Supplier` or `of_model → SensorModel`; else any).
3. Replace the object with another node **of the same class** from the approved graph that is not connected to
   the subject by this predicate. Replace every occurrence of the old label in `answer.text` and
   `answer.justification` with the new label.
4. Citations, passages, evidence and beats stay **unchanged**. A user who opens the source sees the true
   triple. That mismatch is the thing to catch.
5. If no cited edge qualifies, the run is a normal run and the session stays due for the next answer.

The server stores `{run_id, session, claim, truth, edge_id}` in memory and writes audit `canary_planted`
right away, so a canary whose visitor simply leaves is still visible in the audit log (planted, no outcome).
*(Builder's call: no timeout and no "unresolved" outcome; leaving the chat does not count as missed.)* `claim` and `truth` are full sentences
like `"ThermoSense AG supplies the temperature sensor"` / `"Sensorik Nord GmbH supplies ..."`, built from the
labels. The canary is never written to `urn:g:approved` or `urn:g:proposed`.

The stored run file (`runs/live-*.jsonl`) holds the answer exactly as streamed. `AnswerPayload.canary` stays
`null` in the stream. Nothing in the events differs from a normal run.

### Flagging

Every assistant message gets a flag action (thumbs down) that opens an optional text field, like ChatGPT/Claude.
`POST /api/runs/{id}/feedback {text?}`:

- on the open canary of this session → **caught**. Response carries the reveal (`claim`, `truth`,
  `outcome: "caught"`). UI: quiet toast "Good catch, that answer contained a planted false fact", plus the
  comparison. Audit `canary_passed` with the feedback text.
- on any other answer → normal feedback. Response without reveal. UI: "Thanks, an analyst will review this
  answer." Audit `feedback` with the text.
- Flagging twice is idempotent.

### Missed

`POST /api/runs` (next question) from a session whose canary is still open:

- the response carries `reveal` with `outcome: "missed"`. Audit `canary_failed` and `supervisor_notified`
  ("Quality lead (mock)", same as curation).
- UI shows the reveal **before** the new run: "Your last answer contained a deliberately false fact", false vs.
  true side by side, link back to that answer. Calm, unmistakable, the same visual family as the curation
  alert.
- The new run starts normally.

## Contract changes (`contracts/models.py`, then export schema + `npm run types`)

```python
class ChatCanaryReveal(BaseModel):
    run_id: str                      # the run that carried the false fact
    claim: str                       # what the answer said
    truth: str                       # what the approved graph says
    outcome: Literal["caught", "missed"]

class CreateRunResponse(BaseModel):
    run_id: str
    reveal: ChatCanaryReveal | None = None     # set when the previous canary was missed

class Feedback(BaseModel):              # POST /api/runs/{id}/feedback
    text: str | None = None

class FeedbackResponse(BaseModel):
    reveal: ChatCanaryReveal | None = None     # set when the flagged answer was the canary

class SourceOpened(BaseModel):          # POST /api/runs/{id}/opened, response 204
    target: str                      # edge id, chunk IRI or "evidence"
```

`AuditEntry.kind` gains `"feedback"`. `proposal_id` stays null for chat entries; the run id goes in `detail`.

`data.ts` gains `feedback(runId, text)`, `opened(runId, target)` and passes `X-Chat-Session`. Static mode keeps
today's click mock for `demo-canary-chat` and answers `feedback` locally without a reveal.

## Where the code goes

- `api/chat_canary.py`: session state, trigger, falsification, reveal. Same style as `api/canary.py`, shares the
  audit log of `CanaryGuard`.
- `api/main.py`: header, the two new endpoints, hook in `LiveRun.add` for the answer event of canary runs.
- `web/`: **built by the UI/UX team**, not in this work. Backend delivers contract, `data.ts` functions and a
  section in `web/FRONTEND.md` that specifies what the chat needs: a flag action + feedback field per message,
  the reveal box, `opened` calls, the session id. The existing `App.tsx` chat-canary mock stays only for
  recorded runs. (UI branch `chore/hackathon` already has a chat pane and the invite field.)

## Tests

- Trigger: 3 unopened answers → 4th run is a canary; an `opened` call in between resets.
- Falsified answer: object label replaced in text and justification, citations unchanged, `answer.canary` null,
  same event types and count as without canary.
- Flag on canary → caught reveal; flag elsewhere → no reveal; next question after a missed canary → missed
  reveal, audit entries present.
- No `X-Chat-Session` → never a canary.
- Recorded runs and `mock-canary-chat` unchanged.

## Left to the builder

Exact wording of messages, how the UI marks the open source (any interaction that shows a citation or passage
counts), choice among qualifying edges, and visual design of flag, feedback and reveal.

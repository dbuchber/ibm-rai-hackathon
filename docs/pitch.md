# Graph Anchor: 3-Minute Pitch Script

IBM Responsible AI Hackathon, 24 Oct 2026, pitch at 16:00. Total **180 s** (about 2.7 spoken words per second).
Main run: **`demo-po1003`**, replayed from the stored JSONL; the model contrast uses **`demo-po1003-granite`** (same question). No live LLM call and no network needed.

## Timing at a glance

| # | Screen | Start | Length |
|---|---|---|---|
| 1 | The twin | 0:00 | 15 s |
| 2 | Ask | 0:15 | 17 s |
| 3 | Traverse | 0:32 | 25 s |
| 4 | Answer | 0:57 | 23 s |
| 4b | Model contrast: Granite vs Mistral Large | 1:20 | 20 s |
| 5 | Contrast with vector RAG | 1:40 | 15 s |
| 6 | Curate, with the canary moment | 1:55 | 40 s |
| 7 | Roadmap | 2:35 | 25 s |

Before going on stage: open the app in replay mode (see Backup plan, level 0), pick the question `demo-po1003`, leave the curation list at its first item, and check that sound/animations are on. Rehearse once with a timer: the Curate screen is the one that runs over.

## Script

### 1. The twin (0:00 to 0:15)
**Click:** the app opens on the full-screen graph. Slowly drag or zoom once to show documents hanging off the plant.

> "Assistants answer from text that merely sounds like the question and ignore how knowledge connects. This is Kelvara, a fictional company running the real iMAKS plant data. Every dot is a curated entity. This graph is the anchor."

*Say it, don't skip it:* the company is fictional, the plant data is real.

### 2. Ask (0:15 to 0:32)
**Click:** "Ask the twin", pick the recorded question *"Order PO-1003 runs at the sealing station. Can it run at the sealing temperature limit, and who supplies the temperature sensor?"*. Press play.

> "A planner asks: can order PO-1003 run at the sealing limit, and who supplies the sensor? First the engine plans: it classifies the question and picks which relations it may follow. Everything else is off limits."

*What is on screen:* the strategy card with the allowed-predicate chips (`executed_at`, `applies_to`, `monitors`, `of_model`, `supplied_by`) and max depth 4.

### 3. Traverse (0:32 to 0:57)
**Click:** let it play. Pause once on step 1, show a *pruned* edge and a *followed* edge.

> "From three entry points it walks. At every hop the model judges each edge: follow or prune, with a reason. Two steps reach the sensor model and its supplier, then: enough evidence. Pruned edges stay dim."

*Honest note, only if asked:* the model is Mistral Large 4 via OpenRouter. the Granite run in step 4b is real (IBM ICA API); the Mistral runs go through OpenRouter.

### 4. Answer (0:57 to 1:20)
**Click:** open the answer card, then the **Evidence graph** button. Click one citation.

> "The order can run at 195 degrees, the sensor comes from ThermoSense, but the critical 210 exceeds its 200-degree rating. Every claim cites a triple or passage; this evidence graph shows only what the answer relies on. We show what the model was given."

*Honest note:* in this run the 210 versus 200 conflict appears in the answer text but not as a contradiction badge. The badge is shown in the recorded run `demo-contradiction` (SOP versus supplier quality agreement). Switch to it for 5 seconds if time allows, otherwise just say it.

### 4b. Model contrast: Granite vs Mistral Large (1:20 to 1:40)
**Click:** in the run picker choose the recorded run *PO-1003 · IBM Granite 4 H Small*. Let the strategy card and the evidence graph appear (do not wait for every step). Then jump back to the evidence graph of the Mistral run for a second.

> "Same question with IBM Granite 4 H Small: 33 seconds instead of three minutes. But its strategy skips the document links, so it never reaches the datasheet and misses the 210 versus 200 conflict. The evidence graph shows why. That is why we route: small models for steps, large for strategy and answer."

*What is on screen:* Granite's strategy card (`executed_at`, `applies_to`, `of_model`, `supplied_by`; no `mentions`, no `defined_in`) and a smaller evidence graph (6 nodes, 5 edges) without the document nodes. Granite does find the supplier ThermoSense GmbH correctly.

*Honest notes:* this is one question, one run each: a contrast, not a benchmark. Do not say "Granite is worse"; say "this smaller model planned too narrowly here". The Granite call is real (IBM ICA API, model `openai/ibm/granite-4-h-small`); the Mistral runs go through OpenRouter. Which model should handle which task is the roadmap hypothesis this run motivates, not something we have measured.

### 5. Contrast with vector RAG (1:40 to 1:55)
**Click:** open the Contrast view.

> "Same question through plain vector RAG, top three passages. It finds right-sounding SOPs, then admits it knows nothing about this order or its supplier. That fact lives in the links. This baseline is real."

*What is on screen:* the "Illustrative example" tag appears only on hand-written baselines. This run's baseline is real; do not claim otherwise either way.

### 6. Curate, with the canary moment (1:55 to 2:35)
**Click:** open Curation. Approve the first proposal, the second, the third, the fourth, each in a second or two. Then the next list refresh contains the canary among its first three items: *"ST02_SEALING supplied_by Velora Foods AG"* (a station "supplied" by a customer). Approve it, too. The alert opens; show the reverted items and the audit log.

> "How does knowledge get into the graph? The model only proposes: edges, entities, even new relations. A human approves. Nothing enters the approved graph, and so nothing enters an answer, without that click. But humans get tired. After a few quick approvals we plant a test, an obviously false proposal: a station supplied by a customer. I approve it, as a tired reviewer would. The system does not write it, reverts every approval since the last check, and notifies the quality lead. That is human oversight you can measure, our answer to automation bias under Article 14 of the EU AI Act."

*Honest note:* the proposals are real LLM output on the real documents, but this screen is a **click mock**: decisions live in memory (the tag says "Mock · in memory"), the quality lead notification is simulated, and the canary is planted by a fixed rule after four approvals in a row. If you reject or flag the canary, you get the quiet "Good catch" toast instead: either branch is fine to demo.

### 7. Roadmap (2:35 to 3:00)
**Click:** open Roadmap.

> "Next, labelled as not running today: right-sized models on-premises. Small ones for step verdicts, a large one for strategy and answers, escalation on contradictions, and Granite through the same gateway. Plus guardrails, chat feedback into curation, source links, node-level access. The model proposes, people approve, the graph is the anchor."

## What is real, what is mock

| Part | Status |
|---|---|
| iMAKS plant data (nodes, edges, rules, SOPs, datasheets) | **Real**, Zenodo record 20075430 |
| Kelvara Packaging GmbH, customers, suppliers, production orders, quality agreement and contract | **Fictional, synthetic** (written for the demo) |
| Graph in the UI (293 nodes, 867 approved edges) | Real build output; the approved layer is script-built, not LLM-extracted |
| Runs `demo-po1003`, `demo-contradiction`, `demo-maintenance` | **Real engine output**, Mistral Large 4, stored and replayed. `demo-contradiction` contains one step where the model returned unusable JSON and the engine fell back; the answer is still correct |
| Run `demo-po1003-granite` (IBM Granite 4 H Small via IBM ICA API) | **Real engine output**, real Granite call, 33 s; it answers "can run at the limit" and misses the datasheet and the conflict |
| Vector-RAG baseline in those runs | **Real**, top-k 3, same chunks and model |
| Live mode (free-text question) | **Real**, but 45 to 150 s per question and model-dependent; never needed for the pitch |
| Curation proposals (3 contradiction edges) | Real LLM proposals; one is a hand-seeded analyst proposal if marked so |
| Curation clicks, audit log, supervisor notification | **Mock** (in memory, labelled) |
| Canary in curation | Mechanism implemented; **notification is simulated** |
| Canary in the chat (`mock-canary-chat`) | **Mock run**, labelled; do not present as engine output |
| Roadmap screen | **Not running**, labelled "Roadmap" |
| Models | Mistral Large 4 via OpenRouter (main runs); IBM Granite 4 H Small via IBM ICA API (contrast run). Router and size ladder on the roadmap are not implemented |

Do not say: "the model understood", "the model used", "100% accurate", "we evaluated accuracy". We have shown 3 questions, not an evaluation. Accuracy and faithfulness measurement is "how we would measure it" only.

## Responsible-AI arguments (one line each, to land in the speech)

1. **Grounding in a curated graph.** The model proposes, analysts approve; the engine walks only the approved named graph. Hallucination risk stays out of the substrate.
2. **A traceable evidence graph.** Every answer shows the strategy, a verdict per hop, cited triples and passages, and the subgraph behind them: we show what the model was given, and it also makes a smaller model's gap visible (Granite's missing datasheet).
3. **Contradiction instead of silent choice.** When an SOP and a datasheet or agreement disagree, the answer says so.
4. **Canaries against automation bias (EU AI Act Art. 14).** Planted false items measure whether the human is still checking; a miss reverts the unchecked approvals and escalates.

## Backup plan

Everything in the pitch runs from stored files. Decide in this order, and decide fast: 10 seconds of fiddling costs a screen.

**Level 0, normal:** laptop, local static replay, no internet.
```bash
cd web && VITE_DATA=static npm run build && npm run preview     # http://127.0.0.1:5180
```
Prepare this on the laptop **before** the session and keep the tab open. The hosted site `https://rai-hackathon.bbger.at` is the second choice, not the first: it needs the venue network.

**Level 1, venue Wi-Fi down:** nothing changes, because level 0 does not use the network. Do not open live mode. Do not open the hosted site.

**Level 2, projector or HDMI fails:**
- Mirror to a phone or tablet via the laptop's hotspot only if the room has no projector at all. Otherwise present from the laptop screen with the jury gathered around it.
- Keep the screen recording (below) on a USB stick and on the phone.

**Level 3, the app itself breaks (blank screen, crash):**
- Switch to the pre-recorded screen capture of the full 3-minute click path (record it once during rehearsal at 15:00, with the same script). Narrate over it live.
- If even that is unavailable, speak from this document: the story works with only the contradiction sentence and the canary sentence.

**Level 4, a single screen misbehaves:** skip it and say one sentence. Order of what to drop, last first: Roadmap (say it in 10 s), the Granite contrast (4b), the RAG contrast, Traverse detail. Never drop Curate and the canary: it is the Responsible-AI moment.

**Prepare by 15:30 (feature freeze):**
- [ ] `npm run preview` works from a cold terminal on the pitch laptop, offline.
- [ ] Screen recording of the click path saved on laptop, USB stick and phone.
- [ ] This script printed once, or on a phone.
- [ ] Charger, HDMI and USB-C adapters.
- [ ] One person on the team is the only one touching the keyboard.

## Likely questions, honest answers

- **Why not just a bigger RAG?** Similarity cannot tell that the sensor's supplier is linked to this order's station; the link is the knowledge. Our baseline shows the same chunks failing.
- **Who curates at scale?** The model proposes, rule-based checks and analyst review decide; canaries keep the reviewer honest. The curation queue is a mock today.
- **Does it work with Granite?** Yes, one recorded run today via the IBM ICA API (33 s). It planned narrowly and missed the datasheet conflict on this question, which is why we propose routing. One question is not an evaluation.
- **Is the accuracy measured?** No. We show 3 recorded runs and a fair baseline for contrast. Evaluating accuracy and faithfulness over many questions is the next step, using the thesis setup.
- **What if the graph is wrong?** Then the answer cites a wrong edge and the evidence graph shows it. That is the point: the error is visible and fixable at the source, not buried in embeddings.

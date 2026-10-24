# Live chat: 5 free questions against the real graph

Run on main 462011f, graph `data/graph/kg.trig` as shipped, model `openai/mistral-large-4-openrouter`, via
`engine.run --mode live` (same code path as the API). Raw runs were written to a scratch dir, not to `runs/`.
All five ran **in parallel**, so durations below are inflated. See the latency warning.

## Latency warning (most important)

| Run | Wall time |
|---|---|
| q1 / q2 / q3 / q4 / q5, five in parallel | 572 / 367 / 472 / 332 / 266 s |
| q4 alone, same time of day (12:49 UTC) | **641 s** |

The earlier QA free-text run took about 77 s. Today every traversal step took 2 to 4 minutes (q4 alone: strategy 28 s,
step 1 at +133 s, step 2 at +235 s, answer at +232 s). The slowdown is in the gateway/model, not in the engine or the
graph (the strategy call is fast). **Before the pitch: time one live question right before going on stage, and keep a
replay run as fallback.** The UI should show a progress hint while a live run is open.

## Results

| # | Question | Seeds | Verdict |
|---|---|---|---|
| q1 | At ST02_SEALING the SOP sets the CRITICAL current threshold to 15 A. Is that compatible with the rating of the current sensor? | ST02_SEALING, ST02_SEALING_TMP, ST02_SEALING_PRS | **Correct.** Contradiction found: CT-3300 continuous overload 14 A, datasheet recommends alarm thresholds at or below 14 A. Cites SOP-002-s6 and DS-ELEC-3300-s1 plus edges. Best contradiction question: the stored `contradicts` edge is approved. |
| q2 | Is the 210 °C emergency-stop threshold at ST02_SEALING within the warranty of the temperature sensor, and what does the supplier agreement say? | same three | **Correct.** "No": SQA-THERMO-001 §2 warrants up to 200 °C, 10 °C below the SOP's 210 °C. Chain station, sensor, TMP-2210, supplier, agreement. |
| q3 | If PO-1006 stops because of a CRITICAL alarm, how quickly must the service provider be on site, and who do we order a spare temperature sensor from? | PO-1006, MAINT-03, MAINT-07 | **Mostly correct.** 4 h (MC-2026-01 §2) and ThermoSense are right, and it adds the 200/210 °C contradiction unprompted. One misattribution: the spare-ordering sentence is in MC-2026-01 §3, the answer cites SQA-THERMO-001 §3 (replacement within 5 working days). Seeds MAINT-03 and MAINT-07 are noise (they matched "CRITICAL"/"stops"). |
| q4 | Which maintenance action is triggered by current drift at ST02_SEALING, what is its priority, and which SOP defines it? | ST02_SEALING, RULE-ST02-04, RULE-CORR-02 | **Correct.** MAINT-02, HIGH, SOP-003, trigger CUR drift >1.0 A for 30+ min. Also notes the different RULE-ST02-03 threshold (1.5 A / 5 min). Edge `ST02_SEALING_CUR triggers MAINT-02` cited. |
| q5 | Within how many minutes must an operator acknowledge a CRITICAL alarm, and may an operator enter the Server Room? | Server_Room, operator, SE-009 | **Half wrong. Do not use on stage.** Answers "not specified" for the acknowledgment time, but SOP-004 §3 says 3 min. The "may not enter" part is right in conclusion but argued from one person (P019) instead of the role matrix SOP-004 §1. |

Recommended for the stage, in this order: **q1** (contradiction), **q2**, **q4** (clean multi-hop with citations),
**q3** if time allows.

The vector-RAG baseline on q5 returned MC-2026-01-s2 and SOP-003-s7 (irrelevant) too, so q5 is not a graph-vs-RAG win.

## KG findings (nothing changed; contracts/ontology untouched)

1. **Acknowledgment rules are unreachable from Roles (cause of q5).** The 8 `RULE-ACK-*` nodes (e.g. `RULE-ACK-OP-CRIT`,
   "Must acknowledge within 3 minutes") have only `defined_in -> SOP-004-s3`. There is no edge from a Rule to a Role, and the
   `Role` nodes have only incoming `has_role` from the 44 Persons. A traversal starting at `operator` therefore fans out
   into Persons and Zones and never reaches SOP-004-s3. Fix, if wanted: in `kg/layer2_docs.py` add `applies_to`
   (Rule -> Role) for the ACK rules from the `rule.comment` ("operator role — CRITICAL ..."). Needs a check that the
   ontology allows that domain/range; if not, that needs a contract change, which is yours to decide.
2. **Seed noise on order questions (q3).** `MAINT-03`, `MAINT-07` are seeded next to `PO-1006`. Exact-ID seeds are fine; the
   embedding seeds add unrelated maintenance actions. Harmless here, but it wastes frontier slots.
3. **QA point 14 (run 0 flags the contract, not the datasheet) is not a graph fault.** In q2/q3 the model names both SQA-THERMO-001 and
   the SOP. The datasheet chunk `DS-THERM-2200-s1` is reachable via `of_model`, but the contract chunk is shorter and
   states the limit more plainly, so the model prefers it. The pitch sentence should say "supplier contract and datasheet".
4. **Citations of the form `{'edge_id': None, 'chunk_id': ...}`** in q1 are fine for the UI (join on ids), but the answer text
   embeds raw edge ids like `[b23e10c11ecd]`. The justification then reads as noise to a non-technical audience.

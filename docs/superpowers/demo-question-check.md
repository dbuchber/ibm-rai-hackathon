# Demo question check against the real graph

Run: `uv run python -m scripts.check_demo_questions` (graph only, no LLM). Stream B's `runs/*.jsonl` were still
incomplete at the time (only `run.started`), so the real engine runs are not checked here.

| Question | Reachable in the approved graph? |
|---|---|
| demo-po1003 (company → plant → document) | Yes. `PO-1003 -executed_at-> ST02_SEALING`, `SQA-THERMO-001-s2 -mentions-> ST02_SEALING / TMP-2210`, `TMP-2210 -supplied_by-> ThermoSense`: 4 hops. The warranty limit (200 °C) sits in chunk `SQA-THERMO-001-s2`, reachable in 3 hops. |
| demo-contradiction | Yes, but not through an edge. `SOP-001-s3` (RULE-ST02-02, 210 °C) reaches `DS-THERM-2200-s1` (200 °C continuous) in 3 hops via `ST02_SEALING_TMP -of_model-> TMP-2210`. The `contradicts` edge is only in `urn:g:proposed`, so the engine has to notice the conflict from the two chunk texts. |
| demo-maintenance | Half. SOP-003 is 2 hops from `ST04_PACKAGING` (`MAINT-01` chunk). "Who is authorized" is not modelled: `authorized_for` links Persons to Zones only, and all 44 persons are authorized for Production Area. |

## Findings
1. **Seeds:** the contract's lexical `RdfGraphStore.search` ranks wordy chunks above exact IDs. For the PO-1003 question the top seed is `SQA-THERMO-001-s1`, not `PO-1003` or `ST02_SEALING`. Stream B should boost exact local-ID matches (`PO-1003`, `ST02_SEALING`, `ST04_PACKAGING`) before the embedding ranking.
2. **Contradiction:** if the pitch should show the flagged contradiction as a graph edge, one proposal must be approved in the shipped graph (e.g. `SOP-002-s6 contradicts DS-ELEC-3300-s1`), or the demo question stays text-based. Approving `SOP-001-s3 contradicts DS-THERM-2200-s1` would remove it from the curation screen.
3. **Maintenance question:** replace the "who is authorized" part, e.g. "Which SOP defines the maintenance action MAINT-01 on ST04_PACKAGING, and which sensor triggers it?" (answerable: `MAINT-01` → `ST04_PACKAGING_VIB`).

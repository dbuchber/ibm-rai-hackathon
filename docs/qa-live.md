# QA of the live site (https://rai-hackathon.bbger.at)

Date: 2026-10-24. Tool: Playwright (Chromium), viewports 1600x900 and 1280x720. No code was changed.
Screenshots: `docs/qa-screenshots/` (`<viewport>-<n>-<screen>.png`; `local-*` come from a local copy, see below).

**Method.** Read-only checks ran against the live site: Twin, Ask picker, the 3 real runs played to the end, Contrast for each,
Curate, Audit log and Roadmap, at both viewports. Everything that changes state (approve, reject, add proposal, planted-canary
flow, free-text live questions) ran against a **local copy of main** (API + built UI, throw-away `RAI_PROPOSALS` and
`RAI_RUNS`) so the live server's `data/proposals.json` and `runs/` stayed untouched. Live-site behaviour of those paths is
therefore inferred from the same code, not observed.

## What works

- All 3 real runs play to the end (17 to 22 s each), end on the evidence graph and finish without console errors. Contrast renders for each. No horizontal page scroll at either viewport.
- The planted chat canary works as designed: leaving the mock run unreported opens the oversight alert (`local-...-canary-left-unreported.png`), reporting it shows "Good catch" (`...-canary-reported.png`). The run is tagged **Mock run**.
- Curation with all three kinds: filters (All / Edges / Nodes / Predicates), approve, reject, add-form for edge and node, duplicate-ID guard ("A node with this ID already exists."), disabled Propose with a reason in the tooltip. A proposed node (Series 2400) appears in the twin as a dashed node.
- A free-text live question (local, mistral-large-4) produced a correct, cited answer (humidity sensor → HUM-2250 → ThermoSense GmbH) in about 77 s.

## P1: fix before the pitch

1. **`GET /api/audit` returns 404** (live and local). Every page load logs a console error, and the **Audit log is empty ("Nothing logged yet") after approvals, rejections and added proposals** in API mode (`local-...-audit-after-actions.png`). The UI's "Audit log" promise ("Every decision, every test") is not met on the live site. Either add the endpoint in `api/` or hide the entry point in API mode.
2. **Roadmap footer is stale:** "Today: one model (gemma-4-31b) through a LiteLLM gateway…". Live runs use `mistral-large-4-openrouter` and gemma returns 404 on the gateway. Wrong claim on the screen the jury sees (`1600x900-6-roadmap.png`, last line).
3. **Twin text over-claims:** "Every relation here was approved by an analyst." Layers 1 to 3 are script-built from iMAKS and a hand-written YAML; only the curation examples go through an analyst. Suggest "Every relation here is approved. Models only propose." or similar, consistent with the README.

## P2: should fix

4. **New-node form defaults to class `AnomalyEvent`** (first alphabetical). A user who fills ID and label and presses Propose creates `AnomalyEvent · QA-Model-1` without noticing (`local-...-add-node-submitted.png`). The form also offers `Chunk`, `Rule`, `Person`, `Zone`… as classes for new nodes. Start with a placeholder "Choose…" and offer only real-world entity classes (SensorModel, Supplier, Customer, Company, Role), as `kg.propose` does.
5. **Live mode feels frozen for 60 s+.** Strategy arrives after about 23 s, the first step after about 60 s, the answer at about 77 s. The player sits on "Entry points" with a pause icon and no "working…" indicator (`local-live-mistral-end.png`). Add a spinner or "Waiting for the model…" line, and tell people in the pitch not to rely on it.
6. **Raw exception text in the UI on a failed live run:** "Run failed: BadRequestError: litellm.BadRequestError: LLM Provider NOT provided… Learn more: https://docs.litellm.ai/…" (`local-live-badmodel-end.png`, triggered by an unset model). Show a short message ("The model is not available. Replay the recorded runs.") and log the details server-side. Also worth checking that the live server's `.env` can never fall back to `stub`.
7. **Evidence graph is cluttered**, especially at 1280x720: rotated edge labels ("applies to", "monitors", "mentions · 1 passage") sit on top of node labels, and big bold labels overlap ("SOP-001 Standard Op…" / "ST01_FILLING"; `1600x900-3-run0-end.png`, `1280x720-3-run0-end.png`). Dim or hide edge labels except for the selected/hovered edge; cap label size in evidence mode.
8. **Twin is a hairball.** The zone cluster (all `authorized_for` person edges) overlaps labels ("Chemical Storage / Main Entrance / General Warehouse"). It reads as a rich graph from afar, but the first screen has unreadable labels at 1600x900 (`1600x900-1-twin.png`). Consider hiding Person and event nodes by default or folding them into one "44 persons" node.
9. **Run 0 contradiction is against the company contract, not the datasheet.** The flagged conflict is SOP-001/SOP-002 (210 °C) vs `SQA-THERMO-001 §2` (warranty to 200 °C), while the question asks about "the sensor datasheet" and the answer says "the datasheet does not support…". Both are true, but the pitch line "SOP vs datasheet" should say "SOP vs supplier agreement and datasheet", or the run should cite `DS-THERM-2200 §1` too. The SOP-001 vs DS-THERM-2200 edge is still only a proposal (by design).
10. **Contrast and run cards are cut at the viewport bottom at 1280x720** (`1280x720-4-contrast-run2.png`, `...-6-roadmap.png` "Trust and reach" tiles). The content scrolls, but there is no scroll hint or fade, so it looks clipped. The Ask picker's fourth card and the free-text box are also below the fold at 1280x720.

## P3: polish

11. Curate card header shows a stray `---` glyph before "EDGE" (`1280x720-5-curate.png`); the predicate "performs" has the low-value description "Company verb Maintenance." (LLM output, not edited).
12. Predicate add-form was not submitted in this QA (the description field selector changed between kinds). Retest by hand: switch Predicate, fill name/description/why, Propose.
13. The mock canary run shows model `gemma-4-31b-it` in its tag while live runs show `mistral-large-4-openrouter`; fine for a mock, but jurors may ask.
14. `ThermoSense GmbH / ElectroMeasure AG` both appear as seeds for "Which supplier delivers the humidity sensor?" (scores 0.69 / 0.68). The strategy and later steps recover, but the first screen shows a wrong entry point.
15. Console warning on every load: "You have set a custom wheel sensitivity…" (Cytoscape). Harmless.

## Not covered

Mobile widths, keyboard shortcuts 1 to 5, screen readers, the SSE "connection lost" state, and the live site's free-text mode (to avoid writing runs to the production `runs/` directory).

# Scenario 1: lone operator responding to conveyor vibration

All equipment details, events, work reports, contacts, and procedures added for this scenario are synthetic and in English. Existing iMAKS station IDs, sensor IDs, alarm limits, nominal bands, and MAINT-01 are reused. New component IDs and alarm codes are fictional extensions.

The incident is INC-ST04-20261024-01 at ST04_PACKAGING during PO-1005. The replay is fixed at **2026-10-24 10:00:05 Europe/Vienna**. The operator is alone and trained for external checks. Qualifications for intrusive maintenance and authority to restart are not assumed.

| Source in `data/docs` | Document/source ID | Purpose |
|---|---|---|
| ST04_EquipmentGuide.md | EQ-ST04-001 | Locations, controls, operator scope, contact route |
| ST04_AlarmReference.md | ALM-ST04-001 | Codes, thresholds, freshness, alarm lifecycle |
| ST04_VibrationTroubleshooting.md | TRB-ST04-001 | Actions, observations, branches, stop conditions |
| ST04_MaintenanceHistory.md | HIST-ST04-001 | Historical findings and their limits |
| ST04_RecoveryAndRestart.md | REC-ST04-001 | Test prerequisites and production release criteria |
| ST04_Telemetry.json | TEL-ST04-001 | Historical running samples and final stopped snapshot |
| ST04_AlarmEvents.json | EVT-ST04-001 | Timestamped warning and critical alarm activations |

The two JSON sources share station, incident, order, and sensor IDs. Alarm entries reference the exact telemetry sample that triggered them. Both sources use timezone-aware timestamps and the same `as_of` selection. Telemetry is sparse replay evidence, not a continuous stream. No observations after the selected time, completed repairs, or successful recovery are supplied.

`data/company.yaml` registers all seven sources. `kg.layer3_company` loads Markdown sections and calls `kg.operational` for the JSON sources. The adapter produces citable Document/Chunk nodes, links observations to existing sensors and the station, and connects AnomalyEvent nodes using the existing `triggers` predicate. It excludes future records, exposes snapshot freshness/quality, and computes alarm activity from lifecycle transitions at the selected time. Records remain immutable fixture files; nothing connects to a physical machine or refreshes automatically. Changing the files or selected time requires rebuilding the graph. The fixture's approved evidence status is not an approval to operate the machine.

Example question:

> At ST04_PACKAGING, PKG-VIB-HH has activated. I am the only trained line operator here. Using the machine replay at 2026-10-24T10:00:05+02:00, give me a detailed checklist of what I can check, what each result means, and what must happen before restart. Cite the evidence and identify missing information.

Build with `python -m kg.build` in the project environment. This also requires the existing iMAKS raw sources and project dependencies. The generated graph and static graph export have been rebuilt with all three scenarios. Existing recorded demos still show the earlier scenarios. The answer prompt still requests a short answer; structured checklist generation and checklist UI are separate follow-up work.

The other independent replay vignettes are described in [scenario 2](st02-scenario.md) and [scenario 3](st01-scenario.md). Their selected times are separate incident contexts, not a synchronized whole-line simulation.

Dataset checks: `python -m pytest tests/kg/test_operational.py -q`. These do not require an LLM or the iMAKS download.

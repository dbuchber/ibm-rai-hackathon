# Scenario 2: sealing temperature and instrument protection gap

All new sources are synthetic and in English. The station ST02_SEALING, temperature sensor ST02_SEALING_TMP, model TMP-2210, current sensor ST02_SEALING_CUR, and order PO-1003 reuse existing graph identifiers.

Incident INC-ST02-20261024-01 is evaluated at **2026-10-24T12:00:05+02:00** (Europe/Vienna). This is an independent replay vignette, not a synchronized continuation of scenario one. A lone trained operator receives a temperature warning; readings rise from 185 to 198 to 205 degrees C, followed by an operator stop and a cooling reading of 204 degrees C. There is no critical temperature-trip event because the reported peak has not exceeded 210 degrees C.

| Source in `data/docs` | ID | Purpose |
|---|---|---|
| ST02_EquipmentGuide.md | EQ-ST02-001 | Installed model, controls, locations, operator scope |
| ST02_AlarmReference.md | ALM-ST02-001 | Warning, critical trip, instrument advisory, freshness |
| ST02_SpecificationApplicability.md | SPEC-ST02-001 | Source applicability and protection mismatch |
| ST02_TemperatureTroubleshooting.md | TRB-ST02-001 | Detailed external checks and decision branches |
| ST02_MaintenanceHistory.md | HIST-ST02-001 | Prior confirmed causes, explicitly historical |
| ST02_RecoveryAndRestart.md | REC-ST02-001 | Verification and engineering release prerequisites |
| ST02_Telemetry.json | TEL-ST02-001 | Timestamped readings and reported operator stop |
| ST02_AlarmEvents.json | EVT-ST02-001 | Warning and instrument-limit advisory activations |

The core distinction is between the 175–195 degrees C operating band, TMP-2210's 200 degrees C continuous rating, and the critical alarm threshold above 210 degrees C. A critical threshold is not an acceptable operating maximum. The datasheet's intermittent 220 degrees C note is not valid for control. Good telemetry transport quality does not prove measurement accuracy outside the instrument rating. The applicability note records a protection gap; it does not replace or silently revise either original source. No root cause, independent measurement, engineering disposition, repair completion, alarm clearance, or release is supplied.

Example question:

> At ST02_SEALING I am alone and SEAL-TMP-HI is active. Using the replay at 2026-10-24T12:00:05+02:00, give me a detailed checklist. What can I inspect from outside, why is the 205 degrees C reading a problem even without a critical trip, and what blocks restart? Cite the applicable sources.

Sources are registered in `data/company.yaml` and use the same Markdown/JSON ingestion as scenario one. There is no physical machine connection. Existing recorded demos are unchanged; full checklist generation still requires the planned answer-output changes and a configured model.

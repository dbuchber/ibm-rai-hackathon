# Scenario 3: filling pressure loss with the specialist unavailable

All new sources are synthetic and in English. The station ST01_FILLING, pressure sensor ST01_FILLING_PRS, flow sensor ST01_FILLING_FLW, maintenance action MAINT-04, and order PO-1001 reuse existing graph identifiers.

Incident INC-ST01-20261024-01 is evaluated at **2026-10-24T13:00:05+02:00** (Europe/Vienna). This is an independent replay vignette, not a synchronized line simulation. Pressure drops from 3.8 bar to a warning at 3.2 bar and a critical reading of 2.9 bar. Running flow declines from 120 to 110 L/min. The final snapshot reports STOPPED_QUALITY_HOLD, pressure 2.8 bar, and zero flow. The stop-on-quality-hold behavior is a fictional controller policy, not an added iMAKS emergency-stop requirement.

| Source in `data/docs` | ID | Purpose |
|---|---|---|
| ST01_EquipmentGuide.md | EQ-ST01-001 | Product path, external indicators, operator scope |
| ST01_AlarmReference.md | ALM-ST01-001 | Pressure/flow limits, duration uncertainty, lifecycle |
| ST01_PressureTroubleshooting.md | TRB-ST01-001 | Inlet-indicator and pump-status decision branches |
| ST01_MaintenanceHistory.md | HIST-ST01-001 | Competing historical causes and missing diagnostics |
| ST01_ResourcesAndService.md | RES-ST01-001 | Time-bounded support and stock snapshot |
| ST01_RecoveryAndRestart.md | REC-ST01-001 | Maintenance, hygiene, verification and separate product release |
| ST01_Telemetry.json | TEL-ST01-001 | Timestamped pressure/flow and machine state |
| ST01_AlarmEvents.json | EVT-ST01-001 | Low pressure, critical pressure, and low-flow activations |

The operator is alone. The usual specialist is off shift; a remote triage service route is scheduled, but no answered call, dispatch, or arrival is confirmed. The resource snapshot expires fifteen minutes after the incident selection. A compatible filter cartridge is listed in stock; that is not a diagnosis or permission to install it. Personnel IDs are fictional scenario-only identifiers, not iMAKS registry identities.

External valve-position and pump-status observations are deliberately absent, so the checklist must ask the worker to record them and branch on the result. Sparse low-pressure samples do not prove the continuous fifteen-minute MAINT-04 condition. The inlet-valve check's five-minute deadline is already past at the selected time; no completed check may be invented. No root cause, completed repair, verified depressurization, product segregation, alarm clearance, or release is supplied. A requested quality hold is distinct from confirmed execution, and machine release is distinct from Quality's product release.

Example question:

> At ST01_FILLING FILL-PRS-LL is active and I am the only trained line operator here. Using the replay at 2026-10-24T13:00:05+02:00, give me a detailed checklist with branches for the inlet indicator and pump status. Who can I contact, which observations are missing, and what must happen before machine and product release? Cite the evidence.

Sources are registered in `data/company.yaml` and use the existing scenario replay adapter. This is not a physical machine stream. The recorded UI demos are unchanged; a configured model and the planned checklist-output changes are required for a generated checklist.

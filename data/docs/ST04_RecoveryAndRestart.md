# ST04 Recovery and Restart Conditions

## Scope and document control
Document ID: REC-ST04-001. Revision: 1. Effective date: 2026-10-24. Owner: Kelvara Maintenance Engineering. Fictional release rules for ST04_PACKAGING following a vibration alarm. Supplements RULE-ST04-01, RULE-ST04-02, and MAINT-01. This document states acceptance criteria; it is not an isolation, repair, or controller-reset instruction.

## Hold after critical vibration
After PKG-VIB-HH at ST04_PACKAGING, keep the station stopped until a qualified technician has assessed the cause and the shift supervisor has authorized a controlled verification test. An operator working alone cannot grant these approvals. Alarm acknowledgement, zero vibration at zero speed, an old successful work order, and an absence of visible damage do not satisfy release conditions. If assistance is unavailable, the checklist ends with the machine stopped and maintenance pending.

## Prerequisites for a controlled verification test
For ST04_PACKAGING, the maintenance record must identify the incident, inspection findings, any corrective work, and the qualified technician responsible. The technician must confirm completion of the approved isolation and restoration process, guards restored, personnel clear, and protective functions available. The shift supervisor must record test authorization. No test may start with missing prerequisites. The actual restoration, reset, and start sequence must come from the separate approved machine instruction; it is not supplied here.

## Verification acceptance criteria
For an authorized supervised ST04_PACKAGING test at the documented reference speed of 1.20 m/s, collect good-quality ST04_PACKAGING_VIB, ST04_PACKAGING_SPD, and ST04_PACKAGING_CUR samples at intervals no greater than 10 seconds for five uninterrupted minutes. Vibration must remain within 0.115 to 0.125 mm/s, speed within 1.18 to 1.22 m/s, and current within 8.5 to 8.9 A. These fictional test criteria use the existing SOP-002 nominal bands and are stricter than warning limits. No active vibration alarm, unexpected noise, or visible abnormal movement is permitted. If any criterion fails or a sample gap exceeds 10 seconds, stop the test and return the incident to maintenance; do not repeatedly reset.

## Production release and incident closure
For ST04_PACKAGING, the shift supervisor records production release only after the authorized verification test passes and the alarm lifecycle explicitly records clearance. Record test start/end, measurement references, work-order reference, technician confirmation, supervisor approval, and release time. Until those records exist, report restart blocked. INC-ST04-20261024-01 supplies no post-repair test, repair completion, alarm clearance, or release record; checklist generation must not claim successful recovery.

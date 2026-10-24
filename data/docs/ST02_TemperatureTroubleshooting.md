# ST02 Temperature Alarm Troubleshooting

## Scope and document control
Document ID: TRB-ST02-001. Revision: 1. Effective date: 2026-10-24. Owner: Kelvara Maintenance Engineering. Applies to ST02_SEALING. Fictional equipment details and synthetic training instructions; not manufacturer instructions. Existing iMAKS limits are retained. No intrusive repair or isolation sequence is supplied.

## Step 1: establish state and timestamp
ST02_SEALING: At HMI-ST02 Diagnostics, record the selected time, machine state, ST02_SEALING_TMP reading, timestamp, and quality. Use ALM-ST02-001 freshness rules. If missing or stale, do not claim the station is safe; contact Maintenance Desk 240. In an actual running over-temperature condition, use the normal Stop control from outside the guard. If an immediate hazard is present, use the emergency stop and keep clear.

## Step 2: record the temperature history
ST02_SEALING: Open Alarm History and the temperature trend. Record each alarm instance, activation time, trigger sample, peak temperature, operating setpoint if visible, and controller action. Do not change the setpoint or acknowledge away the evidence. An absent setpoint in the replay is unknown. Distinguish the running peak from the later cooling observation and document whether state STOPPED_OPERATOR is supported by fresh telemetry.

## Step 3: compare all three limits
ST02_SEALING: Using SPEC-ST02-001, compare the observed running peak with the 195 degrees C operating-band ceiling, the 200 degrees C TMP-2210 continuous rating, and the 210 degrees C critical threshold. At 205 degrees C report both exceeded limits and the not-yet-triggered critical threshold. Flag the protection mismatch. Do not describe the reading as a verified true temperature or use the intermittent rating to justify operation.

## Step 4: inspect externally
ST02_SEALING: From OBS-ST02-01 outside closed guards, note visible product accumulation, unusual discoloration, or visible cable damage as observed, not observed, or not visible. Do not touch surfaces, remove trays, open guards, or inspect energized circuits. If smoke or another immediate hazard appears, withdraw and follow site emergency arrangements. Lack of visible damage does not establish heater or sensor integrity.

## Step 5: separate hypotheses and escalation
ST02_SEALING: Read HIST-ST02-001. A previous controller setting error or sensor drift is only a hypothesis for this incident. Retain the stop and contact Maintenance Desk 240 with the instrument model, peak, three limits, active alarm IDs, and observed state. Request qualified verification of instrument validity and engineering review of protection applicability. No automatic parameter change or sensor substitution is authorized.

## Step 6: record restart blockers
ST02_SEALING: Apply REC-ST02-001. Record absent independent measurement, unconfirmed cause, missing corrective-work record, unresolved protection mismatch, and missing release approvals. The operator alone cannot clear these blockers. Leave the station stopped and log the handover attempt if assistance is unavailable. Do not claim cooling resolves the mismatch.

# ST04 Vibration Troubleshooting

## Scope and entry condition
Document ID: TRB-ST04-001. Revision: 1. Effective date: 2026-10-24. Owner: Kelvara Maintenance Engineering. Synthetic procedure for a trained lone operator responding to ST04_PACKAGING vibration alarms. Use EQ-ST04-001 for locations, ALM-ST04-001 for thresholds, and REC-ST04-001 for restart restrictions. Perform only external observations; detailed intrusive maintenance is not covered.

## Step 1: confirm machine state
At HMI-ST04, open Diagnostics for ST04_PACKAGING. Record the machine state, ST04_PACKAGING_SPD, measurement timestamp, and quality. Expected after a critical trip: state STOPPED_PROTECTIVE and speed 0.00 m/s, supported by fresh good-quality data. Confirm visually from outside the guard. If movement continues or an immediate hazard is present, use the local emergency stop and keep clear. If state or speed cannot be established, keep clear and contact Maintenance Desk 240. Do not proceed toward equipment to resolve missing telemetry.

## Step 2: preserve alarm evidence
At HMI-ST04 Alarm History, record the ST04_PACKAGING alarm instance ID, code, activation time, trigger measurement ID, and active/cleared status. Compare the trigger value against ALM-ST04-001. Acknowledge the displayed alarm only after recording it; acknowledgement is not a reset. For PKG-VIB-HH, retain the stop even if stopped vibration is now zero. If the live display disagrees with the recorded event, retain both records and report the discrepancy rather than selecting one silently.

## Step 3: check trend and data quality
Read the ST04_PACKAGING_VIB trend alongside ST04_PACKAGING_SPD and ST04_PACKAGING_CUR. Compare good-quality running readings at the same speed across the prior 60 minutes. Record the starting and ending vibration values and their difference. A rise greater than 0.05 mm/s supports MAINT-01. Do not include the stopped sample in that comparison. If timestamps, units, quality, or comparable operating conditions are missing, report that the trend cannot be established. Do not infer a confirmed bearing failure from the trend.

## Step 4: observe without entering
With ST04_PACKAGING stopped, remain at OBS-ST04-01 outside closed guards. Look through the inspection window for displaced trays, visible debris, or visible sensor-cable damage. Record each finding as observed, not observed, or not visible. Do not touch the bearing housing, reach through openings, remove material, or open guards. If smoke, burning smell, or another immediate hazard is present, withdraw and follow site emergency arrangements. If the view is blocked, record not visible; do not treat that as no obstruction.

## Step 5: review history and select the next action
Open ST04_PACKAGING Maintenance History and compare symptoms with HIST-ST04-001. Previous lubrication or sensor-mount faults are possibilities, not the diagnosis of this incident. For a critical alarm, or a visible defect, retain the stop and request qualified maintenance. For warning-only evidence, follow RULE-ST04-01's maintenance scheduling requirement; this procedure grants no independent restart permission. Do not apply the previous repair automatically. MAINT-01 inspection and lubrication require the qualified technician and approved isolation procedure described in EQ-ST04-001.

## Step 6: hand over and record the blocker
For ST04_PACKAGING, contact Maintenance Desk 240 with the incident ID, alarm instance, pre-stop peak, speed/current at that time, trend comparison, machine state, and external observations. State explicitly that the operator is alone. If no technician is available, leave the machine stopped and record maintenance pending. Follow REC-ST04-001 for release conditions. End the operator checklist with the current blocker; do not invent completed repairs, measurements, or approval.

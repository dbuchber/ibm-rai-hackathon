# ST04 Packaging Conveyor Equipment Guide

## Scope and document control
Document ID: EQ-ST04-001. Revision: 1. Effective date: 2026-10-24. Owner: Kelvara Maintenance Engineering. Applies to ST04_PACKAGING and production order PO-1005. This is fictional equipment and synthetic training documentation. Component locations and controls below are invented for this demo; they are not manufacturer instructions. The scenario supplements SOP-001, SOP-002, and SOP-003 without changing their alarm limits.

## Component locations
ST04_PACKAGING transfers sealed trays to the final packaging outlet. The operator position faces the outlet. The operator panel HMI-ST04 is outside the fixed guard on the outlet side. Main bearing BRG-ST04-01 is at the drive end, behind the fixed guard. Sensor ST04_PACKAGING_VIB, model VIB-4480, is mounted on that bearing housing. ST04_PACKAGING_SPD measures conveyor speed; ST04_PACKAGING_CUR measures motor current. These identifiers refer to the same sensors in the telemetry records.

## Operator controls and inspection points
ST04_PACKAGING HMI-ST04 has read-only Diagnostics, Alarm History, and Maintenance History pages, plus Stop and Alarm Acknowledge controls. The outside observation point OBS-ST04-01 faces the drive-end inspection window without entering a guarded area. A local emergency-stop button is beside HMI-ST04. Alarm acknowledgement records that the operator has seen an alarm; it does not clear the underlying fault, release an emergency stop, or authorize restart.

## Lone-worker scope
For ST04_PACKAGING, the scenario assumes a trained line operator is alone and may read diagnostics, record observations, and observe from OBS-ST04-01 with guards closed. The operator may not open guards, reach into the conveyor, remove trapped material, lubricate the bearing, open electrical panels, or perform a test run after a critical vibration trip alone. A stopped conveyor is not evidence of energy isolation. Intrusive work requires a qualified technician following the site's approved isolation procedure; that procedure is outside this dataset.

## Required resources
For external checks of ST04_PACKAGING, use HMI-ST04 and the incident log; no hand tools are required. Do not approach the drive to take manual readings. Record the sensor ID, timestamp, value, unit, quality flag, machine state, and whether each value was measured while running or stopped. Remote maintenance advice is available through the fictional internal Maintenance Desk extension 240; if unavailable, retain the stop and log the attempted contact. No response time or remote restart authority is promised.

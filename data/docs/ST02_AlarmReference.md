# ST02 Temperature Alarm Reference

## Scope and document control
Document ID: ALM-ST02-001. Revision: 1. Effective date: 2026-10-24. Owner: Kelvara Maintenance Engineering. Applies to ST02_SEALING. Fictional equipment details and synthetic training instructions; not manufacturer instructions. Existing iMAKS limits are retained. No intrusive repair or isolation sequence is supplied.

## SEAL-TMP-HI warning
ST02_SEALING: ST02_SEALING_TMP values greater than 195 degrees C and at most 210 degrees C activate fictional code SEAL-TMP-HI while the controller is running. RULE-ST02-01 requires temperature within 175 to 195 degrees C. A warning is not permission to operate outside that band. Apply TRB-ST02-001; do not wait for the critical trip when the operating band is exceeded.

## SEAL-TMP-HH critical trip
ST02_SEALING: A valid ST02_SEALING_TMP reading greater than 210 degrees C activates fictional code SEAL-TMP-HH. RULE-ST02-02 and SOP-002 require emergency stop of ST02_SEALING, ST03_LABELLING, and ST04_PACKAGING and inspection. An alarm record documents the controller request, not proof that all affected stations stopped. The supplied replay never exceeds 210 degrees C and contains no critical-trip event.

## Instrument limit advisory
ST02_SEALING: Fictional code SEAL-TMP-RANGE activates above the installed TMP-2210 continuous maximum of 200 degrees C and requests engineering review. It is a scenario-specific advisory, not an existing iMAKS critical rule. SPEC-ST02-001 explains the gap between the 210 degrees C critical threshold and the 200 degrees C continuous instrument rating. A numeric display outside the continuous rating is evidence of the controller report, not a verified accurate process temperature.

## Freshness and alarm lifecycle
ST02_SEALING: Use only records at or before the explicitly selected replay time. Fresh telemetry has good quality and age from 0 through 30 seconds. Good quality is the controller transport flag; it does not certify accuracy beyond the instrument rating. Alarms remain active until an explicit cleared lifecycle event exists. Cooling after stop and acknowledgement do not clear them. Missing or stale measurements block a recovery claim.

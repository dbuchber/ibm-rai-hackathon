# ST01 Low Pressure Troubleshooting

## Scope and document control
Document ID: TRB-ST01-001. Revision: 1. Effective date: 2026-10-24. Owner: Kelvara Maintenance Engineering. Applies to ST01_FILLING. Fictional equipment details and synthetic training instructions; not manufacturer instructions. Existing iMAKS limits are retained. No intrusive repair or isolation sequence is supplied.

## Step 1: confirm the stop
ST01_FILLING: At HMI-ST01 Diagnostics, record state, timestamp, quality, ST01_FILLING_PRS, and ST01_FILLING_FLW. After FILL-PRS-LL, expected replay state is STOPPED_QUALITY_HOLD and flow is 0.0 L/min. If state is missing or inconsistent, retain the hold and request assistance; do not approach process equipment to compensate for missing data. For an immediate hazard use the emergency stop and keep clear.

## Step 2: preserve the incident evidence
ST01_FILLING: In Alarm History, record instance IDs, codes, times, trigger samples, and whether alarms are still active. Record the last running pressure and flow separately from stopped readings. Compare them with ALM-ST01-001. Acknowledge only after recording; do not reset or resume filling. The replay first shows low pressure at 12:40 and the critical event at 13:00; it does not record that the five-minute inlet check was performed.

## Step 3: inspect the external inlet indicator
ST01_FILLING: From OBS-ST01-01 with the station stopped and guards closed, read the VLV-ST01-01 position indicator. If CLOSED, report a possible supply-path issue without opening the valve. If OPEN, record it and continue to the pump-status observation; an open indicator does not prove supply or filter condition. If UNKNOWN or not visible, record the missing observation and escalate. No actual valve-position observation is included in this incident dataset.

## Step 4: read pump status and look for external evidence
ST01_FILLING: At OBS-ST01-01 read the PMP-ST01-01 status lamp as normal, fault, or not visible. If fault, record the displayed code if readable from the HMI; do not reset motor protection. If normal, compare prior running pressure and flow while keeping the stop; normal status does not prove pump delivery. From outside the guard record visible leakage or abnormal accumulation as observed, not observed, or not visible. Do not touch fluid or open fittings. Pump status and leakage observations are not supplied for this incident.

## Step 5: assess the diagnostic branches
ST01_FILLING: If inlet indication is closed or unknown, qualified inspection of supply path and valve is required. If indication is open and pump status is fault, qualified pump/drive assessment is required. If indication is open with normal pump status but running pressure and flow were low, filter restriction, upstream supply loss, and pump delivery remain competing hypotheses. Without upstream or filter differential-pressure readings, do not select one as confirmed. Read HIST-ST01-001 for prior findings and its limits. Do not report that MAINT-04 duration is proven from sparse samples.

## Step 6: use the available support route
ST01_FILLING: Consult RES-ST01-001 at the same selected time. The usual specialist is off shift; the on-call service can receive a remote triage call, but attendance and arrival are unconfirmed. Contact the stated service route with pressure/flow evidence and missing observations. Keep the product and station on hold under REC-ST01-001. Stock availability alone is not permission to replace a part. If no response is obtained, record the attempted call and leave the hold in place.

# ST01 Pressure and Flow Alarm Reference

## Scope and document control
Document ID: ALM-ST01-001. Revision: 1. Effective date: 2026-10-24. Owner: Kelvara Maintenance Engineering. Applies to ST01_FILLING. Fictional equipment details and synthetic training instructions; not manufacturer instructions. Existing iMAKS limits are retained. No intrusive repair or isolation sequence is supplied.

## FILL-PRS-LO warning
ST01_FILLING: A valid running ST01_FILLING_PRS reading below 3.3 bar and at least 3.0 bar activates fictional FILL-PRS-LO. RULE-ST01-03 requires inlet-valve inspection within five minutes. For a lone operator, the permitted first inspection is the external position indicator in EQ-ST01-001. If that time window has elapsed, record the overdue check; do not report it as completed.

## FILL-PRS-LL critical
ST01_FILLING: A valid running ST01_FILLING_PRS reading below 3.0 bar activates fictional FILL-PRS-LL. SOP-002 specifies inspect and notify maintenance. The simulated controller additionally requests a quality-hold stop; that is a fictional scenario policy, not an iMAKS emergency-stop rule. Confirm actual machine state through telemetry. Acknowledgement does not clear the alarm or authorize product release.

## Flow context and trend
ST01_FILLING: RULE-ST01-01 requires ST01_FILLING_FLW between 112 and 128 L/min; SOP-002 has a low critical boundary of 105 L/min. Flow below 112 but at least 105 L/min activates fictional FILL-FLW-LO in this replay. MAINT-04 requires pressure below 3.3 bar for more than fifteen minutes before inspecting filter and pump. Sparse low samples twenty minutes apart do not prove continuous low pressure; confirm duration from a complete trend or report it unknown. Pressure and flow falling together cannot establish the root cause.

## Freshness and lifecycle
ST01_FILLING: At the selected replay time, use only observations at or before that time. Good-quality telemetry is fresh for thirty seconds inclusive. Each alarm instance remains active until an explicit cleared lifecycle event appears. Stopped zero flow is expected and cannot establish normal delivery. Falling stopped pressure does not establish depressurization, and old nominal readings cannot authorize restart.

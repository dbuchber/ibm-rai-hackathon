# ST04 Vibration Alarm Reference

## Scope and document control
Document ID: ALM-ST04-001. Revision: 1. Effective date: 2026-10-24. Owner: Kelvara Maintenance Engineering. Synthetic demo alarm-code mapping for ST04_PACKAGING and ST04_PACKAGING_VIB. Limits reproduce the existing graph's SOP-001 and SOP-002 values; alarm codes are fictional additions.

## Warning: PKG-VIB-HI
For ST04_PACKAGING_VIB, PKG-VIB-HI activates when a valid running vibration measurement is greater than 0.20 mm/s and at most 0.35 mm/s. RULE-ST04-01 requires maintenance within 24 hours. An active critical alarm takes precedence over this warning response. A warning alone does not establish a bearing defect or authorize maintenance work by an operator. Follow TRB-ST04-001 to establish the current state.

## Critical: PKG-VIB-HH
For ST04_PACKAGING_VIB, PKG-VIB-HH activates when a valid running vibration measurement is greater than 0.35 mm/s. RULE-ST04-02 specifies emergency stop and bearing inspection. In this simulated controller, the event requests a protective stop and latches the critical alarm. Confirm the actual stopped state on HMI-ST04; an alarm event alone does not prove that the machine stopped. If motion continues or an immediate hazard is visible, use the local emergency stop and keep clear. Acknowledgement does not permit restart.

## Trend advisory and uncertainty
MAINT-01 on ST04_PACKAGING is the SOP-003 maintenance action to inspect and lubricate the main bearing when ST04_PACKAGING_VIB drifts upward by more than 0.05 mm/s over 60 minutes. Compare valid running readings at matching speed. The advisory identifies a maintenance need, not a confirmed root cause. Stopped readings must not be used to establish bearing recovery. Vibration can also reflect a loose sensor or a mechanical obstruction; this dataset does not confirm either.

## Freshness and alarm lifecycle
For the ST04_PACKAGING demo replay, evaluate records only at the explicitly selected scenario time. A telemetry sample is fresh if its age is between 0 and 30 seconds inclusive and quality is good. Do not use future records. A pre-stop peak can explain the trip but is not a current running measurement. An alarm remains active until an explicit cleared lifecycle record exists; a zero stopped vibration reading does not clear it. Missing, stale, or bad-quality evidence blocks a recovery claim. Consult REC-ST04-001 for restart conditions.

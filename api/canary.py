"""Canaries against automation bias: planted, obviously false proposals. Never written to the graph.

State lives on the server only; whether an item is a canary is not sent before the decision."""

from __future__ import annotations

import random
from collections import deque
from datetime import datetime, timezone
from typing import Callable

from api.store import CurationStore
from contracts.ids import edge_id, pred_iri, proposal_id
from contracts.models import AuditEntry, CanaryAlert, Proposal, Triple

SUPERVISOR = "Quality lead (mock)"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class CanaryGuard:
    def __init__(self, store: CurationStore, model: str, streak: int = 4, fast_secs: float = 3.0,
                 clock: Callable[[], float] = None, rng: random.Random | None = None):
        import time
        self.store, self.model = store, model
        self.streak_limit, self.fast_secs = streak, fast_secs
        self.clock = clock or time.monotonic
        self.rng = rng or random.Random()
        self.audit: list[AuditEntry] = []
        self.canary: Proposal | None = None
        self._streak = 0
        self._durations: deque[float] = deque(maxlen=4)
        self._since_pass: list[str] = []      # proposals approved since the last passed canary
        self._mark = self.clock()             # last time the user was shown or decided something

    def log(self, kind: str, detail: str, pid: str | None = None) -> None:
        self.audit.append(AuditEntry(ts=_now(), kind=kind, proposal_id=pid, detail=detail))

    # --- triggering -------------------------------------------------------
    def _triggered(self) -> bool:
        if self._streak >= self.streak_limit:
            return True
        return len(self._durations) >= 3 and sum(self._durations) / len(self._durations) < self.fast_secs

    def _make(self) -> Proposal | None:
        nodes = list(self.store._nodes.values())
        stations = [n for n in nodes if n.cls == "Station"]
        customers = [n for n in nodes if n.cls == "Customer"]
        if not stations or not customers:
            return None
        s = next((n for n in stations if n.id.endswith("ST02_SEALING")), stations[0])
        o = customers[0]
        p = pred_iri("supplied_by")
        if edge_id(s.id, p, o.id) in self.store._edges:
            return None
        chunk = next((n.id for n in nodes if n.cls == "Chunk"), None)
        return Proposal(
            kind="edge", triple=Triple(s=s.id, p=p, o=o.id),
            rationale=f"The supplier quality agreement names {o.label} as the supplier of the equipment at {s.label}.",
            evidence_chunk_id=chunk,
            quote=f"{o.label} supplies the equipment of the sealing line under the 2026 framework agreement.",
            id=proposal_id("edge", triple=(s.id, p, o.id)), confidence=0.82,
            proposed_by=f"llm:{self.model}", status="proposed")

    def listing(self, real: list[Proposal]) -> list[Proposal]:
        """Called on GET /api/proposals: plants a canary when due and returns the list to show."""
        self._mark = self.clock()
        if self.canary is None and self._triggered():
            self.canary = self._make()
            if self.canary is not None:
                self.log("canary_planted", "Canary proposal planted after fast or repeated approvals.", self.canary.id)
        out = list(real)
        if self.canary is not None:
            out.insert(self.rng.randrange(min(3, len(out) + 1)), self.canary)
        return out

    # --- decisions --------------------------------------------------------
    def note_decision(self, pid: str, decision: str) -> None:
        now = self.clock()
        self._durations.append(now - self._mark)
        self._mark = now
        self._streak = self._streak + 1 if decision == "approve" else 0
        if decision == "approve":
            if pid not in self._since_pass:
                self._since_pass.append(pid)
        elif pid in self._since_pass:
            self._since_pass.remove(pid)
        self.log("decision", f"{decision} by user", pid)

    def is_canary(self, pid: str) -> bool:
        return self.canary is not None and self.canary.id == pid

    def decide_canary(self, decision: str, revert: Callable[[str], None]) -> Proposal:
        c = self.canary
        self._mark = self.clock()
        self.log("decision", f"{decision} by user", c.id)
        self.canary = None
        self._streak = 0
        self._durations.clear()
        if decision != "approve":
            self._since_pass.clear()
            self.log("canary_passed", "Planted canary was rejected or flagged.", c.id)
            return c.model_copy(update={"status": "rejected"})
        reverted = list(self._since_pass)
        for pid in reverted:
            revert(pid)
            self.log("reverted", "Approval since the last passed canary set back to proposed.", pid)
        self._since_pass.clear()
        self.log("canary_failed", "Planted canary was approved. Nothing was written.", c.id)
        self.log("supervisor_notified", f"{SUPERVISOR} notified about a missed canary and {len(reverted)} reverted approvals.", c.id)
        alert = CanaryAlert(
            message="That proposal was a planted test and is factually wrong. It was not written to the graph. "
                    f"{len(reverted)} approvals since the last check were set back to proposed.",
            reverted=reverted, supervisor_notified=SUPERVISOR)
        return c.model_copy(update={"status": "proposed", "alert": alert})

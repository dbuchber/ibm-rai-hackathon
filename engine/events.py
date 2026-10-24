"""Turns payload models into numbered, timestamped C3 events, each preceded by its demo beat."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from contracts.models import (
    AnswerEvent, AnswerPayload, BaselineEvent, BaselinePayload, BeatEvent, BeatPayload, Event, EvidenceEvent,
    EvidencePayload, RunFinished, RunFinishedEvent, RunStarted, RunStartedEvent, SeedsEvent, SeedsPayload,
    StepEvent, StepPayload, StrategyEvent, StrategyPayload,
)
from engine.beats import Director

_EVENT_FOR = {
    RunStarted: RunStartedEvent, StrategyPayload: StrategyEvent, SeedsPayload: SeedsEvent,
    StepPayload: StepEvent, AnswerPayload: AnswerEvent, EvidencePayload: EvidenceEvent,
    BaselinePayload: BaselineEvent, BeatPayload: BeatEvent, RunFinished: RunFinishedEvent,
}


class Emitter:
    def __init__(self, run_id: str, sink: Callable[[Event], None]):
        self.run_id, self.sink, self.seq = run_id, sink, 0
        self.director = Director()

    def __call__(self, payload) -> None:
        if not isinstance(payload, BeatPayload) and (beat := self.director.beat(payload)):
            self._emit(beat)
        self._emit(payload)

    def _emit(self, payload) -> None:
        ev = _EVENT_FOR[type(payload)](
            run_id=self.run_id, seq=self.seq, payload=payload,
            ts=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        self.seq += 1
        self.sink(ev)

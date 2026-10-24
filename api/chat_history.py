"""Multi-turn chat memory: the last turns per X-Chat-Session, in memory only (like the chat canary).

Turns are recorded from the engine's own events, before the chat canary may falsify the answer, so a planted
false fact never becomes the context a follow-up is answered from."""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Callable

from contracts.models import Event
from engine.history import Turn

WINDOW = 3
MAX_SESSIONS = 1000   # a room of visitors, not a database: the least recently used session is forgotten


class ChatHistory:
    def __init__(self, window: int = WINDOW, max_sessions: int = MAX_SESSIONS):
        self.window, self.max_sessions = window, max_sessions
        self.lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        self.sessions: OrderedDict[str, list[Turn]] = OrderedDict()

    def turns(self, session: str | None) -> list[Turn]:
        """The session's last turns, oldest first; [] without a session."""
        with self.lock:
            return list(self.sessions.get(session or "", []))

    def _add(self, session: str, turn: Turn) -> None:
        with self.lock:
            turns = self.sessions.pop(session, [])
            self.sessions[session] = [*turns, turn][-self.window:]
            while len(self.sessions) > self.max_sessions:
                self.sessions.popitem(last=False)

    def capture(self, session: str | None, question: str, sink: Callable[[Event], None],
                alive: Callable[[], bool] = lambda: True) -> Callable[[Event], None]:
        """Wraps the engine's sink: a run that finishes ok becomes the session's newest turn.

        `alive` false = the server already closed the run (timeout): the user never saw it, so it is no turn."""
        if not session:
            return sink
        seen: dict = {}

        def out(ev: Event) -> None:
            if ev.type == "answer":
                seen["answer"] = ev.payload.text
            elif ev.type == "evidence":
                seen["evidence"] = tuple(n.id for n in ev.payload.nodes)
            elif ev.type == "run.finished" and ev.payload.status == "ok" and "answer" in seen and alive():
                self._add(session, Turn(question=question, answer=seen["answer"],
                                        evidence=seen.get("evidence", ())))
            sink(ev)
        return out

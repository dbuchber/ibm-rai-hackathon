"""Rewrites stored runs with demo beats (engine/beats.py) without re-running the LLM. Idempotent.

    PYTHONPATH=. uv run python scripts/add_beats.py runs/*.jsonl contracts/fixtures/run_*.jsonl
"""

from __future__ import annotations

import sys
from pathlib import Path

from contracts.models import BeatEvent, EventAdapter
from engine.beats import Director


def add_beats(lines: list[str]) -> list[str]:
    director, out = Director(), []
    for line in lines:
        ev = EventAdapter.validate_json(line)
        if ev.type == "beat":
            continue
        if beat := director.beat(ev.payload):
            out.append(BeatEvent(run_id=ev.run_id, seq=0, ts=ev.ts, payload=beat))
        out.append(ev)
    return [e.model_copy(update={"seq": i}).model_dump_json() for i, e in enumerate(out)]


if __name__ == "__main__":
    for p in map(Path, sys.argv[1:]):
        p.write_text("\n".join(add_beats([l for l in p.read_text().splitlines() if l.strip()])) + "\n")
        print("beats:", p)

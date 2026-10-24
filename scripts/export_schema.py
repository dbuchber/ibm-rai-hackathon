"""Exports JSON Schema for the UI (contracts/schema/). Run after any change to contracts/models.py."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from contracts import models as m

OUT = Path(__file__).resolve().parent.parent / "contracts" / "schema"

SCHEMAS = {
    "Event": m.EventAdapter,
    "GraphExport": TypeAdapter(m.GraphExport),
    "Proposal": TypeAdapter(m.Proposal),
    "CreateProposal": TypeAdapter(m.CreateProposal),
    "AuditEntry": TypeAdapter(m.AuditEntry),
    "RunSummary": TypeAdapter(m.RunSummary),
    "CreateRun": TypeAdapter(m.CreateRun),
    "ModelInfo": TypeAdapter(list[m.ModelInfo]),
    "CreateRunResponse": TypeAdapter(m.CreateRunResponse),
    "ProposalDecision": TypeAdapter(m.ProposalDecision),
    "ChatCanaryReveal": TypeAdapter(m.ChatCanaryReveal),
    "Feedback": TypeAdapter(m.Feedback),
    "FeedbackResponse": TypeAdapter(m.FeedbackResponse),
    "SourceOpened": TypeAdapter(m.SourceOpened),
}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, adapter in SCHEMAS.items():
        schema = adapter.json_schema()
        schema["title"] = name
        (OUT / f"{name}.json").write_text(json.dumps(schema, indent=2, ensure_ascii=False))
    print(f"wrote {len(SCHEMAS)} schemas")

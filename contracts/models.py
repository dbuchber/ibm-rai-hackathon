"""Single source of truth for every shape that crosses a stream boundary (spec: Interfaces C1-C5).

Change this file only through the coordinator, then run `scripts/export_schema.py`.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter, model_validator

GraphName = Literal["approved", "proposed", "rejected"]


# --- C1/C2: graph -----------------------------------------------------------

class Node(BaseModel):
    id: str                      # full IRI, see contracts.ids.node_iri
    cls: str                     # ontology class local name, e.g. "Station"
    label: str
    description: str | None = None
    text: str | None = None      # Chunk only
    props: dict[str, str | float | int] = {}   # other ont: literals, e.g. critHi


class ScoredNode(Node):
    score: float


class Edge(BaseModel):
    id: str                      # contracts.ids.edge_id(s, p, o)
    s: str
    p: str                       # predicate IRI; display with contracts.ids.local_name
    o: str
    graph: GraphName = "approved"


class GraphExport(BaseModel):
    nodes: list[Node]
    edges: list[Edge]


class Provenance(BaseModel):
    edge_id: str
    source: str                  # e.g. "imaks:edges.csv#12", "SOP-003.pdf#p1"
    creator: str                 # "script" | "analyst" | "llm:<model>"
    status: GraphName
    created_at: str              # ISO 8601


# --- C3: run events ---------------------------------------------------------

class RunStarted(BaseModel):
    question: str
    model: str
    mode: Literal["replay", "live"]
    mock: bool = False


class StrategyPayload(BaseModel):
    question_type: str
    rationale: str
    allowed_predicates: list[str]    # predicate IRIs
    max_depth: int
    prompt: str


class SeedsPayload(BaseModel):
    nodes: list[ScoredNode]


class Decision(BaseModel):
    edge_id: str
    verdict: Literal["follow", "prune"]
    reason: str


class StepPayload(BaseModel):
    n: int                           # 1-based
    frontier: list[Edge]
    nodes: list[Node]                # endpoints of frontier edges, so the UI never looks anything up
    decisions: list[Decision]
    sufficient: bool


class Citation(BaseModel):
    edge_id: str | None = None
    chunk_id: str | None = None      # Chunk node IRI


class Contradiction(BaseModel):
    a: str                           # node IRI (e.g. a chunk or document)
    b: str
    note: str


class Canary(BaseModel):
    """A deliberately false statement planted to detect automation bias. Never written to the graph."""
    claim: str                       # the false statement as shown
    truth: str                       # what the approved graph actually says


class AnswerPayload(BaseModel):
    text: str
    justification: str
    citations: list[Citation]
    contradictions: list[Contradiction] = []
    canary: Canary | None = None     # set only in planted chat canaries (click mock)


class EvidencePayload(BaseModel):
    """The graph that led to the result: cited edges plus the walked path from the seeds."""
    nodes: list[Node]
    edges: list[Edge]


class BaselinePayload(BaseModel):
    chunks: list[ScoredNode]
    answer: str
    illustrative: bool = False


class BeatPayload(BaseModel):
    """Stage direction for the animated demo. Sent right before the event it introduces; carries no new facts."""
    act: Literal["question", "strategy", "seeds", "traverse", "answer", "evidence", "contrast"]
    focus: list[str]                 # node IRIs the camera should frame (chunks included, fold them like highlights)
    caption: str                     # one plain sentence for viewers without a presenter
    emphasis: Literal["follow", "prune", "enough", "contradiction", "canary"] | None = None
    step: int | None = None          # StepPayload.n for act="traverse"


class RunFinished(BaseModel):
    status: Literal["ok", "error"]
    error: str | None = None


class _Envelope(BaseModel):
    run_id: str
    seq: int                         # 0-based, strictly increasing
    ts: str                          # ISO 8601


class RunStartedEvent(_Envelope):
    type: Literal["run.started"] = "run.started"
    payload: RunStarted


class StrategyEvent(_Envelope):
    type: Literal["strategy"] = "strategy"
    payload: StrategyPayload


class SeedsEvent(_Envelope):
    type: Literal["seeds"] = "seeds"
    payload: SeedsPayload


class StepEvent(_Envelope):
    type: Literal["step"] = "step"
    payload: StepPayload


class AnswerEvent(_Envelope):
    type: Literal["answer"] = "answer"
    payload: AnswerPayload


class EvidenceEvent(_Envelope):
    type: Literal["evidence"] = "evidence"
    payload: EvidencePayload


class BaselineEvent(_Envelope):
    type: Literal["baseline"] = "baseline"
    payload: BaselinePayload


class BeatEvent(_Envelope):
    type: Literal["beat"] = "beat"
    payload: BeatPayload


class RunFinishedEvent(_Envelope):
    type: Literal["run.finished"] = "run.finished"
    payload: RunFinished


Event = Annotated[
    Union[
        RunStartedEvent, StrategyEvent, SeedsEvent, StepEvent,
        AnswerEvent, EvidenceEvent, BaselineEvent, BeatEvent, RunFinishedEvent,
    ],
    Field(discriminator="type"),
]
EventAdapter: TypeAdapter[Event] = TypeAdapter(Event)


# --- C4: HTTP ---------------------------------------------------------------

class RunSummary(BaseModel):
    run_id: str
    question: str
    mock: bool


class CreateRun(BaseModel):
    """POST /api/runs body. The request also needs the header X-Invite-Code (403 without a valid one)."""
    question: str


class CreateRunResponse(BaseModel):
    run_id: str


class ProposalDecision(BaseModel):
    decision: Literal["approve", "reject", "flag"]   # flag = "this is wrong", report it


class CanaryAlert(BaseModel):
    """Returned with the decision that approved a planted canary."""
    message: str
    reverted: list[str]              # proposal IDs approved since the last passed canary, now back to "proposed"
    supervisor_notified: str         # who was notified, e.g. "Quality lead (mock)"


class AuditEntry(BaseModel):
    ts: str
    kind: Literal["decision", "canary_planted", "canary_passed", "canary_failed", "reverted", "supervisor_notified"]
    proposal_id: str | None = None
    detail: str


# --- C5: curation -----------------------------------------------------------

class Triple(BaseModel):
    s: str
    p: str
    o: str


class NodeSpec(BaseModel):
    cls: str                         # existing ontology class local name, e.g. "Supplier"
    local_id: str                    # IRI = contracts.ids.node_iri(cls, local_id)
    label: str
    description: str | None = None


class PredicateSpec(BaseModel):
    name: str                        # snake_case; IRI = contracts.ids.pred_iri(name)
    description: str                 # "Domain verb Range.", like the ontology comments
    domain: str | None = None        # class local name
    range: str | None = None


ProposalKind = Literal["edge", "node", "predicate"]


class _ProposalBody(BaseModel):
    """Exactly the field matching `kind` is set."""
    kind: ProposalKind = "edge"
    triple: Triple | None = None
    node: NodeSpec | None = None
    predicate: PredicateSpec | None = None
    rationale: str
    evidence_chunk_id: str | None = None   # Chunk IRI the proposal is based on, if any
    quote: str | None = None

    @model_validator(mode="after")
    def _payload_matches_kind(self):
        given = {k for k in ("triple", "node", "predicate") if getattr(self, k) is not None}
        expected = {"edge": "triple", "node": "node", "predicate": "predicate"}[self.kind]
        if given != {expected}:
            raise ValueError(f"kind={self.kind} needs exactly '{expected}', got {sorted(given)}")
        return self


class CreateProposal(_ProposalBody):
    """POST /api/proposals body: a proposal entered by a user in the curation screen."""


class Proposal(_ProposalBody):
    id: str                          # contracts.ids.proposal_id(kind, ...)
    confidence: float | None = None  # None for proposals entered by people
    proposed_by: str                 # "llm:<model>" | "analyst-seed" | "user"
    status: GraphName = "proposed"
    # Only on the response of POST /api/proposals/{id}. Whether a proposal is a canary is never sent before the decision.
    alert: CanaryAlert | None = None

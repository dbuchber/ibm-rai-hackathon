"""Single source of truth for every shape that crosses a stream boundary (spec: Interfaces C1-C5).

Change this file only through the coordinator, then run `scripts/export_schema.py`.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter

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


class AnswerPayload(BaseModel):
    text: str
    justification: str
    citations: list[Citation]
    contradictions: list[Contradiction] = []


class EvidencePayload(BaseModel):
    """The graph that led to the result: cited edges plus the walked path from the seeds."""
    nodes: list[Node]
    edges: list[Edge]


class BaselinePayload(BaseModel):
    chunks: list[ScoredNode]
    answer: str
    illustrative: bool = False


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


class RunFinishedEvent(_Envelope):
    type: Literal["run.finished"] = "run.finished"
    payload: RunFinished


Event = Annotated[
    Union[
        RunStartedEvent, StrategyEvent, SeedsEvent, StepEvent,
        AnswerEvent, EvidenceEvent, BaselineEvent, RunFinishedEvent,
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
    question: str


class CreateRunResponse(BaseModel):
    run_id: str


class ProposalDecision(BaseModel):
    decision: Literal["approve", "reject"]


# --- C5: curation -----------------------------------------------------------

class Triple(BaseModel):
    s: str
    p: str
    o: str


class Proposal(BaseModel):
    id: str                          # = edge_id(s, p, o)
    triple: Triple
    rationale: str
    evidence_chunk_id: str
    quote: str
    confidence: float
    proposed_by: str                 # "llm:<model>" | "analyst-seed"
    status: GraphName = "proposed"

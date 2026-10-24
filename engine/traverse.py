"""Stepwise traversal: at every hop the LLM judges each candidate edge and whether the evidence suffices.

Ported from the BA hybrid traversal (frontier -> relevance check -> expand), with the enterprise-specific
strategy whitelist and a per-edge verdict instead of a per-subgraph score.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal

from pydantic import BaseModel

from contracts.ids import local_name
from contracts.models import Decision, Edge, Node, SeedsPayload, StepPayload, StrategyPayload
from contracts.store import GraphStore
from engine import embed, llm
from engine.history import with_context
from engine.llm import LLMFormatError

FRONTIER_CAP = 25
TEXT_PREVIEW = 160

SYSTEM = """You traverse an enterprise knowledge graph step by step to collect evidence for a question. You never answer the question here.
Each step you see the question, the strategy guidance, the facts collected so far and a list of candidate edges (fact triples) that touch the current frontier.
For EVERY candidate edge decide:
- "follow": the edge leads towards information needed for the question, or is itself needed evidence;
- "prune": it is irrelevant or a detour.
Every part of the question must be covered: if it asks who supplies, owns, operates or is authorised, follow the edge whose predicate answers that part (e.g. supplied_by, authorized_for) as soon as it appears. For questions about limits or ratings, the datasheet and SOP passages (Chunk nodes) that mention the relevant device, sensor model or station are essential: follow `mentions` and `has_chunk` edges that lead to them. Be generous: when an edge could lead to a rule, limit, document passage, supplier or owner relevant to the question, follow it. Prune only edges that are clearly unrelated. Rules and document chunks (Chunk nodes carry the SOP/datasheet text) are the most valuable evidence for safety or limit questions.
Then decide `sufficient`: true only if the facts collected so far PLUS the edges you follow now contain everything needed to answer the question (including documents/rules that state limits, and the supplier or owner if asked). If you follow edges that lead to nodes you still need to read, sufficient is false.
Reply with one JSON object: {"decisions": [{"edge_id": "...", "verdict": "follow"|"prune", "reason": "<max 8 words>"}], "sufficient": true|false}
Use the edge ids exactly as given in brackets."""


class _Dec(BaseModel):
    edge_id: str
    verdict: Literal["follow", "prune"]
    reason: str = ""


class _StepOut(BaseModel):
    decisions: list[_Dec]
    sufficient: bool = False


@dataclass
class Walk:
    seeds: list[str]
    followed: list[str] = field(default_factory=list)           # edge ids the LLM chose to follow, in order
    edges: dict[str, Edge] = field(default_factory=dict)         # explored: every frontier edge shown to the LLM
    nodes: dict[str, Node] = field(default_factory=dict)         # explored nodes
    sufficient: bool = False


def _fmt_node(n: Node) -> str:
    extra = ""
    if n.text:
        extra = f': "{n.text[:TEXT_PREVIEW]}…"'
    elif n.description:
        extra = f": {n.description}"
    return f"{n.label} ({n.cls}){extra}"


def _fmt_edge(e: Edge, nodes: dict[str, Node]) -> str:
    return f"[{e.id}] {nodes[e.s].label} — {local_name(e.p)} — {nodes[e.o].label}"


def _node(store: GraphStore, walk: Walk, iri: str) -> Node:
    if iri not in walk.nodes:
        walk.nodes[iri] = store.node(iri)
    return walk.nodes[iri]


def walk(question: str, store: GraphStore, strategy: StrategyPayload, seeds: SeedsPayload, model: str,
         emit: Callable, context: str = "") -> Walk:
    w = Walk(seeds=[n.id for n in seeds.nodes])
    for i in w.seeds:
        _node(store, w, i)
    allowed = set(strategy.allowed_predicates)
    current = list(w.seeds)
    seen_nodes = set(current)
    facts: list[str] = [f"Entry node: {_fmt_node(w.nodes[i])}" for i in w.seeds]

    for n in range(1, strategy.max_depth + 1):
        frontier: dict[str, Edge] = {}
        for nid in current:
            for e in store.neighbors(nid, allowed):
                if e.id not in w.edges and e.id not in frontier:
                    frontier[e.id] = e
        if not frontier:
            break
        cands = list(frontier.values())
        for e in cands:
            _node(store, w, e.s)
            _node(store, w, e.o)
        if len(cands) > FRONTIER_CAP:
            sims = embed.rank(question, [_fmt_edge(e, w.nodes) for e in cands])
            cands = [e for _, e in sorted(zip(sims, cands), key=lambda t: -t[0])[:FRONTIER_CAP]]
        for e in cands:
            w.edges[e.id] = e

        listing = "\n".join(_fmt_edge(e, w.nodes) for e in cands)
        nodes_in = {i: w.nodes[i] for e in cands for i in (e.s, e.o)}
        detail = "\n".join(f"- {_fmt_node(x)}" for x in nodes_in.values())
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": with_context(context,
                f"Question: {question}\n\nStrategy guidance ({strategy.question_type}): {strategy.prompt}\n\n"
                f"Facts collected so far:\n" + "\n".join(facts) +
                f"\n\nNodes in the candidate edges:\n{detail}\n\nCandidate edges (step {n} of max {strategy.max_depth}):\n{listing}")},
        ]
        failed, cand_ids = False, {e.id for e in cands}
        for _try in range(2):   # a valid-but-empty answer (no usable edge ids) is retried too
            try:
                out = llm.complete_json(messages, model, _StepOut)
            except LLMFormatError:
                out, failed = _StepOut(decisions=[], sufficient=True), True
                break
            for d in out.decisions:
                d.edge_id = d.edge_id.strip().strip("[]")
            if sum(d.edge_id in cand_ids for d in out.decisions) >= max(1, len(cands) // 2):
                break
        by_id = {d.edge_id: d for d in out.decisions if d.edge_id in cand_ids}
        decisions = [
            Decision(edge_id=e.id,
                     verdict=by_id[e.id].verdict if e.id in by_id else "prune",
                     reason=by_id[e.id].reason if e.id in by_id else "Step evaluation failed (unusable LLM output); pruned." if failed else "No verdict returned; pruned.")
            for e in cands
        ]
        emit(StepPayload(n=n, frontier=cands, nodes=list(nodes_in.values()), decisions=decisions,
                         sufficient=out.sufficient))

        nxt: list[str] = []
        for d in decisions:
            if d.verdict != "follow":
                continue
            e = w.edges[d.edge_id]
            w.followed.append(e.id)
            facts.append(f"{_fmt_edge(e, w.nodes)}")
            for iri in (e.s, e.o):
                if iri not in seen_nodes:
                    seen_nodes.add(iri)
                    nxt.append(iri)
        w.sufficient = out.sufficient
        if out.sufficient:
            break
        current = nxt
        if not current:
            break
    return w

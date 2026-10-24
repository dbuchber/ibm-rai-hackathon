"""Paired output (answer + justification) citing edge and chunk IDs, plus contradictions."""

from __future__ import annotations

from pydantic import BaseModel

from contracts.ids import local_name
from contracts.models import AnswerPayload, Citation, Contradiction
from contracts.store import GraphStore
from engine import llm
from engine.llm import LLMFormatError
from engine.traverse import Walk

INSUFFICIENT = "Not enough evidence in the approved graph to answer this question."

SYSTEM = """You answer questions about an industrial plant using ONLY the facts below, taken from a human-curated knowledge graph. Do not use outside knowledge.
Facts are triples written `[edge_id] subject — predicate — object`, and document passages written `{chunk_id} text`.
Reply with one JSON object:
{"text": "<the answer, 2-4 sentences, concrete values and names>",
 "justification": "<which facts support it and how they connect>",
 "citations": ["<edge_id or chunk_id exactly as given>", ...],
 "contradictions": [{"a": "<chunk_id>", "b": "<chunk_id>", "note": "<what disagrees, with the numbers>"}]}
Rules: cite every edge and passage the answer relies on, using ids exactly as given. If two passages give conflicting values or limits (for example an SOP allows more than a datasheet rates), report it in `contradictions` and say so in the answer instead of picking one silently. If the facts do not suffice, say so in `text` and leave citations empty."""


class _Out(BaseModel):
    text: str
    justification: str = ""
    citations: list[str] = []
    contradictions: list[dict] = []


def context_for(walk: Walk, store: GraphStore) -> tuple[str, set[str], set[str]]:
    """Facts shown to the answer model: followed triples plus texts of chunk nodes reached."""
    lines, edge_ids = [], set(walk.followed)
    for eid in walk.followed:
        e = walk.edges[eid]
        lines.append(f"[{eid}] {walk.nodes[e.s].label} — {local_name(e.p)} — {walk.nodes[e.o].label}")
    chunks = {i for i, n in walk.nodes.items() if n.cls == "Chunk" and n.text and any(
        i in (walk.edges[e].s, walk.edges[e].o) for e in walk.followed)}
    for cid in sorted(chunks):
        n = walk.nodes[cid]
        lines.append(f"{{{cid}}} {n.label}: {n.text}")
    for nid in walk.seeds + [i for e in walk.followed for i in (walk.edges[e].s, walk.edges[e].o)]:
        n = walk.nodes[nid]
        if n.description and n.cls != "Chunk":
            lines.append(f"(note) {n.label}: {n.description}")
    return "\n".join(dict.fromkeys(lines)), edge_ids, chunks


def answer(question: str, walk: Walk, store: GraphStore, model: str) -> AnswerPayload:
    if not walk.followed:
        return AnswerPayload(text=INSUFFICIENT, justification="The traversal found no approved facts relevant to the question.",
                             citations=[])
    context, edge_ids, chunk_ids = context_for(walk, store)
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"Question: {question}\n\nFacts:\n{context}"}]
    try:
        out = llm.complete_json(messages, model, _Out)
    except LLMFormatError:
        return AnswerPayload(text=INSUFFICIENT, justification="The answer step returned unusable output.", citations=[])
    cites = []
    for c in out.citations:
        c = c.strip().strip("[]{}")
        if c in edge_ids:
            cites.append(Citation(edge_id=c))
        elif c in chunk_ids:
            cites.append(Citation(chunk_id=c))
    cites = list({(c.edge_id, c.chunk_id): c for c in cites}.values())
    contras = [Contradiction(a=d["a"].strip("[]{}"), b=d["b"].strip("[]{}"), note=d.get("note", ""))
               for d in out.contradictions
               if isinstance(d, dict) and d.get("a", "").strip("[]{}") in chunk_ids and d.get("b", "").strip("[]{}") in chunk_ids]
    return AnswerPayload(text=out.text, justification=out.justification, citations=cites, contradictions=contras)

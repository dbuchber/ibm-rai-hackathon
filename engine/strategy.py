"""Strategy step: the LLM classifies the question and picks which predicates the traversal may follow."""

from __future__ import annotations

from pydantic import BaseModel

from contracts.ids import local_name
from contracts.models import StrategyPayload
from engine import llm
from engine.llm import LLMFormatError

FALLBACK_DEPTH = 3
MAX_DEPTH = 5

SYSTEM = """You plan how to search an enterprise knowledge graph (a digital twin of a packaging plant, its company, suppliers, sensors, rules and documents) to answer a question.
You do NOT answer the question. You decide a traversal strategy:
- question_type: a short label, e.g. "order -> asset -> documents", "rule lookup", "supplier trace".
- rationale: one or two sentences on why these relations matter for this question.
- allowed_predicates: the relations the traversal may follow, chosen ONLY from the list given. Pick the few that matter; do not allow everything.
- max_depth: how many hops are needed (1-5).
- prompt: one or two sentences of guidance for the agent that will judge each hop (what to look for, what to ignore).
Reply with a single JSON object with exactly these keys."""


class _Plan(BaseModel):
    question_type: str
    rationale: str
    allowed_predicates: list[str]
    max_depth: int = FALLBACK_DEPTH
    prompt: str = ""


def _resolve(name: str, known: dict[str, str]) -> str | None:
    """Accept a full IRI or the local name; None if unknown."""
    if name in known.values():
        return name
    return known.get(local_name(name.strip()))


def plan(question: str, predicates: list[tuple[str, str]], model: str) -> StrategyPayload:
    known = {local_name(iri): iri for iri, _ in predicates}
    listing = "\n".join(f"- {local_name(iri)}: {desc}" for iri, desc in predicates)
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Question: {question}\n\nAvailable predicates:\n{listing}"},
    ]
    try:
        p = llm.complete_json(messages, model, _Plan)
    except LLMFormatError:
        return StrategyPayload(
            question_type="general",
            rationale="Strategy step failed; falling back to all relations.",
            allowed_predicates=[iri for iri, _ in predicates],
            max_depth=FALLBACK_DEPTH,
            prompt="Follow the relations most relevant to the question.",
        )
    allowed = [iri for n in p.allowed_predicates if (iri := _resolve(n, known))]
    allowed = list(dict.fromkeys(allowed))
    if not allowed:
        allowed = [iri for iri, _ in predicates]
    return StrategyPayload(
        question_type=p.question_type,
        rationale=p.rationale,
        allowed_predicates=allowed,
        max_depth=max(1, min(p.max_depth, MAX_DEPTH)),
        prompt=p.prompt,
    )

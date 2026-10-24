"""Plain vector RAG over the same chunk texts (contrast screen only)."""

from __future__ import annotations

from contracts.models import BaselinePayload, ScoredNode
from contracts.store import GraphStore
from engine import embed, llm

SYSTEM = "Answer the question using ONLY the passages below. If they do not contain the answer, say so. Be concise (2-4 sentences)."


def rag(question: str, store: GraphStore, model: str, k: int = 3) -> BaselinePayload:
    chunks = [n for n in store.export({"approved"}).nodes if n.cls == "Chunk" and n.text]
    if not chunks:
        return BaselinePayload(chunks=[], answer="No document passages available.", illustrative=False)
    sims = embed.rank(question, [n.text for n in chunks])
    top = sorted(zip(sims, chunks), key=lambda t: -t[0])[:k]
    passages = "\n\n".join(f"[{n.label}] {n.text}" for _, n in top)
    text = llm.complete_text([{"role": "system", "content": SYSTEM},
                              {"role": "user", "content": f"Question: {question}\n\nPassages:\n{passages}"}], model)
    return BaselinePayload(chunks=[ScoredNode(**n.model_dump(), score=round(s, 4)) for s, n in top],
                           answer=text, illustrative=False)

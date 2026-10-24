"""Multi-turn chat: the last turns of a conversation, rendered as compact context for the LLM prompts.

The server keeps the turns (api/chat_history.py); the engine only reads them, so follow-ups like
"and who supplies it?" resolve against the previous answer and its evidence."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.store import GraphStore

ANSWER_PREVIEW = 300
ENTITY_CAP = 8
NOT_ENTITIES = {"Chunk", "Document"}   # passages and files are evidence, not what "it" refers to


@dataclass(frozen=True)
class Turn:
    question: str
    answer: str                        # the true engine answer, never a chat-canary falsification
    evidence: tuple[str, ...] = ()     # node ids of the answer's evidence subgraph


def entities(turn: Turn, store: GraphStore) -> list:
    out = []
    for i in turn.evidence:
        try:
            n = store.node(i)
        except KeyError:    # the graph changed since the turn (a reverted proposal): skip the node
            continue
        if n.cls not in NOT_ENTITIES:
            out.append(n)
    return out


def context(turns: list[Turn], store: GraphStore) -> str:
    """'' without history, else a block to put in front of a prompt's question."""
    if not turns:
        return ""
    lines = ["Conversation so far (oldest first). The new question may be a follow-up: resolve references "
             "like \"it\", \"that sensor\" or \"who supplies it\" against the most recent turn."]
    for k, t in enumerate(turns, 1):
        tag = " (most recent)" if k == len(turns) else ""
        a = t.answer if len(t.answer) <= ANSWER_PREVIEW else t.answer[:ANSWER_PREVIEW] + "…"
        lines.append(f"Turn {k}{tag} question: {t.question}")
        lines.append(f"Turn {k} answer: {a}")
        if ents := entities(t, store)[:ENTITY_CAP]:
            lines.append(f"Turn {k} entities: " + ", ".join(f"{n.label} ({n.cls})" for n in ents))
    return "\n".join(lines)


def with_context(ctx: str, user: str) -> str:
    return f"{ctx}\n\n{user}" if ctx else user

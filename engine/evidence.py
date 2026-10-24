"""Evidence subgraph: cited edges plus the walked path connecting them to the seeds."""

from __future__ import annotations

from collections import deque

from contracts.models import AnswerPayload, EvidencePayload
from engine.traverse import Walk


def _path_edges(walk: Walk, target: str) -> list[str]:
    """Shortest path (over followed edges) from any seed to `target`; edge ids, [] if unreachable."""
    adj: dict[str, list[tuple[str, str]]] = {}
    for eid in walk.followed:
        e = walk.edges[eid]
        adj.setdefault(e.s, []).append((e.o, eid))
        adj.setdefault(e.o, []).append((e.s, eid))
    prev: dict[str, tuple[str, str] | None] = {s: None for s in walk.seeds}
    q = deque(walk.seeds)
    while q:
        cur = q.popleft()
        if cur == target:
            break
        for nxt, eid in adj.get(cur, []):
            if nxt not in prev:
                prev[nxt] = (cur, eid)
                q.append(nxt)
    out, cur = [], target
    while cur in prev and prev[cur] is not None:
        cur, eid = prev[cur][0], prev[cur][1]
        out.append(eid)
    return out


def evidence(walk: Walk, answer: AnswerPayload) -> EvidencePayload:
    walked = set(walk.followed)
    cited = [c.edge_id for c in answer.citations if c.edge_id in walked]
    edge_ids: dict[str, None] = dict.fromkeys(cited)
    targets = {i for eid in cited for i in (walk.edges[eid].s, walk.edges[eid].o)}
    targets |= {c.chunk_id for c in answer.citations if c.chunk_id in walk.nodes}
    for t in targets:
        for eid in _path_edges(walk, t):
            edge_ids[eid] = None
    edges = [walk.edges[i] for i in edge_ids]
    node_ids = dict.fromkeys(i for e in edges for i in (e.s, e.o))
    node_ids.update(dict.fromkeys(t for t in targets if t in walk.nodes))
    return EvidencePayload(nodes=[walk.nodes[i] for i in node_ids], edges=edges)

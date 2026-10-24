"""Graph-level check of the demo questions: seeds from store.search, shortest approved paths between key nodes."""
from collections import deque

import yaml

from contracts.ids import local_name as L, node_iri
from contracts.rdf_store import RdfGraphStore

store = RdfGraphStore("data/graph/kg.trig")
QUESTIONS = "../b-engine/runs/questions.yaml"


def path(a: str, b: str, max_depth: int = 6):
    q, seen = deque([(a, [])]), {a}
    while q:
        cur, p = q.popleft()
        if cur == b:
            return p
        if len(p) >= max_depth:
            continue
        for e in store.neighbors(cur):
            nxt = e.o if e.s == cur else e.s
            if nxt not in seen:
                seen.add(nxt)
                q.append((nxt, p + [(e, nxt == e.o)]))
    return None


def show(a, b):
    p = path(a, b)
    if p is None:
        return "NO PATH"
    return " | ".join(f"{L(e.s)} -{L(e.p)}-> {L(e.o)}" for e, _ in p) + f"  [{len(p)} hops]"


for q in yaml.safe_load(open(QUESTIONS)):
    print(f"\n## {q['id']}\nseeds:", [(L(n.id), round(sc, 2)) for n, sc in store.search(q["question"], 5)])

N = lambda c, i: node_iri(c, i)
print("\n-- PO-1003 -> ThermoSense:", show(N("ProductionOrder", "PO-1003"), N("Supplier", "ThermoSense")))
print("-- PO-1003 -> SQA-THERMO-001 (company doc):", show(N("ProductionOrder", "PO-1003"), N("Document", "SQA-THERMO-001")))
print("-- ST02_SEALING -> RULE-ST02-02 chunk:", show(N("Station", "ST02_SEALING"), N("Chunk", "SOP-001-s3")))
print("-- ST02_SEALING_TMP -> DS-THERM-2200-s1:", show(N("Sensor", "ST02_SEALING_TMP"), N("Chunk", "DS-THERM-2200-s1")))
print("-- SOP-001-s3 -> DS-THERM-2200-s1 (approved only):", show(N("Chunk", "SOP-001-s3"), N("Chunk", "DS-THERM-2200-s1")))
print("-- ST04_PACKAGING -> SOP-003:", show(N("Station", "ST04_PACKAGING"), N("Document", "SOP-003")))
ex = store.export({"proposed"})
print("-- proposed contradicts:", [(L(e.s), L(e.o)) for e in ex.edges])
print("-- authorized for maintenance (technician role persons -> Production Area):",
      len([e for e in store.neighbors(N("Zone", "Production_Area")) if L(e.p) == "authorized_for"]), "persons authorized")

"""Layer 4: an LLM proposes edges between SOP chunks and datasheet chunks. Nothing here is approved."""
from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from contracts.ids import edge_id, local_name, node_iri, pred_iri, proposal_id
from contracts.models import NodeSpec, Node, PredicateSpec, Proposal, Triple
from contracts.rdf_store import RdfGraphStore
from contracts.store import GraphStore
from engine import prompt

PROPOSALS_PATH = Path("data/proposals.json")
MAX_EDGES = 3
MAX_NODES = 3
MAX_PREDICATES = 2
MIN_CONFIDENCE = 0.9        # edges: a wrong edge in the graph is worse than a missing one
MIN_CONFIDENCE_OTHER = 0.75  # node and predicate proposals
NODE_CLASSES = ["SensorModel", "Supplier", "Customer", "Company", "Role"]  # real-world entities only

PROMPT = """You are an industrial-quality analyst. Compare an SOP passage with a sensor datasheet passage (blocks `sop_passage` and `datasheet_passage`).
Decide whether the SOP sets an operating value or instruction that CONFLICTS with a limit or recommendation in the
datasheet (for example an alarm or critical threshold above the sensor's rated continuous maximum).

Answer with JSON only: {"relation": "contradicts" | "none", "quote": "<verbatim sentence copied from the DATASHEET passage>",
"rationale": "<one sentence naming both numbers>", "confidence": <0..1>}
Use "none" if there is no clear numeric or instructional conflict."""


VERIFY = """Check a claimed conflict between an SOP passage and a datasheet passage (blocks `claim`, `sop_passage`, `datasheet_passage`). Every number in the claim must
match the passages, and the datasheet must really forbid or discourage what the SOP sets. Be strict.
Answer with JSON only: {"correct": true | false}"""


def _env() -> dict[str, str]:
    env = dict(os.environ)
    p = Path(".env")
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                env.setdefault(k.strip(), v.strip())
    return env


def _llm_json(messages: list[dict], model: str) -> dict | None:
    import litellm

    env = _env()
    for _ in range(2):
        try:
            r = litellm.completion(model=model, api_base=env["LITELLM_BASE_URL"], api_key=env["LITELLM_API_KEY"],
                                   messages=messages, temperature=0)
            m = re.search(r"\{.*\}", r.choices[0].message.content, re.S)
            return json.loads(m.group(0)) if m else None
        except Exception:
            continue
    return None


def _models(store: GraphStore, chunk: Node) -> set[str]:
    """SensorModel IRIs a chunk is about: mentioned directly, or via a mentioned sensor's `of_model`."""
    out = set()
    for e in store.neighbors(chunk.id):
        if e.s != chunk.id or local_name(e.p) != "mentions":
            continue
        n = store.node(e.o)
        if n.cls == "SensorModel":
            out.add(n.id)
        elif n.cls == "Sensor":
            out.update(x.o for x in store.neighbors(n.id) if x.s == n.id and local_name(x.p) == "of_model")
    return out


def candidate_pairs(store: GraphStore) -> list[tuple[Node, Node]]:
    """SOP chunk x datasheet chunk that concern the same sensor model."""
    chunks = [n for n in store.export({"approved"}).nodes if n.cls == "Chunk"]
    sop = [c for c in chunks if "/chunk/SOP-" in c.id and c.text]
    ds = [c for c in chunks if "/chunk/DS-" in c.id and c.text]
    return [(s, d) for s in sop for d in ds if _models(store, s) & _models(store, d)]


def propose(store: GraphStore, chunks: list[Node] | None = None, model: str | None = None) -> list[Proposal]:
    model = model or _env()["RAI_MODEL"]
    pairs = candidate_pairs(store)
    if chunks:
        ids = {c.id for c in chunks}
        pairs = [(s, d) for s, d in pairs if s.id in ids or d.id in ids]

    def judge(pair: tuple[Node, Node]) -> Proposal | None:
        s, d = pair
        out = _llm_json(prompt.build(PROMPT, sop_passage=f"{local_name(s.id)}\n{s.text}",
                                     datasheet_passage=f"{local_name(d.id)}\n{d.text}"), model)
        if not out or out.get("relation") != "contradicts":
            return None
        quote = str(out.get("quote", "")).strip()
        if not quote or quote not in d.text:  # guard: the quote must be verbatim
            return None
        conf = float(out.get("confidence", 0))
        if conf < MIN_CONFIDENCE:
            return None
        check = _llm_json(prompt.build(VERIFY, claim=str(out.get("rationale", "")), sop_passage=s.text,
                                       datasheet_passage=d.text), model)
        if not check or check.get("correct") is not True:  # second pass: drop claims whose numbers do not hold up
            return None
        p = pred_iri("contradicts")
        return Proposal(id=edge_id(s.id, p, d.id), triple=Triple(s=s.id, p=p, o=d.id),
                        rationale=str(out.get("rationale", "")), evidence_chunk_id=d.id, quote=quote,
                        confidence=conf, proposed_by=f"llm:{model}")

    with ThreadPoolExecutor(8) as ex:
        found = [p for p in ex.map(judge, pairs) if p]
    found.sort(key=lambda p: -p.confidence)
    return found[:MAX_EDGES]


def seed_contradiction(store: GraphStore, proposals: list[Proposal]) -> list[Proposal]:
    """Guarantee the ST02 TMP conflict (critical 210 C vs 200 C continuous) is proposed, from SOP-001 and SOP-002."""
    nodes = {n.id: n for n in store.export({"approved"}).nodes}
    ds = nodes[node_iri("Chunk", "DS-THERM-2200-s1")]
    quote = "The rated maximum for continuous operation is 200°C."
    assert quote in ds.text
    p = pred_iri("contradicts")
    seeds = [
        (lambda n: "/SOP-001-" in n.id and "RULE-ST02-02" in n.text,
         "SOP-001 sets 210 °C as the critical limit for the ST02_SEALING temperature sensor, but datasheet "
         "DS-THERM-2200 rates the TMP-2210 for 200 °C continuous operation."),
        (lambda n: "/SOP-002-" in n.id and n.text.startswith("ST02_SEALING TMP"),
         "SOP-002 lists CRIT_HI 210 °C for the ST02_SEALING temperature sensor, but datasheet DS-THERM-2200 "
         "rates the TMP-2210 for 200 °C continuous operation."),
    ]
    out = list(proposals)
    for match, rationale in seeds:
        sop = next(n for n in nodes.values() if n.cls == "Chunk" and n.text and match(n))
        eid = edge_id(sop.id, p, ds.id)
        if not any(x.id == eid for x in out):
            out.append(Proposal(id=eid, triple=Triple(s=sop.id, p=p, o=ds.id), evidence_chunk_id=ds.id, quote=quote,
                                rationale=rationale, confidence=0.9, proposed_by="analyst-seed"))
    return out[:MAX_EDGES]


EXTRACT = """You are a knowledge-graph analyst. Read this passage from a company document and propose additions to
the knowledge graph. The graph already has these classes: {classes}. New nodes may only use: {node_classes}.
It already has these predicates: {predicates}.

1. "nodes": real entities named in the passage that are NOT in the graph yet (for example a successor or alternative
   product model, a vendor, a standard). Use one of the existing classes. local_id has no spaces.
2. "predicates": a relationship stated in the passage that none of the existing predicates can express.
   name is snake_case, description reads "Domain verb Range.", domain and range are existing classes.
Only propose what the passage states. quote must be copied verbatim from the passage. Propose at most 2 of each.
Entities that already exist in the graph (listed below) must not be proposed again.

Existing entities: {existing}

Answer with JSON only:
{{"nodes": [{{"cls": "...", "local_id": "...", "label": "...", "description": "...", "quote": "...", "rationale": "...", "confidence": 0.0}}],
"predicates": [{{"name": "...", "description": "...", "domain": "...", "range": "...", "quote": "...", "rationale": "...", "confidence": 0.0}}]}}

Passage ({chunk_id}):
{text}
"""


def _ontology_classes() -> list[str]:
    from rdflib import OWL, RDF, Graph

    g = Graph().parse("data/graph/ontology.ttl", format="turtle")
    return sorted(local_name(str(s)) for s in g.subjects(RDF.type, OWL.Class))


def propose_new_kinds(store: GraphStore, model: str | None = None) -> tuple[list[Proposal], list[Proposal]]:
    """LLM proposals for missing nodes and missing predicates, read from datasheets and company documents."""
    model = model or _env()["RAI_MODEL"]
    classes = _ontology_classes()
    preds = [local_name(i) for i, _ in store.predicates()]
    export = store.export({"approved"})
    existing = sorted({local_name(n.id) for n in export.nodes if n.cls != "Chunk"} |
                      {n.label for n in export.nodes if n.cls in ("SensorModel", "Supplier", "Customer", "Company")})
    chunks = [n for n in export.nodes if n.cls == "Chunk" and n.text and
              any(f"/chunk/{d}" in n.id for d in ("DS-", "SQA-", "MC-"))]

    def read(chunk: Node) -> list[Proposal]:
        out = _llm_json(EXTRACT.format(classes=", ".join(classes), node_classes=", ".join(NODE_CLASSES), predicates=", ".join(preds),
                                       existing=", ".join(existing), chunk_id=local_name(chunk.id), text=chunk.text), model)
        found: list[Proposal] = []
        for n in (out or {}).get("nodes", []):
            quote, conf = str(n.get("quote", "")).strip(), float(n.get("confidence", 0))
            lid = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(n.get("local_id", "")))
            if (n.get("cls") not in NODE_CLASSES or not lid or lid in existing or quote not in chunk.text
                    or conf < MIN_CONFIDENCE_OTHER):
                continue
            iri = node_iri(n["cls"], lid)
            found.append(Proposal(id=proposal_id("node", iri=iri), kind="node",
                                  node=NodeSpec(cls=n["cls"], local_id=lid, label=str(n.get("label") or lid),
                                                description=n.get("description")),
                                  rationale=str(n.get("rationale", "")), evidence_chunk_id=chunk.id, quote=quote,
                                  confidence=conf, proposed_by=f"llm:{model}"))
        for q in (out or {}).get("predicates", []):
            quote, conf = str(q.get("quote", "")).strip(), float(q.get("confidence", 0))
            name = str(q.get("name", ""))
            if (not re.fullmatch(r"[a-z][a-z0-9_]*", name) or name in preds or quote not in chunk.text
                    or conf < MIN_CONFIDENCE_OTHER or q.get("domain") not in classes or q.get("range") not in classes):
                continue
            found.append(Proposal(id=proposal_id("predicate", iri=pred_iri(name)), kind="predicate",
                                  predicate=PredicateSpec(name=name, description=str(q.get("description", "")),
                                                          domain=q["domain"], range=q["range"]),
                                  rationale=str(q.get("rationale", "")), evidence_chunk_id=chunk.id, quote=quote,
                                  confidence=conf, proposed_by=f"llm:{model}"))
        return found

    with ThreadPoolExecutor(8) as ex:
        allp = [p for ps in ex.map(read, chunks) for p in ps]
    uniq: dict[str, Proposal] = {}
    for p in sorted(allp, key=lambda p: -(p.confidence or 0)):
        uniq.setdefault(p.id, p)
    ranked = list(uniq.values())
    return ([p for p in ranked if p.kind == "node"][:MAX_NODES],
            [p for p in ranked if p.kind == "predicate"][:MAX_PREDICATES])


def seed_new_kinds(store: GraphStore, nodes: list[Proposal], preds: list[Proposal]) -> tuple[list[Proposal], list[Proposal]]:
    """Guarantee one node and one predicate proposal from the TMP-2210 datasheet (successor model Series 2400)."""
    ds = store.node(node_iri("Chunk", "DS-THERM-2200-s1"))
    quote = ("For applications requiring sustained operation above 200°C, ThermoSense recommends the Series 2400 "
             "(Pt100 RTD, rated to 250°C continuous).")
    assert quote in ds.text
    if not nodes:
        iri = node_iri("SensorModel", "RTD-2400")
        nodes = [Proposal(id=proposal_id("node", iri=iri), kind="node",
                          node=NodeSpec(cls="SensorModel", local_id="RTD-2400", label="RTD-2400 (Series 2400 Pt100)",
                                        description="Pt100 RTD temperature sensor, rated to 250 °C continuous."),
                          rationale="The datasheet names a successor model that is not yet in the graph.",
                          evidence_chunk_id=ds.id, quote=quote, confidence=0.9, proposed_by="analyst-seed")]
    if not preds:
        preds = [Proposal(id=proposal_id("predicate", iri=pred_iri("recommended_replacement")), kind="predicate",
                          predicate=PredicateSpec(name="recommended_replacement", domain="SensorModel", range="SensorModel",
                                                  description="SensorModel recommended_replacement SensorModel."),
                          rationale="Vendors name successor models; no predicate can express that today.",
                          evidence_chunk_id=ds.id, quote=quote, confidence=0.8, proposed_by="analyst-seed")]
    return nodes, preds


def write(proposals: list[Proposal], path: Path = PROPOSALS_PATH) -> None:
    path.write_text(json.dumps([p.model_dump(mode="json") for p in proposals], indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    import sys

    model = sys.argv[1] if len(sys.argv) > 1 else None
    store = RdfGraphStore("data/graph/kg.trig")
    # Statuses already decided by the analyst survive a re-run.
    decided = {x["id"]: x["status"] for x in json.loads(PROPOSALS_PATH.read_text())} if PROPOSALS_PATH.exists() else {}
    edges = seed_contradiction(store, propose(store, model=model))
    nodes, preds = seed_new_kinds(store, *propose_new_kinds(store, model))
    props = edges + nodes + preds
    for p in props:
        p.status = decided.get(p.id, p.status)
    write(props)
    for p in props:
        what = p.kind if p.kind != "edge" else f"edge {local_name(p.triple.s)} -> {local_name(p.triple.o)}"
        if p.kind == "node":
            what = f"node {p.node.cls}:{p.node.local_id}"
        if p.kind == "predicate":
            what = f"predicate {p.predicate.name}"
        print(p.proposed_by, p.confidence, p.status, what, "|", p.rationale[:90])

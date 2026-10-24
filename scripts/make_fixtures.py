"""Writes contracts/fixtures/*: a mini graph with real iMAKS values and one complete demo run (mock).

Run: uv run python scripts/make_fixtures.py
"""

from __future__ import annotations

import json
from pathlib import Path

from rdflib import RDF, RDFS, Dataset, Literal, URIRef

from contracts.ids import GRAPH_IRIS, ONT, edge_id, node_iri, pred_iri, proposal_id
from contracts.models import (
    AnswerEvent, AnswerPayload, BaselineEvent, Canary, BaselinePayload, Citation, Contradiction, Decision,
    EvidenceEvent, EvidencePayload, NodeSpec, PredicateSpec, Proposal, RunFinished, RunFinishedEvent, RunStarted, RunStartedEvent,
    ScoredNode, SeedsEvent, SeedsPayload, StepEvent, StepPayload, StrategyEvent, StrategyPayload, Triple,
)
from contracts.rdf_store import RdfGraphStore

OUT = Path(__file__).resolve().parent.parent / "contracts" / "fixtures"

SOP_TEXT = ("SOP-001 Operating Procedures, Station ST02_SEALING. RULE-ST02-01: TMP MUST remain between "
            "175°C and 195°C. Warning above 195°C, critical above 210°C: inspect and notify maintenance.")
DS_TEXT = ("DS-THERM-2200 Temperature Sensor TMP-2210. Measurement range -40 to +200°C. Note 1: the rated maximum "
           "for continuous operation is 200°C. Exposure above this value accelerates thermocouple ageing and may "
           "cause drift of up to ±5°C within 500 hours.")

N = {
    "company": ("Company", "Kelvara", "Kelvara Packaging GmbH", "Fictional company operating iMAKS line A."),
    "system": ("System", "iMAKS", "iMAKS Line A", None),
    "station": ("Station", "ST02_SEALING", "ST02_SEALING", "Heat sealing station."),
    "sensor": ("Sensor", "ST02_SEALING_TMP", "ST02_SEALING_TMP", "Sealing jaw temperature."),
    "model": ("SensorModel", "TMP-2210", "TMP-2210", "Thermocouple temperature sensor, Series 2200."),
    "supplier": ("Supplier", "ThermoSense", "ThermoSense GmbH", None),
    "order": ("ProductionOrder", "PO-1003", "PO-1003", "Sealed yoghurt cups, 40,000 units."),
    "customer": ("Customer", "Velora", "Velora Foods AG", "Fictional customer."),
    "rule": ("Rule", "RULE-ST02-01", "RULE-ST02-01", "TMP MUST remain between 175°C and 195°C."),
    "sop": ("Document", "SOP-001", "SOP-001 Operating Procedures", None),
    "sop_c": ("Chunk", "SOP-001-s2", "SOP-001 §2 Sealing", None),
    "ds": ("Document", "DS-THERM-2200", "DS-THERM-2200 Thermal Sensors Datasheet", None),
    "ds_c": ("Chunk", "DS-THERM-2200-s1", "DS-THERM-2200 §1 TMP-2210", None),
}
IRI = {k: node_iri(cls, lid) for k, (cls, lid, _, _) in N.items()}

APPROVED = [
    ("company", "operates", "system"), ("station", "part_of", "system"), ("sensor", "monitors", "station"),
    ("sensor", "of_model", "model"), ("model", "supplied_by", "supplier"), ("order", "executed_at", "station"),
    ("order", "ordered_by", "customer"), ("rule", "applies_to", "sensor"), ("rule", "defined_in", "sop_c"),
    ("sop", "has_chunk", "sop_c"), ("ds", "has_chunk", "ds_c"), ("ds_c", "mentions", "model"),
    ("sop_c", "mentions", "station"),
]
PROPOSED = [("sop_c", "contradicts", "ds_c")]
REJECTED = [("ds", "governs", "station")]


def build_graph() -> Path:
    ds = Dataset()
    approved = ds.graph(URIRef(GRAPH_IRIS["approved"]))
    for k, (cls, _, label, desc) in N.items():
        s = URIRef(IRI[k])
        approved.add((s, RDF.type, URIRef(ONT + cls)))
        approved.add((s, RDFS.label, Literal(label)))
        if desc:
            approved.add((s, RDFS.comment, Literal(desc)))
    sensor = URIRef(IRI["sensor"])
    for key, val in [("sensorType", "TMP"), ("unit", "°C"), ("warnLo", 175.0), ("warnHi", 195.0), ("critHi", 210.0), ("critLo", 165.0)]:
        approved.add((sensor, URIRef(pred_iri(key)), Literal(val)))
    for k, text, page in [("sop_c", SOP_TEXT, 1), ("ds_c", DS_TEXT, 1)]:
        approved.add((URIRef(IRI[k]), URIRef(pred_iri("text")), Literal(text)))
        approved.add((URIRef(IRI[k]), URIRef(pred_iri("page")), Literal(page)))
    for name, triples in [("approved", APPROVED), ("proposed", PROPOSED), ("rejected", REJECTED)]:
        g = ds.graph(URIRef(GRAPH_IRIS[name]))
        for s, p, o in triples:
            g.add((URIRef(IRI[s]), URIRef(pred_iri(p)), URIRef(IRI[o])))
    path = OUT / "mini_graph.trig"
    ds.serialize(path, format="trig")
    return path


def build_run(store: RdfGraphStore) -> list:
    rid, ts = "demo-po1003", "2026-10-24T11:00:00Z"
    events: list = []

    def add(cls, payload):
        events.append(cls(run_id=rid, seq=len(events), ts=ts, payload=payload))

    allowed = [pred_iri(p) for p in ["executed_at", "monitors", "of_model", "supplied_by", "applies_to", "defined_in", "mentions", "has_chunk"]]
    question = "Can order PO-1003 run safely at the sealing temperature limit, and who supplies the temperature sensor?"
    add(RunStartedEvent, RunStarted(question=question, model="openrouter/google/gemma-4-31b-it", mode="replay", mock=True))
    add(StrategyEvent, StrategyPayload(
        question_type="order → asset → documents",
        rationale="Order safety depends on the station it runs at, the sensor limits there, the rule that sets them and the sensor's datasheet.",
        allowed_predicates=allowed, max_depth=4,
        prompt="Follow only edges that lead from the order to the asset, its sensor, the governing rule and the documents that define limits."))
    add(SeedsEvent, SeedsPayload(nodes=[
        ScoredNode(**store.node(IRI["order"]).model_dump(), score=0.62),
        ScoredNode(**store.node(IRI["station"]).model_dump(), score=0.41)]))

    allowed_set = set(allowed)
    follow_reason = {
        "executed_at": "The order runs at this station.",
        "monitors": "This sensor measures the sealing temperature.",
        "mentions": "This document section is about the station/sensor model.",
        "of_model": "Need the sensor's rated limits.",
        "applies_to": "This rule sets the temperature limits.",
        "defined_in": "Source text of the rule.",
        "supplied_by": "Question asks for the supplier.",
    }
    current = {IRI["order"], IRI["station"]}
    seen: set[str] = set()
    walked: list[str] = []
    for n in range(1, 4):
        frontier = [e for c in sorted(current) for e in store.neighbors(c, allowed_set) if e.id not in seen]
        frontier = list({e.id: e for e in frontier}.values())
        decisions, nxt = [], set()
        for e in frontier:
            seen.add(e.id)
            p = e.p.rsplit("#", 1)[-1]
            if p in follow_reason:
                decisions.append(Decision(edge_id=e.id, verdict="follow", reason=follow_reason[p]))
                walked.append(e.id)
                nxt |= {e.s, e.o} - current
            else:
                decisions.append(Decision(edge_id=e.id, verdict="prune", reason="Document container adds nothing beyond its section."))
        nodes = {i: store.node(i) for e in frontier for i in (e.s, e.o)}
        add(StepEvent, StepPayload(n=n, frontier=frontier, nodes=list(nodes.values()), decisions=decisions, sufficient=n == 3))
        current = nxt

    def eid(s, p, o):
        return edge_id(IRI[s], pred_iri(p), IRI[o])

    cited = [eid("order", "executed_at", "station"), eid("sensor", "monitors", "station"), eid("rule", "applies_to", "sensor"),
             eid("rule", "defined_in", "sop_c"), eid("sensor", "of_model", "model"), eid("ds_c", "mentions", "model"),
             eid("model", "supplied_by", "supplier")]
    add(AnswerEvent, AnswerPayload(
        text=("Not safely at the upper limit. PO-1003 runs at ST02_SEALING, whose rule RULE-ST02-01 (SOP-001) tolerates up to "
              "210 °C before it is critical, but the installed sensor TMP-2210 is rated for only 200 °C continuous operation "
              "(DS-THERM-2200). The sensor is supplied by ThermoSense GmbH. Escalate before running near the critical limit."),
        justification=("Order → station → sensor → rule gives the SOP limits; sensor → model → datasheet gives the rated maximum. "
                       "The two documents disagree above 200 °C."),
        citations=[Citation(edge_id=c) for c in cited] + [Citation(chunk_id=IRI["sop_c"]), Citation(chunk_id=IRI["ds_c"])],
        contradictions=[Contradiction(a=IRI["sop_c"], b=IRI["ds_c"],
                                      note="SOP-001 critical limit 210 °C vs. TMP-2210 rated 200 °C continuous.")]))
    all_edges = {e.id: e for e in store.export({"approved"}).edges}
    ev_edges = [all_edges[c] for c in cited]
    ev_nodes = {i: store.node(i) for e in ev_edges for i in (e.s, e.o)}
    add(EvidenceEvent, EvidencePayload(nodes=list(ev_nodes.values()), edges=ev_edges))
    add(BaselineEvent, BaselinePayload(
        chunks=[ScoredNode(**store.node(IRI["sop_c"]).model_dump(), score=0.81)],
        answer="Yes. SOP-001 allows the sealing temperature up to 210 °C before it becomes critical, so PO-1003 can run at the limit.",
        illustrative=True))
    add(RunFinishedEvent, RunFinished(status="ok"))
    return events


def canary_run(events: list) -> list:
    """Chat canary (click mock): same walk, but the answer plants an obviously false supplier."""
    out = []
    for e in events:
        e = e.model_copy(deep=True, update={"run_id": "demo-canary-chat"})
        if e.type == "run.started":
            e.payload.question = "Who supplies the temperature sensor at the sealing station?"
        if e.type == "answer":
            e.payload.text = ("The temperature sensor TMP-2210 at ST02_SEALING is supplied by Velora Foods AG "
                              "under the maintenance contract of PO-1003.")
            e.payload.justification = "Sensor → model → supplier."
            e.payload.contradictions = []
            e.payload.canary = Canary(claim="TMP-2210 is supplied by Velora Foods AG.",
                                      truth="TMP-2210 is supplied by ThermoSense GmbH; Velora Foods AG is a customer.")
        out.append(e)
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    store = RdfGraphStore(build_graph())
    events = build_run(store)
    (OUT / "run_demo.jsonl").write_text("".join(e.model_dump_json() + "\n" for e in events))
    (OUT / "run_canary_chat.jsonl").write_text("".join(e.model_dump_json() + "\n" for e in canary_run(events)))
    s, p, o = IRI["sop_c"], pred_iri("contradicts"), IRI["ds_c"]
    proposal = Proposal(id=edge_id(s, p, o), triple=Triple(s=s, p=p, o=o),
                        rationale="SOP-001 sets 210 °C as critical for ST02 TMP; the TMP-2210 datasheet rates 200 °C continuous.",
                        evidence_chunk_id=o, quote="the rated maximum for continuous operation is 200°C",
                        confidence=0.86, proposed_by="llm:openrouter/google/gemma-4-31b-it")
    ds_quote = "For applications requiring sustained operation above 200°C, ThermoSense recommends the Series 2400 (Pt100 RTD, rated to 250°C continuous)."
    new_model = NodeSpec(cls="SensorModel", local_id="RTD-2400", label="RTD-2400 (Series 2400 Pt100)",
                         description="Pt100 RTD temperature sensor, rated to 250 °C continuous.")
    node_prop = Proposal(id=proposal_id("node", iri=node_iri("SensorModel", "RTD-2400")), kind="node", node=new_model,
                         rationale="The datasheet names a successor model that is not yet in the graph.",
                         evidence_chunk_id=o, quote=ds_quote, confidence=0.91,
                         proposed_by="llm:openrouter/google/gemma-4-31b-it")
    pred = PredicateSpec(name="recommended_replacement", description="SensorModel recommended_replacement SensorModel.",
                         domain="SensorModel", range="SensorModel")
    pred_prop = Proposal(id=proposal_id("predicate", iri=pred_iri("recommended_replacement")), kind="predicate", predicate=pred,
                         rationale="Vendors name successor models; no predicate can express that today.",
                         evidence_chunk_id=o, quote=ds_quote, confidence=0.78,
                         proposed_by="llm:openrouter/google/gemma-4-31b-it")
    governs = (IRI["sop"], pred_iri("governs"), IRI["station"])
    user_prop = Proposal(id=proposal_id("edge", triple=governs), kind="edge", triple=Triple(s=governs[0], p=governs[1], o=governs[2]),
                         rationale="SOP-001 is the operating procedure for the sealing station.", proposed_by="user")
    proposals = [proposal, node_prop, pred_prop, user_prop]
    (OUT / "proposals.json").write_text(json.dumps([x.model_dump() for x in proposals], indent=2, ensure_ascii=False))
    (OUT / "graph_export.json").write_text(store.export({"approved", "proposed"}).model_dump_json(indent=2))
    print(f"wrote {len(events)} events")


if __name__ == "__main__":
    main()

"""Writes web/public/data/graph_export.json from data/graph/kg.trig (approved + proposed).

Run from the repo root: uv run python web/scripts/export_graph.py
"""

from collections import Counter
from pathlib import Path

from contracts.rdf_store import RdfGraphStore

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "web/public/data/graph_export.json"

export = RdfGraphStore(ROOT / "data/graph/kg.trig").export({"approved", "proposed"})
OUT.write_text(export.model_dump_json(indent=1))
print(f"{len(export.nodes)} nodes, {len(export.edges)} edges -> {OUT.relative_to(ROOT)}")
print("classes:", dict(Counter(n.cls for n in export.nodes).most_common()))
print("edges:", dict(Counter(e.graph for e in export.edges)))

# Ontology for the curation forms: classes and predicates with their comments.
import json  # noqa: E402

from rdflib import OWL, RDF, RDFS, Graph  # noqa: E402

from contracts.ids import local_name  # noqa: E402

ont = Graph().parse(ROOT / "data/graph/ontology.ttl")
classes = sorted(
    ({"name": local_name(str(c)), "description": str(ont.value(c, RDFS.comment) or "")} for c in ont.subjects(RDF.type, OWL.Class)),
    key=lambda c: c["name"],
)
store = RdfGraphStore(ROOT / "data/graph/kg.trig")
predicates = [{"iri": iri, "name": local_name(iri), "description": d} for iri, d in store.predicates()]
(OUT.parent / "ontology.json").write_text(json.dumps({"classes": classes, "predicates": predicates}, indent=1, ensure_ascii=False))
print(f"ontology: {len(classes)} classes, {len(predicates)} predicates")

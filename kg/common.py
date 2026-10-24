"""Shared helpers for building the KG: a Dataset that also collects provenance."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from rdflib import RDF, RDFS, Dataset, Literal, URIRef
from rdflib.namespace import XSD

from contracts.ids import GRAPH_IRIS, edge_id, node_iri, pred_iri
from contracts.models import Provenance

RAW_DIR = Path("data/raw/imaks")
NOW = datetime.now(timezone.utc).isoformat(timespec="seconds")


class KGDataset(Dataset):
    """rdflib Dataset plus the provenance records of every edge added."""

    def __init__(self):
        super().__init__()
        self.prov: list[Provenance] = []

    def graph_for(self, name: str):
        return self.graph(URIRef(GRAPH_IRIS[name]))

    def add_node(self, cls: str, local_id: str, label: str, comment: str | None = None,
                 graph: str = "approved", **props) -> str:
        iri = node_iri(cls, local_id)
        g = self.graph_for(graph)
        s = URIRef(iri)
        g.add((s, RDF.type, URIRef(pred_iri(cls))))
        g.add((s, RDFS.label, Literal(label)))
        if comment:
            g.add((s, RDFS.comment, Literal(comment)))
        for k, v in props.items():
            self.add_prop(iri, k, v, graph)
        return iri

    def add_prop(self, iri: str, key: str, value, graph: str = "approved") -> None:
        if isinstance(value, bool):
            lit = Literal(value)
        elif isinstance(value, (int, float)):
            lit = Literal(value)
        else:
            lit = Literal(str(value))
        self.graph_for(graph).add((URIRef(iri), URIRef(pred_iri(key)), lit))

    def add_edge(self, s: str, p: str, o: str, source: str, creator: str = "script",
                 graph: str = "approved") -> str:
        """`p` is the ontology local name. Returns the edge id; duplicates are ignored."""
        pi = pred_iri(p)
        eid = edge_id(s, pi, o)
        g = self.graph_for(graph)
        if (URIRef(s), URIRef(pi), URIRef(o)) in g:
            return eid
        g.add((URIRef(s), URIRef(pi), URIRef(o)))
        self.prov.append(Provenance(edge_id=eid, source=source, creator=creator,
                                    status=graph, created_at=NOW))  # type: ignore[arg-type]
        return eid


def parse_number(v: str):
    """CSV cell -> int/float if numeric, else the string."""
    try:
        return int(v)
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return v

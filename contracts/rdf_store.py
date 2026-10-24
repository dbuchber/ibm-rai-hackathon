"""GraphStore over a TriG file. Works on the fixture and on stream A's `data/graph/kg.trig`."""

from __future__ import annotations

import re
from pathlib import Path

from rdflib import RDF, RDFS, Dataset, Literal, URIRef

from contracts.ids import GRAPH_IRIS, KG, ONT, edge_id, local_name
from contracts.models import Edge, GraphExport, GraphName, Node

ONTOLOGY = Path(__file__).resolve().parent.parent / "data" / "graph" / "ontology.ttl"
_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = {"the", "a", "an", "of", "for", "to", "in", "is", "and", "which", "what", "at", "on", "by", "with", "are", "does", "do"}


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN.findall(text.lower().replace("_", " ")) if t not in _STOP}


class RdfGraphStore:
    def __init__(self, path: str | Path, ontology: str | Path = ONTOLOGY):
        self.ds = Dataset()
        self.ds.parse(str(path), format="trig")
        self._ont = Dataset()
        self._ont.parse(str(ontology), format="turtle")
        self._nodes: dict[str, Node] = {}
        self._edges: dict[str, Edge] = {}
        self._load()

    def _load(self) -> None:
        graph_of = {URIRef(iri): name for name, iri in GRAPH_IRIS.items()}
        raw: dict[str, dict] = {}
        for s, p, o, g in self.ds.quads((None, None, None, None)):
            gname: GraphName | None = graph_of.get(g)
            if gname is None or not str(s).startswith(KG):
                continue
            sid = str(s)
            if p == RDF.type:
                raw.setdefault(sid, {})["cls"] = local_name(str(o))
            elif p == RDFS.label:
                raw.setdefault(sid, {})["label"] = str(o)
            elif p == RDFS.comment:
                raw.setdefault(sid, {})["description"] = str(o)
            elif isinstance(o, Literal) and str(p).startswith(ONT):
                key = local_name(str(p))
                entry = raw.setdefault(sid, {})
                if key == "text":
                    entry["text"] = str(o)
                else:
                    entry.setdefault("props", {})[key] = o.toPython() if isinstance(o.toPython(), (int, float)) else str(o)
            elif isinstance(o, URIRef) and str(o).startswith(KG) and str(p).startswith(ONT):
                eid = edge_id(sid, str(p), str(o))
                self._edges[eid] = Edge(id=eid, s=sid, p=str(p), o=str(o), graph=gname)
        for sid, d in raw.items():
            if "cls" in d:
                self._nodes[sid] = Node(id=sid, cls=d["cls"], label=d.get("label", local_name(sid)),
                                        description=d.get("description"), text=d.get("text"),
                                        props=d.get("props", {}))
        self._adj: dict[str, list[Edge]] = {}
        for e in self._edges.values():
            if e.graph == "approved":
                self._adj.setdefault(e.s, []).append(e)
                self._adj.setdefault(e.o, []).append(e)

    def node(self, id: str) -> Node:
        return self._nodes[id]

    def search(self, text: str, k: int = 5) -> list[tuple[Node, float]]:
        q = _tokens(text)
        if not q:
            return []
        lowered = text.lower()
        scored = []
        for n in self._nodes.values():
            # An entity named verbatim in the question (PO-1003, ST02_SEALING) beats any token overlap.
            lid = local_name(n.id).lower()
            if len(lid) >= 4 and re.search(rf"(?<![a-z0-9_-]){re.escape(lid)}(?![a-z0-9_-])", lowered):
                scored.append((n, 2.0))
                continue
            name_hit = len(q & _tokens(" ".join(filter(None, [n.label, local_name(n.id)]))))
            body_hit = len(q & _tokens(" ".join(filter(None, [n.description, n.text]))))
            score = (name_hit + 0.5 * body_hit) / len(q)
            if score:
                scored.append((n, score))
        scored.sort(key=lambda t: (-t[1], t[0].id))
        return scored[:k]

    def neighbors(self, id: str, predicates: set[str] | None = None) -> list[Edge]:
        return [e for e in self._adj.get(id, []) if predicates is None or e.p in predicates]

    def predicates(self) -> list[tuple[str, str]]:
        out = []
        for s, _, c in self._ont.triples((None, RDFS.comment, None)):
            if (s, RDF.type, None) not in self._ont:
                out.append((str(s), str(c)))
        return sorted(out)

    def export(self, graphs: set[GraphName]) -> GraphExport:
        edges = [e for e in self._edges.values() if e.graph in graphs]
        return GraphExport(nodes=list(self._nodes.values()), edges=edges)

    # Not part of the protocol: used by the API for curation decisions.
    def set_edge_graph(self, eid: str, graph: GraphName) -> Edge:
        e = self._edges[eid].model_copy(update={"graph": graph})
        self._edges[eid] = e
        for lst in self._adj.values():
            lst[:] = [x for x in lst if x.id != eid]
        if graph == "approved":
            self._adj.setdefault(e.s, []).append(e)
            self._adj.setdefault(e.o, []).append(e)
        return e

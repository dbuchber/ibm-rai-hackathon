"""RdfGraphStore plus the in-memory writes curation needs (the contract store only reads)."""

from __future__ import annotations

from rdflib import RDF, RDFS, Literal, URIRef

from contracts.ids import ONT, edge_id, node_iri, pred_iri
from contracts.models import Edge, GraphName, Node, NodeSpec, PredicateSpec
from contracts.rdf_store import RdfGraphStore


class CurationStore(RdfGraphStore):
    def has_class(self, cls: str) -> bool:
        return (URIRef(ONT + cls), RDF.type, None) in self._ont

    def add_edge(self, s: str, p: str, o: str, graph: GraphName) -> Edge:
        eid = edge_id(s, p, o)
        if eid in self._edges:
            return self.set_edge_graph(eid, graph)
        e = Edge(id=eid, s=s, p=p, o=o, graph=graph)
        self._edges[eid] = e
        if graph == "approved":
            self._adj.setdefault(s, []).append(e)
            self._adj.setdefault(o, []).append(e)
        return e

    def add_node(self, spec: NodeSpec) -> Node:
        iri = node_iri(spec.cls, spec.local_id)
        n = Node(id=iri, cls=spec.cls, label=spec.label, description=spec.description)
        self._nodes[iri] = n
        return n

    def add_predicate(self, spec: PredicateSpec) -> str:
        iri = URIRef(pred_iri(spec.name))
        self._ont.add((iri, RDFS.comment, Literal(spec.description)))
        if spec.domain:
            self._ont.add((iri, RDFS.domain, URIRef(ONT + spec.domain)))
        if spec.range:
            self._ont.add((iri, RDFS.range, URIRef(ONT + spec.range)))
        return str(iri)

    def remove_node(self, iri: str) -> None:
        self._nodes.pop(iri, None)

    def remove_predicate(self, name: str) -> None:
        self._ont.remove((URIRef(pred_iri(name)), None, None))

"""C2: what the engine may ask of the graph."""

from __future__ import annotations

from typing import Protocol

from contracts.models import Edge, GraphExport, GraphName, Node


class GraphStore(Protocol):
    def node(self, id: str) -> Node: ...

    def search(self, text: str, k: int = 5) -> list[tuple[Node, float]]:
        """Seed candidates from the approved graph, best first."""
        ...

    def neighbors(self, id: str, predicates: set[str] | None = None) -> list[Edge]:
        """Approved edges touching `id` in either direction; `predicates` are IRIs, None = all."""
        ...

    def predicates(self) -> list[tuple[str, str]]:
        """(predicate IRI, description) for every predicate in the ontology."""
        ...

    def export(self, graphs: set[GraphName]) -> GraphExport: ...

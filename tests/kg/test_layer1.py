from pathlib import Path

import pytest
from rdflib import RDF, URIRef

from contracts.ids import GRAPH_IRIS, ONT, node_iri
from kg import layer1_imaks

RAW = Path("data/raw/imaks")
pytestmark = pytest.mark.skipif(not RAW.exists(), reason="run kg.download first")

CLASSES = ["System", "Zone", "Station", "Sensor", "Person", "AnomalyEvent", "SafetyEvent", "Maintenance"]


def test_counts():
    ds = layer1_imaks.build(RAW)
    g = ds.graph(URIRef(GRAPH_IRIS["approved"]))
    nodes = {s for c in CLASSES for s in g.subjects(RDF.type, URIRef(ONT + c))}
    assert len(nodes) == 115
    edges = [t for t in g if isinstance(t[2], URIRef) and str(t[1]).startswith(ONT) and t[1] != RDF.type]
    assert len(edges) == 319
    assert len(ds.prov) == 319


def test_ids_match_fixture():
    ds = layer1_imaks.build(RAW)
    g = ds.graph(URIRef(GRAPH_IRIS["approved"]))
    st = URIRef(node_iri("Station", "ST02_SEALING"))
    tmp = URIRef(node_iri("Sensor", "ST02_SEALING_TMP"))
    assert (st, RDF.type, URIRef(ONT + "Station")) in g
    assert (tmp, URIRef(ONT + "monitors"), st) in g

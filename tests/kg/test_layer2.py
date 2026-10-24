from pathlib import Path

import pytest
from rdflib import URIRef

from contracts.ids import GRAPH_IRIS, node_iri, pred_iri
from kg import layer1_imaks, layer2_docs

RAW = Path("data/raw/imaks")
pytestmark = pytest.mark.skipif(not RAW.exists(), reason="run kg.download first")


@pytest.fixture(scope="module")
def ds():
    d = layer1_imaks.build(RAW)
    layer2_docs.build(RAW, d)
    return d


def has(ds, s, p, o):
    return (URIRef(s), URIRef(pred_iri(p)), URIRef(o)) in ds.graph(URIRef(GRAPH_IRIS["approved"]))


def test_sop_chunks_link_stations(ds):
    g = ds.graph(URIRef(GRAPH_IRIS["approved"]))
    sop3 = [str(c) for c in g.objects(URIRef(node_iri("Document", "SOP-003")), URIRef(pred_iri("has_chunk")))]
    assert sop3
    st4 = node_iri("Station", "ST04_PACKAGING")
    maint1 = [c for c in sop3 if str(next(g.objects(URIRef(c), URIRef(pred_iri("text"))))).startswith("MAINT-01")]
    assert maint1 and has(ds, maint1[0], "mentions", st4)
    rule = node_iri("Rule", "RULE-ST02-01")
    sop1 = {str(c) for c in g.objects(URIRef(node_iri("Document", "SOP-001")), URIRef(pred_iri("has_chunk")))}
    assert any(has(ds, rule, "defined_in", c) for c in sop1)


def test_contradiction_chunks_exist(ds):
    g = ds.graph(URIRef(GRAPH_IRIS["approved"]))
    sop1 = [str(c) for c in g.objects(URIRef(node_iri("Document", "SOP-001")), URIRef(pred_iri("has_chunk")))]
    texts = {c: str(next(g.objects(URIRef(c), URIRef(pred_iri("text"))))) for c in sop1}
    sealing = [c for c, t in texts.items() if "RULE-ST02-02" in t]
    assert sealing and "210" in texts[sealing[0]]
    assert has(ds, sealing[0], "mentions", node_iri("Sensor", "ST02_SEALING_TMP"))


def test_all_rules_defined_in_chunk(ds):
    g = ds.graph(URIRef(GRAPH_IRIS["approved"]))
    rules = list(g.subjects(URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"), URIRef(pred_iri("Rule"))))
    assert len(rules) == 86
    for r in rules:
        assert list(g.objects(r, URIRef(pred_iri("defined_in")))), r

from collections import deque
from pathlib import Path

import pytest
from rdflib import URIRef

from contracts.ids import GRAPH_IRIS, node_iri, pred_iri
from kg import layer1_imaks, layer2_docs, layer3_company

RAW = Path("data/raw/imaks")
pytestmark = pytest.mark.skipif(not RAW.exists(), reason="run kg.download first")


@pytest.fixture(scope="module")
def ds():
    d = layer1_imaks.build(RAW)
    layer2_docs.build(RAW, d)
    layer3_company.build(d)
    return d


def test_supplier_path(ds):
    g = ds.graph(URIRef(GRAPH_IRIS["approved"]))
    p = lambda n: URIRef(pred_iri(n))
    po = URIRef(node_iri("ProductionOrder", "PO-1003"))
    st = URIRef(node_iri("Station", "ST02_SEALING"))
    ts = URIRef(node_iri("Supplier", "ThermoSense"))
    assert (po, p("executed_at"), st) in g
    sensor = next(s for s in g.subjects(p("monitors"), st) if (s, p("of_model"), None) in g
                  and str(s).endswith("_TMP"))
    model = next(g.objects(sensor, p("of_model")))
    assert str(model).endswith("TMP-2210")
    assert (model, p("supplied_by"), ts) in g


def test_company_doc_links_to_plant(ds):
    g = ds.graph(URIRef(GRAPH_IRIS["approved"]))
    p = lambda n: URIRef(pred_iri(n))
    doc = URIRef(node_iri("Document", "SQA-THERMO-001"))
    chunks = list(g.objects(doc, p("has_chunk")))
    assert chunks
    mentioned = {o for c in chunks for o in g.objects(c, p("mentions"))}
    assert URIRef(node_iri("SensorModel", "TMP-2210")) in mentioned
    assert URIRef(node_iri("Station", "ST02_SEALING")) in mentioned


def test_datasheet_chunk_mentions_model(ds):
    g = ds.graph(URIRef(GRAPH_IRIS["approved"]))
    c = URIRef(node_iri("Chunk", "DS-THERM-2200-s1"))
    assert (c, URIRef(pred_iri("mentions")), URIRef(node_iri("SensorModel", "TMP-2210"))) in g

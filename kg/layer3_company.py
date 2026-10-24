"""Layer 3: fictional company overlay from data/company.yaml, plus its documents."""
from __future__ import annotations

import re
from pathlib import Path

import yaml
from rdflib import RDF, RDFS, URIRef

from contracts.ids import local_name, node_iri, pred_iri
from kg import layer2_docs, operational
from kg.common import KGDataset, safe_id

COMPANY_YAML = Path("data/company.yaml")
DOCS_DIR = Path("data/docs")


def _iri(cls: str, local_id: str) -> str:
    return node_iri(cls, safe_id(local_id))


def build(ds: KGDataset, yaml_path: Path = COMPANY_YAML, docs_dir: Path = DOCS_DIR) -> KGDataset:
    cfg = yaml.safe_load(Path(yaml_path).read_text())
    src = "company.yaml"
    c = cfg["company"]
    company = ds.add_node("Company", c["id"], c["label"], c["comment"])
    ds.add_edge(company, "operates", _iri("System", c["operates"]), src)
    for cu in cfg["customers"]:
        ds.add_node("Customer", cu["id"], cu["label"], cu["comment"])
    for su in cfg["suppliers"]:
        ds.add_node("Supplier", su["id"], su["label"], su["comment"])
    type_to_model = {}
    for m in cfg["sensor_models"]:
        iri = ds.add_node("SensorModel", m["id"], m["id"], m["comment"], sensorType=m["type"])
        ds.add_edge(iri, "supplied_by", _iri("Supplier", m["supplier"]), src)
        type_to_model[m["type"]] = iri
    g = ds.graph_for("approved")
    for sensor in g.subjects(RDF.type, URIRef(pred_iri("Sensor"))):
        stype = next((str(o) for o in g.objects(sensor, URIRef(pred_iri("sensorType")))), None)
        if stype in type_to_model:
            ds.add_edge(str(sensor), "of_model", type_to_model[stype], src)
    for po in cfg["production_orders"]:
        iri = ds.add_node("ProductionOrder", po["id"], po["id"], po["comment"])
        ds.add_edge(iri, "executed_at", _iri("Station", po["station"]), src)
        ds.add_edge(iri, "ordered_by", _iri("Customer", po["customer"]), src)
    for role, comment in cfg["roles"].items():
        ds.add_node("Role", role, role, comment)
    for person in g.subjects(RDF.type, URIRef(pred_iri("Person"))):
        role = next((str(o) for o in g.objects(person, URIRef(pred_iri("role")))), None)
        if role in cfg["roles"]:
            ds.add_edge(str(person), "has_role", _iri("Role", role), src)
    for d in cfg["documents"]:
        text = (Path(docs_dir) / d["file"]).read_text()
        doc = ds.add_node("Document", d["id"], f"{d['id']} {d['title']}", d["title"], file=d["file"])
        for party in d["parties"]:
            cls = "Company" if party == c["id"] else "Supplier"
            ds.add_edge(_iri(cls, party), "party_to", doc, d["file"])
        sections = re.split(r"^## ", text, flags=re.M)[1:]
        for n, sec in enumerate(sections, start=1):
            title, _, body = sec.partition("\n")
            layer2_docs.add_chunk(ds, doc, d["id"], n, title.strip(), f"{title.strip()}. {' '.join(body.split())}",
                                  1, d["file"])
    for file in cfg.get("machine_data", []):
        operational.build(ds, Path(docs_dir) / file)
    layer2_docs.link_mentions(ds)
    return ds

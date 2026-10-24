"""Layer 1: iMAKS kg_seed CSVs -> approved RDF."""
from __future__ import annotations

import csv
from pathlib import Path

from contracts.ids import node_iri
from kg.common import KGDataset, parse_number

CLASS_MAP = {"Component": "Station"}
NO_PROP = {"label", "name", "description"}


def _local_id(row: dict, cls: str) -> str:
    if cls in ("System", "Zone", "Station", "Sensor"):
        return row["name"]
    if cls == "Person":
        return row["personId"] or row["nodeId"]
    if cls == "Maintenance":
        return row["ruleId"] or row["nodeId"]
    return row["eventId"] or row["nodeId"]


def _label(row: dict, cls: str, lid: str) -> str:
    if cls == "Person":
        return f"{lid} ({row['role']})" if row["role"] else lid
    if cls == "Maintenance":
        return f"{lid}: {row['action']}"
    if cls in ("AnomalyEvent", "SafetyEvent"):
        return f"{lid} {row.get('anomalyType') or row.get('type') or ''}".strip()
    return lid


def build(raw_dir: Path, ds: KGDataset | None = None) -> KGDataset:
    ds = ds or KGDataset()
    seed = Path(raw_dir) / "kg_seed"
    iri_of: dict[str, str] = {}
    cls_of: dict[str, str] = {}
    with open(seed / "nodes.csv", newline="") as f:
        for row in csv.DictReader(f):
            cls = CLASS_MAP.get(row["label"], row["label"])
            lid = _local_id(row, cls)
            props = {k: parse_number(v) for k, v in row.items() if v and k not in NO_PROP}
            iri = ds.add_node(cls, lid, _label(row, cls, lid), row["description"] or None, **props)
            iri_of[row["nodeId"]] = iri
            cls_of[row["nodeId"]] = cls
    with open(seed / "edges.csv", newline="") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):  # row 1 is the header
            s, o = row["fromId"], row["toId"]
            if row["type"] == "monitors" and cls_of[s] == "Station":
                continue  # reverse duplicate of Sensor monitors Station
            ds.add_edge(iri_of[s], row["type"], iri_of[o], f"imaks:edges.csv#{i}")
    return ds

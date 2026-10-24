"""Rebuild everything: `uv run python -m kg.build`."""
from __future__ import annotations

import json
from pathlib import Path

from contracts.models import Proposal
from kg import layer1_imaks, layer2_docs, layer3_company
from kg.common import RAW_DIR, KGDataset
from kg.download import download

OUT = Path("data/graph")
PROPOSALS = Path("data/proposals.json")


def add_proposals(ds: KGDataset, path: Path = PROPOSALS) -> list[Proposal]:
    """Edge proposals become edges in their status graph; node proposals also get a `mentions` edge from the evidence
    chunk, so they are connected. Predicate proposals only live in proposals.json: the ontology is frozen."""
    if not path.exists():
        return []
    props = [Proposal.model_validate(x) for x in json.loads(path.read_text())]
    for p in props:
        creator = "analyst" if p.status != "proposed" else p.proposed_by
        if p.kind == "edge":
            ds.add_edge(p.triple.s, p.triple.p.rsplit("#", 1)[-1], p.triple.o, p.evidence_chunk_id or "proposals.json",
                        creator=creator, graph=p.status)
        elif p.kind == "node":
            iri = ds.add_node(p.node.cls, p.node.local_id, p.node.label, p.node.description, graph=p.status)
            if p.evidence_chunk_id:
                ds.add_edge(p.evidence_chunk_id, "mentions", iri, p.evidence_chunk_id, creator=creator, graph=p.status)
    return props


def build(raw_dir: Path = RAW_DIR) -> KGDataset:
    download(raw_dir)
    ds = KGDataset()
    layer1_imaks.build(raw_dir, ds)
    layer2_docs.build(raw_dir, ds)
    layer3_company.build(ds)
    add_proposals(ds)
    return ds


def write(ds: KGDataset, out: Path = OUT) -> None:
    ds.serialize(destination=str(out / "kg.trig"), format="trig")
    with open(out / "provenance.jsonl", "w") as f:
        for p in ds.prov:
            f.write(p.model_dump_json() + "\n")


if __name__ == "__main__":
    ds = build()
    write(ds)
    print(f"wrote {OUT}/kg.trig and {len(ds.prov)} provenance rows")

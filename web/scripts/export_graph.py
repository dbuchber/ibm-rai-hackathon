"""Writes web/public/data/graph_export.json from data/graph/kg.trig (approved + proposed).

Run from the repo root: uv run python web/scripts/export_graph.py
"""

from collections import Counter
from pathlib import Path

from contracts.rdf_store import RdfGraphStore

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "web/public/data/graph_export.json"

export = RdfGraphStore(ROOT / "data/graph/kg.trig").export({"approved", "proposed"})
OUT.write_text(export.model_dump_json(indent=1))
print(f"{len(export.nodes)} nodes, {len(export.edges)} edges -> {OUT.relative_to(ROOT)}")
print("classes:", dict(Counter(n.cls for n in export.nodes).most_common()))
print("edges:", dict(Counter(e.graph for e in export.edges)))

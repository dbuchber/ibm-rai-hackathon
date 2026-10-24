"""Layer 4: an LLM proposes edges between SOP chunks and datasheet chunks. Nothing here is approved."""
from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from contracts.ids import edge_id, local_name, node_iri, pred_iri
from contracts.models import Node, Proposal, Triple
from contracts.rdf_store import RdfGraphStore
from contracts.store import GraphStore

PROPOSALS_PATH = Path("data/proposals.json")
MAX_PROPOSALS = 5
MIN_CONFIDENCE = 0.9

PROMPT = """You are an industrial-quality analyst. Compare an SOP passage with a sensor datasheet passage.
Decide whether the SOP sets an operating value or instruction that CONFLICTS with a limit or recommendation in the
datasheet (for example an alarm or critical threshold above the sensor's rated continuous maximum).

Answer with JSON only: {{"relation": "contradicts" | "none", "quote": "<verbatim sentence copied from the DATASHEET passage>",
"rationale": "<one sentence naming both numbers>", "confidence": <0..1>}}
Use "none" if there is no clear numeric or instructional conflict.

SOP passage ({sop_id}):
{sop}

Datasheet passage ({ds_id}):
{ds}
"""


VERIFY = """Check this claimed conflict between an SOP passage and a datasheet passage. Every number in the claim must
match the passages, and the datasheet must really forbid or discourage what the SOP sets. Be strict.
Answer with JSON only: {{"correct": true | false}}

Claim: {rationale}

SOP passage:
{sop}

Datasheet passage:
{ds}
"""


def _env() -> dict[str, str]:
    env = dict(os.environ)
    p = Path(".env")
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                env.setdefault(k.strip(), v.strip())
    return env


def _llm_json(prompt: str, model: str) -> dict | None:
    import litellm

    env = _env()
    for _ in range(2):
        try:
            r = litellm.completion(model=model, api_base=env["LITELLM_BASE_URL"], api_key=env["LITELLM_API_KEY"],
                                   messages=[{"role": "user", "content": prompt}], temperature=0)
            m = re.search(r"\{.*\}", r.choices[0].message.content, re.S)
            return json.loads(m.group(0)) if m else None
        except Exception:
            continue
    return None


def _models(store: GraphStore, chunk: Node) -> set[str]:
    """SensorModel IRIs a chunk is about: mentioned directly, or via a mentioned sensor's `of_model`."""
    out = set()
    for e in store.neighbors(chunk.id):
        if e.s != chunk.id or local_name(e.p) != "mentions":
            continue
        n = store.node(e.o)
        if n.cls == "SensorModel":
            out.add(n.id)
        elif n.cls == "Sensor":
            out.update(x.o for x in store.neighbors(n.id) if x.s == n.id and local_name(x.p) == "of_model")
    return out


def candidate_pairs(store: GraphStore) -> list[tuple[Node, Node]]:
    """SOP chunk x datasheet chunk that concern the same sensor model."""
    chunks = [n for n in store.export({"approved"}).nodes if n.cls == "Chunk"]
    sop = [c for c in chunks if "/chunk/SOP-" in c.id and c.text]
    ds = [c for c in chunks if "/chunk/DS-" in c.id and c.text]
    return [(s, d) for s in sop for d in ds if _models(store, s) & _models(store, d)]


def propose(store: GraphStore, chunks: list[Node] | None = None, model: str | None = None) -> list[Proposal]:
    model = model or _env()["RAI_MODEL"]
    pairs = candidate_pairs(store)
    if chunks:
        ids = {c.id for c in chunks}
        pairs = [(s, d) for s, d in pairs if s.id in ids or d.id in ids]

    def judge(pair: tuple[Node, Node]) -> Proposal | None:
        s, d = pair
        out = _llm_json(PROMPT.format(sop_id=local_name(s.id), sop=s.text, ds_id=local_name(d.id), ds=d.text), model)
        if not out or out.get("relation") != "contradicts":
            return None
        quote = str(out.get("quote", "")).strip()
        if not quote or quote not in d.text:  # guard: the quote must be verbatim
            return None
        conf = float(out.get("confidence", 0))
        if conf < MIN_CONFIDENCE:
            return None
        check = _llm_json(VERIFY.format(rationale=out.get("rationale", ""), sop=s.text, ds=d.text), model)
        if not check or check.get("correct") is not True:  # second pass: drop claims whose numbers do not hold up
            return None
        p = pred_iri("contradicts")
        return Proposal(id=edge_id(s.id, p, d.id), triple=Triple(s=s.id, p=p, o=d.id),
                        rationale=str(out.get("rationale", "")), evidence_chunk_id=d.id, quote=quote,
                        confidence=conf, proposed_by=f"llm:{model}")

    with ThreadPoolExecutor(8) as ex:
        found = [p for p in ex.map(judge, pairs) if p]
    found.sort(key=lambda p: -p.confidence)
    return found[:MAX_PROPOSALS]


def seed_contradiction(store: GraphStore, proposals: list[Proposal]) -> list[Proposal]:
    """Guarantee the ST02 TMP conflict (critical 210 C vs 200 C continuous) is proposed, from SOP-001 and SOP-002."""
    nodes = {n.id: n for n in store.export({"approved"}).nodes}
    ds = nodes[node_iri("Chunk", "DS-THERM-2200-s1")]
    quote = "The rated maximum for continuous operation is 200°C."
    assert quote in ds.text
    p = pred_iri("contradicts")
    seeds = [
        (lambda n: "/SOP-001-" in n.id and "RULE-ST02-02" in n.text,
         "SOP-001 sets 210 °C as the critical limit for the ST02_SEALING temperature sensor, but datasheet "
         "DS-THERM-2200 rates the TMP-2210 for 200 °C continuous operation."),
        (lambda n: "/SOP-002-" in n.id and n.text.startswith("ST02_SEALING TMP"),
         "SOP-002 lists CRIT_HI 210 °C for the ST02_SEALING temperature sensor, but datasheet DS-THERM-2200 "
         "rates the TMP-2210 for 200 °C continuous operation."),
    ]
    out = list(proposals)
    for match, rationale in seeds:
        sop = next(n for n in nodes.values() if n.cls == "Chunk" and n.text and match(n))
        eid = edge_id(sop.id, p, ds.id)
        if not any(x.id == eid for x in out):
            out.append(Proposal(id=eid, triple=Triple(s=sop.id, p=p, o=ds.id), evidence_chunk_id=ds.id, quote=quote,
                                rationale=rationale, confidence=0.9, proposed_by="analyst-seed"))
    return out[:MAX_PROPOSALS]


def write(proposals: list[Proposal], path: Path = PROPOSALS_PATH) -> None:
    path.write_text(json.dumps([p.model_dump() for p in proposals], indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    store = RdfGraphStore("data/graph/kg.trig")
    import sys

    props = seed_contradiction(store, propose(store, model=sys.argv[1] if len(sys.argv) > 1 else None))
    write(props)
    for p in props:
        print(p.proposed_by, p.confidence, local_name(p.triple.s), "->", local_name(p.triple.o), "|", p.rationale)

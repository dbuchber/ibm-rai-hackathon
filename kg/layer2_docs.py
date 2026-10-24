"""Layer 2: iMAKS SOP + datasheet PDFs -> Document/Chunk nodes, mentions, Rule nodes."""
from __future__ import annotations

import csv
import re
from pathlib import Path

from pypdf import PdfReader
from rdflib import RDF, RDFS, URIRef

from contracts.ids import GRAPH_IRIS, KG, ONT, local_name, node_iri, pred_iri
from kg.common import KGDataset, parse_number, safe_id

# Datasheet chunks that never spell out a model code (analyst-approved mapping).
DATASHEET_MODELS = {"DS-ELEC-3300": ["CT-3300"]}
MENTION_CLASSES = ("Station", "Sensor", "SensorModel", "Rule", "Maintenance", "Zone")
RULE_FALLBACKS = {  # rule-id prefix -> keyword that identifies the chunk defining it
    "RULE-ACK": "Acknowledgment", "RULE-OCC": "Maximum Occupancy", "RULE-ANOM": "Anomaly Type",
    "RULE-CORR": "Correlated Fault",
}
SENSOR_CODES = ("TMP", "PRS", "FLW", "CUR", "SPD", "TEN", "CNT", "VIB", "HUM")


def _approved(ds: KGDataset):
    return ds.graph_for("approved")


def _nodes_of(ds: KGDataset, cls: str) -> list[str]:
    return [str(s) for s in _approved(ds).subjects(RDF.type, URIRef(pred_iri(cls)))]


def _pdf_lines(path: Path) -> list[tuple[int, str]]:
    out = []
    for i, page in enumerate(PdfReader(str(path)).pages, start=1):
        for line in (page.extract_text() or "").splitlines():
            line = line.strip().replace("R&D;", "R&D")
            if line:
                out.append((i, line))
    return out


def _repair(text: str, ds: KGDataset) -> str:
    """Rejoin identifiers that the PDF wrapped mid-word (e.g. `SRV01_SERVERRO OM`)."""
    for iri in _nodes_of(ds, "Station"):
        name = local_name(iri)
        if len(name) < 8:
            continue
        pat = r"\s*".join(re.escape(c) for c in name)
        text = re.sub(pat, name, text)
    return text


def _split(lines: list[tuple[int, str]], is_start) -> list[tuple[int, str, list[str]]]:
    """Group lines into (page, title, body lines); `is_start(line)` opens a new group."""
    groups: list[tuple[int, str, list[str]]] = []
    for page, line in lines:
        if is_start(line):
            groups.append((page, line, []))
        elif groups:
            groups[-1][2].append(line)
    return groups


def add_chunk(ds: KGDataset, doc_iri: str, doc_id: str, n: int, title: str, text: str, page: int,
              source: str, station: str | None = None, creator: str = "script") -> str:
    iri = ds.add_node("Chunk", f"{doc_id}-s{n}", f"{doc_id} §{title}", None, text=text, page=page)
    ds.add_edge(doc_iri, "has_chunk", iri, f"{source}#p{page}", creator)
    ds.chunk_meta[iri] = {"station": station, "source": f"{source}#p{page}", "creator": creator}
    return iri


def _parse_doc_header(lines: list[tuple[int, str]]) -> tuple[str, str, dict]:
    head, title_parts = {}, []
    for _, line in lines[:6]:
        if line.startswith("Document:"):
            for part in line.split("|"):
                k, _, v = part.partition(":")
                head[k.strip()] = v.strip()
            break
        title_parts.append(line)
    return head["Document"], " ".join(title_parts), head


def _station_ids(ds: KGDataset) -> list[str]:
    return [local_name(i) for i in _nodes_of(ds, "Station")]


def build_pdf(ds: KGDataset, path: Path) -> str:
    lines = _pdf_lines(path)
    doc_id, title, head = _parse_doc_header(lines)
    idx = next(i for i, (_, l) in enumerate(lines) if l.startswith("Document:"))
    body = lines[idx + 1:]
    short = title.split(" — ")[0]
    doc = ds.add_node("Document", doc_id, f"{doc_id} {short}", title, rev=head.get("Rev", ""),
                      date=head.get("Date", ""), author=head.get("Author", ""), file=path.name)
    stations = _station_ids(ds)
    chunks: list[tuple[int, str, str, str | None]] = []  # page, title, text, primary station
    if doc_id == "SOP-001":
        for page, t, b in _split(body, lambda l: re.match(r"^(\d+(\.\d+)?)\.? \S", l) is not None and
                                  not l.startswith("RULE") and re.match(r"^\d", l) is not None
                                  and "L/min" not in l and "bar" not in l):
            m = re.match(r"^2\.\d+ (\S+)", t)
            chunks.append((page, t, " ".join([t] + b), m.group(1) if m else None))
        # the section "2." heading has no rules of its own; drop empty ones
        chunks = [c for c in chunks if not re.fullmatch(r"2\. Station-Level Operating Rules", c[2])]
    elif doc_id == "SOP-002":
        station = None
        row_start = re.compile(rf"^({'|'.join(SENSOR_CODES)})$")
        cur: tuple[int, str, str | None, list[str]] | None = None
        for page, line in body:
            m = re.match(r"^(\S+) Thresholds$", line)
            if m or line.startswith("Anomaly Type Definitions"):
                if cur:
                    chunks.append((cur[0], cur[1], " ".join(cur[3]), cur[2]))
                    cur = None
                if m:
                    station = m.group(1)
                else:
                    cur = (page, "Anomaly Type Definitions", None, [line])
                continue
            if cur is None and station is None:
                continue
            if row_start.match(line) and station and True:
                if cur:
                    chunks.append((cur[0], cur[1], " ".join(cur[3]), cur[2]))
                cur = (page, f"{station} {line} thresholds", station, [f"{station} {line}:"])
            elif cur and re.match(r"^(Sensor|Unit|CRIT_|WARN|LO|HI|Nominal|CRITICAL Response|_)", line) is None:
                cur[3].append(line)
        if cur:
            chunks.append((cur[0], cur[1], " ".join(cur[3]), cur[2]))
    elif doc_id == "SOP-003":
        for page, t, b in _split(body, lambda l: re.match(r"^(MAINT-\d\d$|2\. Correlated)", l) is not None):
            m = re.match(r"^MAINT-\d\d", t)
            text = " ".join([t] + b)
            st = next((s for s in stations if s in _repair(text, ds)), None) if m else None
            chunks.append((page, t, text, st))
    elif doc_id == "SOP-004":
        for page, t, b in _split(body, lambda l: re.match(r"^\d\. [A-Z]", l) is not None):
            chunks.append((page, t, " ".join([t] + b), None))
    else:  # datasheets: one chunk per numbered section
        for page, t, b in _split(body, lambda l: re.match(r"^\d\. [A-Z]", l) is not None):
            chunks.append((page, t, " ".join([t] + b), None))
        if not chunks:
            chunks.append((1, title, " ".join(l for _, l in body), None))
    for n, (page, t, text, st) in enumerate(chunks, start=1):
        text = _repair(text, ds).replace("pcs/m in", "pcs/min")
        if st:
            st = _repair(st, ds)
        short_t = re.sub(r"\s+", " ", t)[:60]
        c = add_chunk(ds, doc, doc_id, n, short_t, text, page, path.name, st)
        if doc_id in DATASHEET_MODELS and not re.search(r"\b[A-Z]{2,3}-\d{4}\b", text):
            for m in DATASHEET_MODELS[doc_id]:
                ds.chunk_meta[c].setdefault("models", []).append(m)
    return doc


def link_mentions(ds: KGDataset) -> None:
    """`Chunk mentions X` for exact ID matches only. Idempotent."""
    ids: dict[str, list[tuple[str, str]]] = {}
    sensors: dict[str, dict[str, str]] = {}  # station local -> {code: sensor iri}
    for cls in MENTION_CLASSES:
        for iri in _nodes_of(ds, cls):
            key = str(next(_approved(ds).objects(URIRef(iri), RDFS.label))) if cls == "Zone" else local_name(iri)
            ids.setdefault(key, []).append((cls, iri))
    for local, items in ids.items():
        for cls, iri in items:
            if cls == "Sensor":
                for code in SENSOR_CODES:
                    if local.endswith("_" + code):
                        sensors.setdefault(local[: -len(code) - 1], {})[code] = iri
    patterns = {k: re.compile(rf"(?<![\w-]){re.escape(k)}(?![\w-])") for k in ids}
    for chunk in _nodes_of(ds, "Chunk"):
        node = URIRef(chunk)
        text_objs = list(_approved(ds).objects(node, URIRef(pred_iri("text"))))
        if not text_objs:
            continue
        text = str(text_objs[0])
        meta = ds.chunk_meta.get(chunk, {})
        src, creator = meta.get("source", "unknown"), meta.get("creator", "script")
        found: set[str] = set()
        for local, pat in patterns.items():
            if pat.search(text):
                found.update(iri for _, iri in ids[local])
        for st, by_code in sensors.items():
            for code, siri in by_code.items():
                if re.search(rf"(?<![\w-]){re.escape(st)}[-_ ]{code}(?![\w-])", text):
                    found.add(siri)
        prim = meta.get("station")
        if prim:
            for code, siri in sensors.get(prim, {}).items():
                if re.search(rf"(?<![\w/]){code}(?![\w])", text):
                    found.add(siri)
        for m in meta.get("models", []):
            found.update(iri for cls, iri in ids.get(m, []) if cls == "SensorModel")
        for iri in found:
            if iri != chunk:
                ds.add_edge(chunk, "mentions", iri, src, creator)


def _chunk_of_rule(ds: KGDataset, row: dict, doc_chunks: list[tuple[str, str, str | None]]) -> str | None:
    rid = re.sub(r"(?<=\d)[ab]$", "", row["ruleId"])
    pat = re.compile(rf"(?<![\w-]){re.escape(rid)}(?![\w-])")
    for iri, text, _ in doc_chunks:
        if pat.search(text):
            return iri
    if row["sensorType"] and row["station"]:
        for iri, text, st in doc_chunks:
            if st == row["station"] and re.search(rf"(?<![\w]){row['sensorType']}(?![\w])", text) \
                    and row["class"] == "ThresholdRule":
                return iri
    for prefix, kw in RULE_FALLBACKS.items():
        if row["ruleId"].startswith(prefix):
            for iri, text, _ in doc_chunks:
                if kw in text:
                    return iri
    if row["station"]:
        for iri, text, _ in doc_chunks:
            if row["station"] in text:
                return iri
    return doc_chunks[0][0] if doc_chunks else None


def add_rules(ds: KGDataset, raw_dir: Path) -> None:
    by_doc: dict[str, list[tuple[str, str, str | None]]] = {}
    g = _approved(ds)
    for doc in _nodes_of(ds, "Document"):
        did = local_name(doc)
        for c in g.objects(URIRef(doc), URIRef(pred_iri("has_chunk"))):
            text = str(next(g.objects(c, URIRef(pred_iri("text")))))
            by_doc.setdefault(did, []).append((str(c), text, ds.chunk_meta.get(str(c), {}).get("station")))
    zones = {z: node_iri("Zone", safe_id(z)) for z in ("Production Area", "Server Room", "General Warehouse",
                                              "Main Entrance", "Chemical Storage", "R&D Lab", "Cafeteria")}
    with open(Path(raw_dir) / "kg_seed" / "ground_truth.csv", newline="") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            props = {k: parse_number(row[k]) for k in
                     ("class", "severity", "action", "critHi", "warnHi", "critLo", "warnLo", "unit", "sensorType")
                     if row[k]}
            props["ruleClass"] = props.pop("class")
            rule = ds.add_node("Rule", row["ruleId"], row["ruleId"], row["condition"], **props)
            src = f"imaks:ground_truth.csv#{i}"
            st = row["station"]
            st_iri = node_iri("Station", safe_id(st)) if st else None
            if st_iri and URIRef(st_iri) in set(_approved(ds).subjects(RDF.type, None)):
                ds.add_edge(rule, "applies_to", st_iri, src)
            elif st:
                z = zones.get(st)  # zone names, e.g. "Chemical Storage"
                z = z if z and URIRef(z) in set(_approved(ds).subjects(RDF.type, None)) else None
                if z:
                    ds.add_edge(rule, "applies_to", z, src)
            if row["sensor"]:
                s_iri = node_iri("Sensor", row["sensor"])
                if URIRef(s_iri) in set(_approved(ds).subjects(RDF.type, None)):
                    ds.add_edge(rule, "applies_to", s_iri, src)
            ch = _chunk_of_rule(ds, row, by_doc.get(row["source"], []))
            if ch:
                ds.add_edge(rule, "defined_in", ch, src)


def build(raw_dir: Path, ds: KGDataset) -> KGDataset:
    raw = Path(raw_dir)
    for pdf in sorted((raw / "rules").glob("*.pdf")) + sorted((raw / "datasheets").glob("*.pdf")):
        build_pdf(ds, pdf)
    add_rules(ds, raw)
    link_mentions(ds)
    return ds

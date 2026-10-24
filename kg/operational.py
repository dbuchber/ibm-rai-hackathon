"""Project a selected synthetic machine replay into timestamped, citable graph evidence.

This is a fixture adapter, not a live connector. Observation approval means the
fixture source is accepted; it does not approve maintenance or production release.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from rdflib import RDF, URIRef

from contracts.ids import node_iri, pred_iri
from kg.common import KGDataset
from kg.layer2_docs import add_chunk


def _time(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("Replay timestamps must include a timezone")
    return result


def build(ds: KGDataset, path: Path) -> None:
    data = json.loads(path.read_text())
    if data["schema_version"] != 1 or data["synthetic"] is not True:
        raise ValueError("Only version 1 synthetic replay sources are supported")
    cutoff = _time(data["as_of"])
    station = node_iri("Station", data["station_id"])
    graph = ds.graph_for("approved")

    def require(iri: str, cls: str) -> None:
        if (URIRef(iri), RDF.type, URIRef(pred_iri(cls))) not in graph:
            raise ValueError(f"Replay references unknown {cls}: {iri}")

    require(station, "Station")
    source = path.as_posix()
    doc_id = data["source_id"]
    doc = ds.add_node("Document", doc_id, f"{doc_id} {path.stem}",
                      "Synthetic operational replay; historical fixture, not a live feed.",
                      file=path.name, asOf=data["as_of"], incidentId=data["incident_id"])
    header = (f"Synthetic replay for {data['station_id']}, incident {data['incident_id']}, "
              f"order {data['production_order_id']}. Selected time: {data['as_of']}. "
              "This source provides observations, not repair or restart approval. ")

    if "samples" in data:
        samples = sorted((s for s in data["samples"] if _time(s["observed_at"]) <= cutoff),
                         key=lambda s: _time(s["observed_at"]))
        lines = []
        sensors = set()
        for sample in samples:
            values = []
            for m in sample["measurements"]:
                sensor = node_iri("Sensor", m["sensor_id"])
                require(sensor, "Sensor")
                sensors.add(sensor)
                values.append(f"{m['sensor_id']}={m['value']} {m['unit']} (quality={m['quality']})")
            lines.append(f"{sample['sample_id']} at {sample['observed_at']}: "
                         f"state={sample['machine_state']}; " + "; ".join(values) + ".")
        latest = samples[-1] if samples else None
        fresh = (latest is not None and
                 (cutoff - _time(latest["observed_at"])).total_seconds() <= data["fresh_for_seconds"] and
                 all(m["quality"] == "good" for m in latest["measurements"]))
        text = header + f"Latest snapshot fresh with good quality: {fresh}. " + " ".join(lines)
        text += " Stopped readings do not establish recovery. " + data["sampling_note"]
        chunk = add_chunk(ds, doc, doc_id, 1, "Machine observations", text, 1, source)
        for sensor in sensors:
            ds.add_edge(chunk, "mentions", sensor, source)
        ds.add_edge(chunk, "mentions", station, source)
    else:
        events = sorted((e for e in data["events"] if _time(e["occurred_at"]) <= cutoff),
                        key=lambda e: _time(e["occurred_at"]))
        active: dict[str, bool] = {}
        for event in events:
            transition = event["transition"]
            if transition not in {"activated", "cleared", "acknowledged"}:
                raise ValueError(f"Unknown alarm transition: {transition}")
            if transition != "acknowledged":
                active[event["alarm_instance_id"]] = transition == "activated"
        for n, event in enumerate(events, 1):
            sensor = node_iri("Sensor", event["sensor_id"])
            require(sensor, "Sensor")
            text = header + json.dumps(event, ensure_ascii=False) + (
                f" Active at selected time: {active.get(event['alarm_instance_id'], 'unknown')}. "
                "Controller action is a request; confirm machine state using telemetry. "
                "The cause is unconfirmed; no repair or restart release is recorded.")
            node = ds.add_node("AnomalyEvent", event["event_id"],
                               f"{event['event_id']} {event['alarm_code']}", text,
                               occurredAt=event["occurred_at"], asOf=data["as_of"])
            ds.add_edge(sensor, "triggers", node, source)
            chunk = add_chunk(ds, doc, doc_id, n, event["event_id"], text, 1, source)
            for target in (station, sensor, node):
                ds.add_edge(chunk, "mentions", target, source)

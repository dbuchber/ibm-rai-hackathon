import json
from pathlib import Path

import pytest
from rdflib import URIRef

from contracts.ids import node_iri, pred_iri
from kg.common import KGDataset
from kg.operational import build


def seeded():
    ds = KGDataset()
    for station, suffixes in (("ST04_PACKAGING", ("VIB", "SPD", "CUR")),
                              ("ST02_SEALING", ("TMP", "CUR")),
                              ("ST01_FILLING", ("PRS", "FLW"))):
        ds.add_node("Station", station, station)
        for suffix in suffixes:
            ds.add_node("Sensor", f"{station}_{suffix}", suffix)
    return ds


def text(ds):
    return " ".join(str(t) for t in ds.graph_for("approved").objects(None, URIRef(pred_iri("text"))))


def test_replay_links_alarm_and_telemetry_to_same_sensor():
    ds = seeded()
    for filename in ("ST04_Telemetry.json", "ST04_AlarmEvents.json"):
        build(ds, Path("data/docs") / filename)
    g = ds.graph_for("approved")
    sensor = URIRef(node_iri("Sensor", "ST04_PACKAGING_VIB"))
    alarm = URIRef(node_iri("AnomalyEvent", "EVT-ST04-001-B"))
    assert (sensor, URIRef(pred_iri("triggers")), alarm) in g
    assert (URIRef(node_iri("Chunk", "TEL-ST04-001-s1")), URIRef(pred_iri("mentions")), sensor) in g
    assert "STOPPED_PROTECTIVE" in text(ds)
    assert "Active at selected time: True" in text(ds)


def test_future_samples_are_excluded_and_stale_data_is_identified(tmp_path):
    data = json.loads(Path("data/docs/ST04_Telemetry.json").read_text())
    data["as_of"] = "2026-10-24T09:51:00+02:00"
    path = tmp_path / "telemetry.json"
    path.write_text(json.dumps(data))
    ds = seeded()
    build(ds, path)
    assert "TEL-ST04-003" in text(ds)
    assert "TEL-ST04-004" not in text(ds)
    assert "Latest snapshot fresh with good quality: False" in text(ds)


def test_unknown_sensor_is_rejected(tmp_path):
    data = json.loads(Path("data/docs/ST04_Telemetry.json").read_text())
    data["samples"][0]["measurements"][0]["sensor_id"] = "UNKNOWN"
    path = tmp_path / "telemetry.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="unknown Sensor"):
        build(seeded(), path)


def test_alarm_clearance_respects_selected_time(tmp_path):
    data = json.loads(Path("data/docs/ST04_AlarmEvents.json").read_text())
    data["events"].append(dict(data["events"][1], event_id="FUTURE-CLEAR",
                               transition="cleared", occurred_at="2026-10-24T10:05:00+02:00"))
    path = tmp_path / "alarms.json"
    path.write_text(json.dumps(data))
    ds = seeded()
    build(ds, path)
    assert "FUTURE-CLEAR" not in text(ds)
    assert "Active at selected time: True" in text(ds)
    data["as_of"] = "2026-10-24T10:05:00+02:00"
    path.write_text(json.dumps(data))
    ds = seeded()
    build(ds, path)
    assert "Active at selected time: False" in text(ds)


@pytest.mark.parametrize("prefix,station_id,doc_ids,last_sample", [
    ("ST04", "ST04_PACKAGING", ("EQ", "ALM", "TRB", "HIST", "REC"), "006"),
    ("ST02", "ST02_SEALING", ("EQ", "ALM", "SPEC", "TRB", "HIST", "REC"), "004"),
    ("ST01", "ST01_FILLING", ("EQ", "ALM", "TRB", "HIST", "RES", "REC"), "004"),
])
def test_company_registration_ingests_documents_and_machine_data(prefix, station_id, doc_ids, last_sample):
    from kg.layer3_company import build as company_build

    ds = seeded()
    company_build(ds)
    g = ds.graph_for("approved")
    station = URIRef(node_iri("Station", station_id))
    for kind in doc_ids:
        doc_id = f"{kind}-{prefix}-001"
        chunks = list(g.objects(URIRef(node_iri("Document", doc_id)), URIRef(pred_iri("has_chunk"))))
        assert chunks
        assert any((c, URIRef(pred_iri("mentions")), station) in g for c in chunks)
    assert f"TEL-{prefix}-{last_sample}" in text(ds)


@pytest.mark.parametrize("prefix", ["ST04", "ST02", "ST01"])
def test_alarm_trigger_references_match_machine_observations(prefix):
    telemetry = json.loads(Path(f"data/docs/{prefix}_Telemetry.json").read_text())
    alarms = json.loads(Path(f"data/docs/{prefix}_AlarmEvents.json").read_text())
    for key in ("scenario_id", "incident_id", "station_id", "production_order_id", "as_of"):
        assert alarms[key] == telemetry[key]
    samples = {s["sample_id"]: s for s in telemetry["samples"]}
    for event in alarms["events"]:
        sample = samples[event["trigger_sample_id"]]
        assert sample["observed_at"] == event["occurred_at"]
        measurement = next(m for m in sample["measurements"] if m["sensor_id"] == event["sensor_id"])
        assert measurement["value"] == event["trigger_value"]
        assert measurement["unit"] == event["unit"]
        assert measurement["quality"] == "good"


def test_temperature_excursion_does_not_fabricate_a_critical_trip():
    data = json.loads(Path("data/docs/ST02_AlarmEvents.json").read_text())
    assert {e["alarm_code"] for e in data["events"]} == {"SEAL-TMP-HI", "SEAL-TMP-RANGE"}
    peak = max(e["trigger_value"] for e in data["events"])
    assert 200 < peak < 210


def test_each_scenario_has_separate_citable_evidence():
    ds = seeded()
    for prefix in ("ST01", "ST02", "ST04"):
        build(ds, Path(f"data/docs/{prefix}_Telemetry.json"))
        build(ds, Path(f"data/docs/{prefix}_AlarmEvents.json"))
    g = ds.graph_for("approved")
    for prefix, station in (("ST01", "ST01_FILLING"), ("ST02", "ST02_SEALING"), ("ST04", "ST04_PACKAGING")):
        chunks = list(g.objects(URIRef(node_iri("Document", f"TEL-{prefix}-001")), URIRef(pred_iri("has_chunk"))))
        assert len(chunks) == 1
        assert (chunks[0], URIRef(pred_iri("mentions")), URIRef(node_iri("Station", station))) in g

import random
from pathlib import Path

import pytest

from api.chat_canary import falsify
from api.store import CurationStore
from contracts.models import EventAdapter, NodeSpec

FIX = Path(__file__).resolve().parents[2] / "contracts" / "fixtures"


def _answer():
    events = [EventAdapter.validate_json(l) for l in (FIX / "run_demo.jsonl").read_text().splitlines() if l.strip()]
    return next(e for e in events if e.type == "answer").payload


@pytest.fixture
def store():
    s = CurationStore(FIX / "mini_graph.trig")
    s.add_node(NodeSpec(cls="Supplier", local_id="SensorikNord", label="Sensorik Nord GmbH"))
    return s


@pytest.fixture
def answer():
    return _answer()


# --- falsify ----------------------------------------------------------------

def test_swaps_leaf_supplier(store, answer):
    out, swap = falsify(answer, "Who supplies the sensor?", store, random.Random(0))
    assert "Sensorik Nord GmbH" in out.text and "ThermoSense GmbH" not in out.text
    assert out.citations == answer.citations and out.canary is None
    assert swap.claim == "TMP-2210 supplied by Sensorik Nord GmbH"
    assert swap.truth == "TMP-2210 supplied by ThermoSense GmbH"


def test_never_swaps_the_topic(store, answer):
    assert falsify(answer, "What does ThermoSense GmbH supply?", store, random.Random(0)) is None


def test_none_without_same_class_alternative(answer):
    bare = CurationStore(FIX / "mini_graph.trig")  # only one Supplier
    assert falsify(answer, "Who supplies the sensor?", bare, random.Random(0)) is None

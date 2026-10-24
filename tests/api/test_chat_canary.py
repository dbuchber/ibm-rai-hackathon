import random
from pathlib import Path

import pytest

from api.chat_canary import ChatCanary, falsify
from api.store import CurationStore
from contracts.models import AnswerEvent, EventAdapter, NodeSpec

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


# --- ChatCanary -------------------------------------------------------------

@pytest.fixture
def log():
    return []


@pytest.fixture
def cc(store, log):
    return ChatCanary(lambda: store, lambda k, d, p=None: log.append((k, d, p)), streak=3, rng=random.Random(0))


def ask(cc, session, run_id, answer_event=True) -> bool:
    """One chat turn; True if the streamed answer was falsified."""
    cc.start(session, run_id, "Who supplies the sensor?")
    if not answer_event:
        return False
    out = []
    cc.emit(run_id, out.append)(AnswerEvent(run_id=run_id, seq=0, ts="t", payload=_answer()))
    return "Sensorik Nord GmbH" in out[0].payload.text


def plant(cc, session, run_id):
    for i in range(3):
        assert not ask(cc, session, f"{run_id}-pre{i}")
    assert ask(cc, session, run_id)


def kinds(log):
    return [k for k, *_ in log]


def test_three_blind_answers_then_canary(cc, log):
    assert not any(ask(cc, "s", f"r{i}") for i in range(3))
    assert ask(cc, "s", "r3")
    assert kinds(log).count("canary_planted") == 1


def test_opened_source_resets_counter(cc):
    for i in range(3):
        ask(cc, "s", f"r{i}")
        cc.opened(f"r{i}", "evidence")
    assert not ask(cc, "s", "r3")


def test_flag_on_normal_answer_resets_counter(cc, log):
    for i in range(3):
        ask(cc, "s", f"r{i}")
    assert cc.feedback("s", "r2", "unclear") is None   # r2 was the 3rd blind answer
    assert not ask(cc, "s", "r3")
    assert "feedback" in kinds(log)


def test_flag_on_canary_is_caught_once(cc, log):
    plant(cc, "s", "rc")
    r1 = cc.feedback("s", "rc", "wrong supplier")
    r2 = cc.feedback("s", "rc", None)
    assert r1.outcome == "caught" and r1 == r2
    assert r1.claim == "TMP-2210 supplied by Sensorik Nord GmbH"
    assert kinds(log).count("canary_passed") == 1
    assert cc.start("s", "rn", "q") is None


def test_next_question_reveals_missed(cc, log):
    plant(cc, "s", "rc")
    reveal = cc.start("s", "rn", "next?")
    assert reveal.outcome == "missed" and reveal.run_id == "rc"
    assert {"canary_failed", "supervisor_notified"} <= set(kinds(log))


def test_flag_from_other_session_leaks_nothing(cc):
    plant(cc, "s", "rc")
    assert cc.feedback("other", "rc", "x") is None
    assert cc.start("s", "rn", "q").outcome == "missed"


def test_no_session_never_canary(cc):
    assert not any(ask(cc, None, f"r{i}") for i in range(5))


def test_failed_run_keeps_session_due(cc):
    for i in range(3):
        ask(cc, "s", f"r{i}")
    ask(cc, "s", "r3", answer_event=False)   # run ended in error before the answer
    assert ask(cc, "s", "r4")

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
    return _with_second_supplier(CurationStore(FIX / "mini_graph.trig"))


def _with_second_supplier(s):
    """A second Supplier that really supplies something, so a swap has a plausible target."""
    from contracts.ids import pred_iri
    sup = s.add_node(NodeSpec(cls="Supplier", local_id="SensorikNord", label="Sensorik Nord GmbH"))
    model = s.add_node(NodeSpec(cls="SensorModel", local_id="HUM-2250", label="HUM-2250"))
    s.add_edge(model.id, pred_iri("supplied_by"), sup.id, "approved")
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


# --- review fixes -----------------------------------------------------------

def _single(store, edge, text, question):
    """An answer citing exactly one edge (s, p, o local names) with the given text."""
    from contracts.ids import edge_id, node_iri, pred_iri
    from contracts.models import AnswerPayload, Citation
    e = next(x for x in store._edges.values() if x.id == edge)
    return AnswerPayload(text=text, justification="", citations=[Citation(edge_id=e.id)]), question


def _edge(store, s_local, p, o_local):
    from contracts.ids import local_name
    return next(e for e in store._edges.values()
                if local_name(e.s) == s_local and local_name(e.p) == p and local_name(e.o) == o_local).id


def test_never_corrupts_longer_labels(store):
    from contracts.ids import pred_iri
    st = store.add_node(NodeSpec(cls="Station", local_id="ST09_FILLING", label="ST09_FILLING"))
    tmp = store.add_node(NodeSpec(cls="Sensor", local_id="ST09_FILLING_TMP", label="ST09_FILLING_TMP"))
    store.add_edge(tmp.id, pred_iri("monitors"), st.id, "approved")
    ans, q = _single(store, _edge(store, "ST02_SEALING_TMP", "monitors", "ST02_SEALING"),
                     "ST02_SEALING_TMP monitors ST02_SEALING.", "What is monitored?")
    hit = falsify(ans, q, store, random.Random(0))
    assert hit is None or "ST02_SEALING_TMP" in hit[0].text


def _model_store(store, *models):
    from contracts.ids import pred_iri
    for i, m in enumerate(models):
        n = store.add_node(NodeSpec(cls="SensorModel", local_id=m, label=m))
        sensor = store.add_node(NodeSpec(cls="Sensor", local_id=f"X{i}_TMP", label=f"X{i}_TMP"))
        store.add_edge(sensor.id, pred_iri("of_model"), n.id, "approved")
    return _single(store, _edge(store, "ST02_SEALING_TMP", "of_model", "TMP-2210"),
                   "The installed sensor is a TMP-2210.", "Which model is installed?")


def test_model_code_swaps_only_within_its_family(store):
    ans, q = _model_store(store, "VIB-4480")
    assert falsify(ans, q, store, random.Random(0)) is None


def test_model_code_swaps_to_same_family(store):
    ans, q = _model_store(store, "VIB-4480", "TMP-2250")
    out, swap = falsify(ans, q, store, random.Random(0))
    assert "TMP-2250" in out.text and swap.claim == "ST02_SEALING_TMP of model TMP-2250"


def test_replacement_only_from_predicate_range(answer):
    s = CurationStore(FIX / "mini_graph.trig")
    s.add_node(NodeSpec(cls="Supplier", local_id="Unused", label="Never Supplies AG"))  # no supplied_by edge
    assert falsify(answer, "Who supplies the sensor?", s, random.Random(0)) is None


def test_falsify_error_keeps_true_answer(cc, monkeypatch):
    import api.chat_canary as mod
    for i in range(3):
        ask(cc, "s", f"r{i}")
    monkeypatch.setattr(mod, "falsify", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    assert not ask(cc, "s", "r3")                     # true answer streamed, no crash
    monkeypatch.undo()
    assert ask(cc, "s", "r4")                         # still due


def test_open_canary_hidden_from_public_audit(cc, log):
    plant(cc, "s", "rc")
    assert cc.hidden(log_entry_detail(log, "canary_planted"))
    assert all("Sensorik" not in d and "rc" not in d for k, d, _ in log if k == "canary_planted")
    cc.start("s", "rn", "q")                          # missed -> resolved
    assert not cc.hidden(log_entry_detail(log, "canary_planted"))


def log_entry_detail(log, kind):
    return next(d for k, d, _ in log if k == kind)


def test_feedback_text_kept_out_of_audit(store, log):
    kept = []
    cc = ChatCanary(lambda: store, lambda k, d, p=None: log.append((k, d, p)), streak=3,
                    rng=random.Random(0), record=kept.append)
    ask(cc, "s", "r0")
    cc.feedback("s", "r0", "my private note")
    assert all("my private note" not in d for _, d, _ in log)
    assert kept[0]["text"] == "my private note" and kept[0]["run_id"] == "r0"

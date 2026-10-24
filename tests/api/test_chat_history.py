import pytest

from api.chat_history import ChatHistory
from api.main import _stub_runner
from contracts.models import AnswerEvent, AnswerPayload, EvidenceEvent, EvidencePayload, Node, RunFinished, \
    RunFinishedEvent
from engine.history import Turn
from tests.api.test_api import _app, _chat_app, _client, _live

pytestmark = pytest.mark.asyncio


def _events(text="A.", status="ok", nodes=("n1", "n2")):
    yield AnswerEvent(run_id="r", seq=0, ts="t", payload=AnswerPayload(text=text, justification="", citations=[]))
    yield EvidenceEvent(run_id="r", seq=1, ts="t", payload=EvidencePayload(
        nodes=[Node(id=i, cls="Sensor", label=i) for i in nodes], edges=[]))
    yield RunFinishedEvent(run_id="r", seq=2, ts="t", payload=RunFinished(status=status))


def _feed(h, session, question, **kw):
    out = []
    sink = h.capture(session, question, out.append)
    for ev in _events(**kw):
        sink(ev)
    return out


async def test_window_keeps_last_three_turns_oldest_first():
    h = ChatHistory()
    for k in range(5):
        _feed(h, "s", f"q{k}", text=f"a{k}")
    assert [t.question for t in h.turns("s")] == ["q2", "q3", "q4"]
    assert h.turns("s")[-1] == Turn(question="q4", answer="a4", evidence=("n1", "n2"))


async def test_sessions_are_separate_and_none_has_no_history():
    h = ChatHistory()
    _feed(h, "s1", "q")
    assert h.turns("s2") == [] and h.turns(None) == []
    sink = []
    assert h.capture(None, "q", sink.append) == sink.append   # no session: the sink is not even wrapped


async def test_failed_or_closed_runs_are_no_turn():
    h = ChatHistory()
    _feed(h, "s", "q", status="error")
    out = []
    sink = h.capture("s", "q", out.append, alive=lambda: False)
    for ev in _events():
        sink(ev)
    assert h.turns("s") == [] and len(out) == 3   # events still flow on


async def test_least_recently_used_session_is_forgotten():
    h = ChatHistory(max_sessions=2)
    for s in ("a", "b", "c"):
        _feed(h, s, "q")
    assert h.turns("a") == [] and h.turns("c")


async def test_runner_gets_the_session_history(tmp_path):
    seen = []
    stub = _stub_runner(0.0)

    def runner(question, store, *, history=None, **kw):
        seen.append((question, [t.question for t in history]))
        stub(question, store, **kw)
    async with _client(_app(tmp_path, runner=runner)) as c:
        await _live(c, "s1")
        await _live(c, "s1")
        await _live(c, "other")
    assert [h for _, h in seen] == [[], ["Who supplies the sensor?"], []]


async def test_canary_answer_never_enters_history_as_truth(tmp_path):
    app = _chat_app(tmp_path)          # streak 1: the second answer is falsified
    async with _client(app) as c:
        await _live(c, "s1")
        _, ev = await _live(c, "s1")
    shown = next(e for e in ev if e["type"] == "answer")["payload"]["text"]
    stored = app.state.chat_history.turns("s1")[-1].answer
    assert "Sensorik Nord GmbH" in shown                 # what the user saw: the planted fact
    assert "Sensorik Nord GmbH" not in stored and "ThermoSense GmbH" in stored   # what follow-ups build on


async def test_admin_reset_clears_history(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "tok")
    app = _chat_app(tmp_path)
    async with _client(app) as c:
        await _live(c, "s1")
        assert app.state.chat_history.turns("s1")
        assert (await c.post("/api/admin/reset", headers={"X-Admin-Token": "tok"})).status_code == 200
    assert app.state.chat_history.turns("s1") == []

from contracts.ids import pred_iri
from engine import strategy
from engine.llm import LLMFormatError

PREDS = [(pred_iri("executed_at"), "order runs at station"), (pred_iri("monitors"), "sensor monitors station")]


def test_unknown_predicates_dropped(monkeypatch):
    plan = strategy._Plan(question_type="t", rationale="r", allowed_predicates=["executed_at", "bogus", pred_iri("monitors")], max_depth=2, prompt="p")
    monkeypatch.setattr(strategy.llm, "complete_json", lambda *a, **k: plan)
    out = strategy.plan("q", PREDS, "m")
    assert out.allowed_predicates == [pred_iri("executed_at"), pred_iri("monitors")]
    assert out.max_depth == 2


def test_malformed_llm_json_falls_back(monkeypatch):
    def boom(*a, **k):
        raise LLMFormatError("bad")
    monkeypatch.setattr(strategy.llm, "complete_json", boom)
    out = strategy.plan("q", PREDS, "m")
    assert set(out.allowed_predicates) == {p for p, _ in PREDS}
    assert out.max_depth == 3

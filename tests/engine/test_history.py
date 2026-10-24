import pytest

from contracts.ids import node_iri
from contracts.models import BaselinePayload, ScoredNode, SeedsPayload, StrategyPayload
from contracts.rdf_store import RdfGraphStore
from engine import answer as ans_mod, history, run, seeds as seeds_mod, strategy, traverse
from engine.history import Turn
from tests.engine.test_answer_evidence import follow_all

SENSOR = node_iri("Sensor", "ST02_SEALING_TMP")
MODEL = node_iri("SensorModel", "TMP-2210")
STATION = node_iri("Station", "ST02_SEALING")
CHUNK = node_iri("Chunk", "DS-THERM-2200-s1")

FIRST = Turn(question="Which temperature sensor is used at ST02_SEALING?",
             answer="ST02_SEALING uses the sensor ST02_SEALING_TMP, model TMP-2210.",
             evidence=(STATION, SENSOR, MODEL, CHUNK))


@pytest.fixture
def store():
    return RdfGraphStore("contracts/fixtures/mini_graph.trig")


def test_context_empty_without_history(store):
    assert history.context([], store) == ""


def test_context_lists_turns_oldest_first_with_entity_labels(store):
    older = Turn(question="Q0?", answer="A0.", evidence=())
    ctx = history.context([older, FIRST], store)
    assert ctx.index("Q0?") < ctx.index(FIRST.question)
    assert "ST02_SEALING_TMP (Sensor)" in ctx and "TMP-2210 (SensorModel)" in ctx
    assert "DS-THERM-2200 §1" not in ctx          # chunks are passages, not things "it" refers to
    assert any("most recent" in l and FIRST.question in l for l in ctx.splitlines())


def test_context_truncates_long_answers(store):
    t = Turn(question="q", answer="x" * 5000, evidence=())
    assert len(history.context([t], store)) < 1000


def test_context_skips_unknown_evidence_nodes(store):
    t = Turn(question="q", answer="a", evidence=("https://rai-hackathon.bbger.at/kg/sensor/GONE",))
    assert "GONE" not in history.context([t], store)


def test_carry_over_adds_previous_entities_as_extra_seeds(store):
    sd = SeedsPayload(nodes=[ScoredNode(**store.node(STATION).model_dump(), score=1.2)])
    out = seeds_mod.carry_over("Who supplies it?", store, [FIRST], sd)
    ids = [n.id for n in out.nodes]
    assert ids[0] == STATION                     # the question's own seeds come first, untouched
    assert SENSOR in ids or MODEL in ids
    assert CHUNK not in ids and len(ids) == len(set(ids))
    assert len(ids) <= 1 + seeds_mod.CARRY_OVER


def test_carry_over_prefers_entities_named_in_the_last_answer(store):
    t = Turn(question="q", answer="The model is TMP-2210.", evidence=(STATION, SENSOR, MODEL))
    out = seeds_mod.carry_over("Who supplies it?", store, [t], SeedsPayload(nodes=[]))
    assert out.nodes[0].id == MODEL


def test_carry_over_without_history_is_identity(store):
    sd = SeedsPayload(nodes=[])
    assert seeds_mod.carry_over("q", store, [], sd) is sd


def test_strategy_prompt_carries_the_conversation(monkeypatch):
    seen = []

    def fake(messages, model, schema):
        seen.append(messages[-1]["content"])
        return strategy._Plan(question_type="t", rationale="r", allowed_predicates=["supplied_by"])
    monkeypatch.setattr(strategy.llm, "complete_json", fake)
    strategy.plan("Who supplies it?", [("https://rai-hackathon.bbger.at/ont#supplied_by", "d")], "m",
                  context="CONTEXT-BLOCK")
    assert "CONTEXT-BLOCK" in seen[0] and seen[0].index("CONTEXT-BLOCK") < seen[0].index("Question: Who supplies it?")


def test_run_passes_history_to_every_llm_prompt(store, monkeypatch):
    prompts = []

    def spy(messages, model, schema):
        prompts.append((schema, messages[-1]["content"]))
        if schema is strategy._Plan:
            return strategy._Plan(question_type="t", rationale="r", max_depth=2,
                                  allowed_predicates=[i for i, _ in store.predicates()])
        return follow_all(messages, model, schema)
    for mod in (strategy, traverse, ans_mod):
        monkeypatch.setattr(mod.llm, "complete_json", spy)
    monkeypatch.setattr(run.seeds_mod, "find", lambda q, s: SeedsPayload(nodes=[]))
    rag_q = []
    monkeypatch.setattr(run.baseline, "rag", lambda q, *a, **k: rag_q.append(q) or BaselinePayload(chunks=[], answer="-"))
    events = []
    run.run_question("Who supplies it?", store, model="m", mode="live", emit=events.append, run_id="t",
                     history=[FIRST])
    assert events[-1].payload.status == "ok"
    schemas = {s for s, _ in prompts}
    assert {strategy._Plan, traverse._StepOut, ans_mod._Out} <= schemas
    assert all(FIRST.question in p for _, p in prompts)
    seeds = next(e for e in events if e.type == "seeds").payload
    assert seeds.nodes, "previous evidence must seed the follow-up"
    assert FIRST.question in rag_q[0] and "Who supplies it?" in rag_q[0]
    started = next(e for e in events if e.type == "run.started").payload
    assert started.question == "Who supplies it?"


def test_run_without_history_prompts_unchanged(store, monkeypatch):
    prompts = []

    def spy(messages, model, schema):
        prompts.append(messages[-1]["content"])
        return strategy._Plan(question_type="t", rationale="r", max_depth=1, allowed_predicates=[])
    monkeypatch.setattr(strategy.llm, "complete_json", spy)
    monkeypatch.setattr(run.seeds_mod, "find", lambda q, s: SeedsPayload(nodes=[]))
    monkeypatch.setattr(run.baseline, "rag", lambda *a, **k: BaselinePayload(chunks=[], answer="-"))
    run.run_question("q", store, model="m", mode="live", emit=lambda e: None, run_id="t")
    assert prompts[0].startswith("Question: q")

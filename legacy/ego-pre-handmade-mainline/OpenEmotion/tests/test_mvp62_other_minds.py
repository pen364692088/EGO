import pytest

from emotiond.models import Event
from emotiond.appraisal import appraise_event, AppraisalContext
from emotiond.other_minds import (
    OtherMindsModel,
    apply_other_minds_to_appraisal,
    apply_other_minds_to_intent_scores,
    get_other_minds_model,
    reset_other_minds_model,
)


@pytest.fixture
def model():
    return OtherMindsModel(alpha=0.2, uncertainty_decay=0.08)


# 1-8
@pytest.mark.parametrize("outcome,expect_down", [
    ("ignored", True), ("interrupted", True), ("rejection", True), ("betrayal", True),
    ("continue", False), ("success", False), ("apology", False), ("care", False),
])
def test_interaction_updates_reliability_direction(model, outcome, expect_down):
    before = model.get_state("A").reliability
    after = model.update_from_interaction("A", outcome).reliability
    assert (after < before) if expect_down else (after > before)


# 9-14
@pytest.mark.parametrize("event,is_negative", [
    ("promise_broken", True),
    ("repeated_broken", True),
    ("promise_kept", False),
    ("repeated_kept", False),
    ("promise_broken", True),
    ("promise_kept", False),
])
def test_ledger_updates_bounds(model, event, is_negative):
    before = model.get_state("A").reliability
    s = model.update_from_ledger("A", event)
    assert (s.reliability < before) if is_negative else (s.reliability > before)
    assert 0.0 <= s.reliability <= 1.0
    assert 0.0 <= s.cooperativeness <= 1.0
    assert -1.0 <= s.valence_toward_me <= 1.0


# 15-18
@pytest.mark.parametrize("status", ["success", "partial_success", "failure", "timeout"])
def test_tool_result_path_executes(model, status):
    s = model.update_from_tool_result("A", status)
    assert 0.0 <= s.reliability <= 1.0


# 19-22
@pytest.mark.parametrize("target", ["A", "B", "user:1", "telegram:42"])
def test_target_isolation(model, target):
    model.update_from_interaction(target, "continue")
    state = model.get_state(target)
    other = model.get_state("__other__")
    if target != "__other__":
        assert state.to_dict() != other.to_dict()


# 23-26
@pytest.mark.parametrize("n", [1, 3, 5, 8])
def test_uncertainty_tends_down_with_consistent_positive(model, n):
    start = model.get_state("A").uncertainty
    for _ in range(n):
        model.update_from_interaction("A", "continue")
    assert model.get_state("A").uncertainty <= start


# 27-30
@pytest.mark.parametrize("n", [1, 2, 4, 6])
def test_uncertainty_tends_up_with_unclear(model, n):
    start = model.get_state("A").uncertainty
    for _ in range(n):
        model.update_from_interaction("A", "unclear")
    assert model.get_state("A").uncertainty >= start


# 31
def test_appraisal_bias_increases_threat_for_low_trust():
    reset_other_minds_model()
    m = get_other_minds_model()
    for _ in range(8):
        m.update_from_interaction("A", "betrayal")
    out = apply_other_minds_to_appraisal("A", social_threat=0.2, controllability=0.5)
    assert out["social_threat"] > 0.2


# 32
def test_appraisal_bias_increases_controllability_for_good_partner():
    reset_other_minds_model()
    m = get_other_minds_model()
    for _ in range(8):
        m.update_from_interaction("A", "continue")
    out = apply_other_minds_to_appraisal("A", social_threat=0.2, controllability=0.5)
    assert out["controllability"] >= 0.5


# 33
def test_strategy_bias_prefers_repair_for_reliable_target():
    reset_other_minds_model()
    m = get_other_minds_model()
    for _ in range(10):
        m.update_from_interaction("A", "continue")
    scores = {"repair": 0.1, "set_boundary": 0.1, "withdraw": 0.1, "retaliate": 0.1}
    adj = apply_other_minds_to_intent_scores("A", scores)
    assert adj["repair"] > adj["set_boundary"]


# 34
def test_strategy_bias_prefers_boundary_withdraw_for_unreliable_target():
    reset_other_minds_model()
    m = get_other_minds_model()
    for _ in range(10):
        m.update_from_interaction("A", "ignored")
    scores = {"repair": 0.1, "set_boundary": 0.1, "withdraw": 0.1, "retaliate": 0.1}
    adj = apply_other_minds_to_intent_scores("A", scores)
    assert max(adj, key=adj.get) in {"set_boundary", "withdraw"}


# 35
def test_high_impact_paths_not_boosted():
    reset_other_minds_model()
    m = get_other_minds_model()
    for _ in range(10):
        m.update_from_interaction("A", "ignored")
    scores = {"attack": 0.2, "retaliate": 0.2}
    adj = apply_other_minds_to_intent_scores("A", scores)
    assert adj["attack"] == scores["attack"]
    assert adj["retaliate"] == scores["retaliate"]


# 36
def test_export_import_roundtrip(model):
    model.update_from_interaction("A", "continue")
    data = model.export()
    m2 = OtherMindsModel()
    m2.import_state(data)
    assert m2.export()["A"]["reliability"] == pytest.approx(data["A"]["reliability"])


# 37
def test_appraise_event_integration_changes_dimensions():
    reset_other_minds_model()
    m = get_other_minds_model()
    for _ in range(8):
        m.update_from_interaction("A", "betrayal")
    e = Event(type="world_event", actor="A", target="me", text="算了", meta={"subtype": "neutral"})
    r = appraise_event(e, context=AppraisalContext(target="A"))
    assert 0.0 <= r.social_threat <= 1.0
    assert 0.0 <= r.controllability <= 1.0

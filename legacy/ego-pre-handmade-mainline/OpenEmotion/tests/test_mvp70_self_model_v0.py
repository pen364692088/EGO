import pytest

from emotiond.self_model.legacy import build_self_model_v0, render_self_report


class DummyEmotion:
    energy = 0.42
    social_safety = 0.58
    uncertainty = 0.2
    regulation_budget = 0.88
    energy_budget = 0.75


def test_build_self_model_v0_maps_runtime_state():
    rel = {"bond": 0.31, "grudge": 0.44, "trust": 0.55, "repair_bank": 0.12}
    m = build_self_model_v0(
        focus_target="alice",
        emotion_state=DummyEmotion(),
        relationship=rel,
        ledger_summary={"promise_count": 1, "violation_count": 0},
    )
    assert m.relational.focus_target == "alice"
    assert m.bodily.energy == pytest.approx(0.42)
    assert m.relational.grudge == pytest.approx(0.44)
    assert m.cognitive.confidence == pytest.approx(0.8)


def test_render_self_report_contains_evidence_refs():
    rel = {"bond": 0.5, "grudge": 0.1, "trust": 0.6, "repair_bank": 0.0}
    m = build_self_model_v0(focus_target="bob", emotion_state=DummyEmotion(), relationship=rel)
    r = render_self_report(m, evidence={"ledger": {"promise_count": 2}, "episode_refs": ["ep-1"]})
    assert "self_model" in r
    assert r["summary"]["focus_target"] == "bob"
    assert "self_model_fields" in r["evidence"]
    assert r["evidence"]["ledger"]["promise_count"] == 2

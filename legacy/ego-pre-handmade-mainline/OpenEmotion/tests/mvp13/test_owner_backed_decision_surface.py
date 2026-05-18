from emotiond import core
from openemotion.self_model import SelfModelStore
from openemotion.self_model.model import create_default_self_model


def test_formal_owner_uses_action_confidence_namespace():
    model = create_default_self_model("openemotion")
    model.confidence_by_domain["action:approach"] = 1.0
    model.confidence_by_domain["action.withdraw"] = 0.0

    assert model.get_action_bias("approach") == 1.0
    assert model.get_action_bias("withdraw") == -1.0
    assert model.get_action_bias("boundary") == 0.0


def test_formal_owner_store_prefers_action_bias(tmp_path):
    store = SelfModelStore(base_dir=tmp_path)
    model = create_default_self_model("openemotion")
    model.confidence_by_domain["action:approach"] = 1.0
    model.confidence_by_domain["action.withdraw"] = 0.0
    store.save(model, update_source="test", trace_reference="test:formal_owner_store")

    loaded = store.load("openemotion")
    assert loaded is not None
    assert loaded.get_action_bias("approach") == 1.0


def test_select_action_uses_owner_backed_decision_surface(monkeypatch, tmp_path):
    target = "owner_bias_target"
    core.relationship_manager._ensure_relationship_fields(target)

    store = SelfModelStore(base_dir=tmp_path / "self_model_store")
    model = create_default_self_model(target)
    model.confidence_by_domain = {
        "action:approach": 1.0,
        "action:withdraw": 0.0,
    }
    store.save(model, update_source="test", trace_reference="test:owner_bias_target")
    monkeypatch.setattr(core, "_formal_self_model_store", store)
    monkeypatch.setattr(core, "score_action", lambda action, state, relationship, pred: 0.0)

    def fake_get_auto_tune_param(name: str, default):
        if name == "self_bias_weight":
            return 1.0
        if name.startswith("residual_"):
            return 0.0
        return default

    monkeypatch.setattr(core, "get_auto_tune_param", fake_get_auto_tune_param)

    def fail_legacy_lookup(_target: str):
        raise AssertionError("legacy bias path should not be used when owner-backed surface is available")

    monkeypatch.setattr(core, "get_self_model_v0", fail_legacy_lookup)

    selected = core.select_action(core.emotion_state, target, test_mode=True)

    assert selected == "approach"

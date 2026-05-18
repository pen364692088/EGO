from scripts.auto_tune_v0_3 import KnobRegistry


def test_knob_registry_rejects_hard_freeze_key():
    reg = KnobRegistry()
    result = reg.validate_candidate({"signature_secret": 0.1})
    assert not result.accepted
    assert result.reason_code == "HARD_FREEZE_VIOLATION"


def test_knob_registry_rejects_non_allowlist_key():
    reg = KnobRegistry()
    result = reg.validate_candidate({"totally_new_knob": 0.1})
    assert not result.accepted
    assert result.reason_code == "KNOB_NOT_ALLOWLISTED"


def test_knob_registry_accepts_valid_knob_subset():
    reg = KnobRegistry()
    result = reg.validate_candidate({"precision_temperature": 0.6, "bond_update_gain": 1.2})
    assert result.accepted

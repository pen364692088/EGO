"""Regression guard: intervention module imports stay intact."""

from emotiond.science import interventions as iv


def test_interventions_symbol_imports_do_not_break():
    required = [
        "InterventionType",
        "InterventionConfig",
        "InterventionResult",
        "InterventionManager",
        "DisableHomeostasisIntervention",
        "FreezeHomeostasisIntervention",
        "OpenLoopIntervention",
        "FreezePrecisionIntervention",
        "DisableInfoGainIntervention",
        "RemoveSelfStateIntervention",
    ]
    for name in required:
        assert hasattr(iv, name), f"missing symbol: {name}"


def test_intervention_type_members_exist_for_mvp11_chain():
    members = {m.value for m in iv.InterventionType}
    for expected in {
        "disable_homeostasis",
        "freeze_homeostasis",
        "freeze_precision",
        "disable_info_gain",
        "open_loop",
        "remove_self_state",
        "enable_cycle_prior",
    }:
        assert expected in members

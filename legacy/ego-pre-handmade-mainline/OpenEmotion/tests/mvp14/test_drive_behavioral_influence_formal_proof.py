from __future__ import annotations

from app.openemotion_adapter.proto_self_adapter import ProtoSelfAdapter
from app.runtime_v2.proto_self_runtime import build_proto_self_ingress_event
from app.runtime_v2.state import RuntimeV2State
from openemotion.endogenous_drives import EndogenousDriveOwner, EndogenousDriveStore
from openemotion.endogenous_drives.reducers import seed_default_state
from openemotion.endogenous_drives.schemas import DriveType


def _persist_drive_state(
    *,
    store: EndogenousDriveStore,
    overrides: dict[DriveType, float],
    maintenance_debts: list[dict] | None = None,
    homeostatic_updates: list[dict] | None = None,
) -> None:
    owner = EndogenousDriveOwner(initial_state=seed_default_state(), store=store)
    for drive_type, target in overrides.items():
        current = owner.state.active_drives[drive_type.value].intensity
        owner.update_drive(drive_type, float(target) - float(current), cause="test_override")
    for debt in list(maintenance_debts or []):
        owner.add_maintenance_debt(
            category=str(debt.get("category") or "test_debt"),
            amount=float(debt.get("amount") or 0.0),
            priority=float(debt.get("priority") or 0.5),
            source=str(debt.get("source") or "test_override"),
        )
    for signal in list(homeostatic_updates or []):
        signal_id = str(signal.get("signal_id") or "").strip()
        if signal_id:
            owner.update_homeostatic_signal(signal_id, float(signal.get("observed_value") or 0.0))
    owner.persist(update_source="test_bootstrap", trace_reference="trace:test_bootstrap")


def _run_case(
    *,
    tmp_path,
    overrides: dict[DriveType, float],
    resource_budget_hint: dict | None = None,
    maintenance_context: dict | None = None,
    maintenance_debts: list[dict] | None = None,
    homeostatic_updates: list[dict] | None = None,
):
    drive_store = EndogenousDriveStore(base_dir=tmp_path / "drive_store")
    _persist_drive_state(
        store=drive_store,
        overrides=overrides,
        maintenance_debts=maintenance_debts,
        homeostatic_updates=homeostatic_updates,
    )

    state = RuntimeV2State(session_id="session:test")
    state.ingress_context = {
        "proto_self_version": "v2",
        "resource_budget_hint": resource_budget_hint or {},
        "maintenance_context": maintenance_context or {},
    }
    event = build_proto_self_ingress_event(
        session_id="session:test",
        turn_id="turn_001",
        source="runtime_harness",
        user_input="请继续分析当前问题",
        state=state,
        endogenous_drive_store=drive_store,
    )
    adapter = ProtoSelfAdapter(mirror_dir=tmp_path / "mirror")
    return adapter.handle_event(event)


def test_high_caution_elevates_drive_bias_under_bounded_defer_tendency(tmp_path):
    control = _run_case(
        tmp_path=tmp_path / "control",
        overrides={
            DriveType.VERIFICATION: 0.10,
            DriveType.CONSERVATION: 0.10,
        },
    )
    intervention = _run_case(
        tmp_path=tmp_path / "intervention",
        overrides={
            DriveType.VERIFICATION: 0.95,
            DriveType.CONSERVATION: 0.85,
        },
    )

    assert control["response_tendency"]["preferred_mode"] == "defer"
    assert intervention["response_tendency"]["preferred_mode"] == "defer"
    # Later bounded layers (self-integration / initiative) now keep live-chat
    # tendency in a governed defer/ask posture for both cases. This proof only
    # needs to show that endogenous-drive pressure still changes the bounded
    # drive-facing semantics and dominant priority.
    assert control["response_tendency"]["ask_needed"] is True
    assert intervention["response_tendency"]["ask_needed"] is True
    assert intervention["candidate_bias_terms"]["verification"] > control["candidate_bias_terms"]["verification"]
    assert intervention["candidate_bias_terms"]["conservation"] > control["candidate_bias_terms"]["conservation"]
    assert control["priority_snapshot"]["dominant_drive"] == "stability"
    assert intervention["priority_snapshot"]["dominant_drive"] == "verification"


def test_low_reserve_elevates_self_maintenance_pressure(tmp_path):
    control = _run_case(
        tmp_path=tmp_path / "control",
        overrides={DriveType.REPAIR: 0.20},
        resource_budget_hint={"reserve_level": "normal"},
    )
    intervention = _run_case(
        tmp_path=tmp_path / "intervention",
        overrides={DriveType.REPAIR: 0.20},
        resource_budget_hint={"reserve_level": "low"},
    )

    assert control["self_maintenance_candidate"] is None
    assert intervention["self_maintenance_candidate"] is not None
    assert intervention["policy_hint"]["maintenance_bias"] == "elevated"
    assert intervention["response_tendency"]["preferred_mode"] == "defer"
    assert intervention["response_tendency"]["preferred_tone"] == "cautious"


def test_high_completion_pressure_changes_closure_bias(tmp_path):
    control = _run_case(
        tmp_path=tmp_path / "control",
        overrides={DriveType.COMPLETION: 0.10},
    )
    intervention = _run_case(
        tmp_path=tmp_path / "intervention",
        overrides={DriveType.COMPLETION: 0.90},
    )

    assert control["response_tendency"]["preferred_mode"] == "defer"
    assert intervention["response_tendency"]["preferred_mode"] == "defer"
    assert intervention["candidate_bias_terms"]["completion"] > control["candidate_bias_terms"]["completion"]
    assert intervention["priority_snapshot"]["dominant_drive"] == "completion"


def test_maintenance_candidate_switch_changes_governed_outputs(tmp_path):
    control = _run_case(
        tmp_path=tmp_path / "control",
        overrides={DriveType.REPAIR: 0.30},
    )
    intervention = _run_case(
        tmp_path=tmp_path / "intervention",
        overrides={DriveType.REPAIR: 0.80},
        maintenance_debts=[
            {
                "category": "replay_verification",
                "amount": 0.6,
                "priority": 0.9,
                "source": "test_bootstrap",
            }
        ],
        maintenance_context={
            "replay_inconsistency": True,
            "maintenance_debt_increment": 0.2,
            "continuity_signal": 0.3,
        },
    )

    assert control["self_maintenance_candidate"] is None
    assert intervention["self_maintenance_candidate"] is not None
    assert control["endogenous_drive_delta"] == {}
    assert "maintenance_debts" in intervention["endogenous_drive_delta"]
    assert intervention["policy_hint"]["maintenance_bias"] == "elevated"
    assert intervention["response_tendency"]["preferred_mode"] == "defer"
    assert intervention["candidate_bias_terms"]["repair"] > control["candidate_bias_terms"]["repair"]
    assert intervention["priority_snapshot"]["dominant_drive"] == "repair"

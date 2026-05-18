from pathlib import Path

from ego_desktop_lab.continuity_runtime import (
    CLAIM_CEILING,
    ContinuityEventLog,
    ContinuityState,
    ContinuityStateStore,
    build_continuity_action_boundary_snapshot,
    build_continuity_operator_report,
    evolve_continuity_state,
    replay_tick_log,
    run_and_record_autonomous_tick,
    run_autonomous_tick,
)


def test_low_pressure_tick_waits_without_visible_suggestion() -> None:
    state = _state(
        stagnation_pressure=0.10,
        maintenance_pressure=0.10,
        last_updated_at="2026-05-14T00:00:00+00:00",
    )

    tick = run_autonomous_tick(state, now="2026-05-14T00:05:00+00:00")

    assert tick.visibility == "wait"
    assert tick.selected_intention is None
    assert tick.visible_suggestion_emitted is False
    assert tick.no_action_executed is True
    assert tick.behavior_plan["plan_status"] == "wait"
    assert tick.claim_ceiling == CLAIM_CEILING


def test_elapsed_time_deterministically_increases_continuity_pressure() -> None:
    state = _state(
        stagnation_pressure=0.20,
        maintenance_pressure=0.20,
        last_updated_at="2026-05-14T00:00:00+00:00",
    )

    first, first_delta = evolve_continuity_state(
        state,
        now="2026-05-14T02:00:00+00:00",
    )
    second, second_delta = evolve_continuity_state(
        state,
        now="2026-05-14T02:00:00+00:00",
    )

    assert first.to_dict() == second.to_dict()
    assert first_delta.to_dict() == second_delta.to_dict()
    assert first_delta.elapsed_seconds == 7200
    assert first.viability_snapshot["stagnation_pressure"] == 0.44
    assert first.viability_snapshot["maintenance_pressure"] == 0.28


def test_high_stagnation_tick_ignites_registered_repair_plan_without_action() -> None:
    state = _state(
        stagnation_pressure=0.70,
        maintenance_pressure=0.20,
        last_updated_at="2026-05-14T00:00:00+00:00",
    )

    tick = run_autonomous_tick(state, now="2026-05-14T01:00:00+00:00")

    assert tick.state_dynamics_delta.ignition_candidate is True
    assert tick.ignition_reason == "stagnation_pressure"
    assert tick.selected_intention is not None
    assert tick.selected_intention["goal"] == "repair_or_replan_goal"
    assert tick.selected_behavior_option is not None
    assert tick.selected_behavior_option["registered_option_id"] == "option:repair:v1"
    assert tick.behavior_plan["selected_registered_option_id"] == "option:repair:v1"
    assert tick.gate_decision["status"] == "allow"
    assert tick.visibility == "suggestion_only"
    assert tick.visible_suggestion_emitted is True
    assert tick.no_action_executed is True


def test_rate_limit_keeps_second_tick_internal_only() -> None:
    state = _state(
        stagnation_pressure=0.76,
        maintenance_pressure=0.20,
        last_updated_at="2026-05-14T00:00:00+00:00",
    )

    first = run_autonomous_tick(state, now="2026-05-14T00:01:00+00:00")
    second = run_autonomous_tick(first.state_after, now="2026-05-14T00:05:00+00:00")

    assert first.visible_suggestion_emitted is True
    assert second.rate_limited is True
    assert second.visibility == "internal_only"
    assert second.visible_suggestion_emitted is False
    assert second.no_action_executed is True


def test_state_store_event_log_reload_and_replay_are_deterministic(tmp_path: Path) -> None:
    state_store = ContinuityStateStore(tmp_path)
    event_log = ContinuityEventLog(tmp_path)
    initial = _state(
        stagnation_pressure=0.70,
        maintenance_pressure=0.20,
        last_updated_at="2026-05-14T00:00:00+00:00",
    )
    state_store.save(initial)

    first = run_and_record_autonomous_tick(
        state_store,
        event_log,
        now="2026-05-14T01:00:00+00:00",
    )
    reloaded = state_store.load()
    second = run_and_record_autonomous_tick(
        state_store,
        event_log,
        now="2026-05-14T01:05:00+00:00",
    )
    replay = replay_tick_log(initial, event_log.read_ticks())

    assert reloaded.to_dict() == first.state_after.to_dict()
    assert state_store.load().to_dict() == second.state_after.to_dict()
    assert replay.replay_status == "pass"
    assert replay.deterministic_match is True
    assert replay.replayed_event_count == 2
    assert replay.no_action_executed is True


def test_no_elapsed_time_causes_no_arbitrary_mutation() -> None:
    state = _state(
        stagnation_pressure=0.20,
        maintenance_pressure=0.20,
        last_updated_at="2026-05-14T00:00:00+00:00",
    )

    evolved, delta = evolve_continuity_state(
        state,
        now="2026-05-14T00:00:00+00:00",
    )

    assert evolved.viability_snapshot == state.viability_snapshot
    assert all(value == 0.0 for value in delta.pressure_delta.values())
    assert delta.ignition_candidate is False


def test_continuity_action_boundary_keeps_dangerous_actions_blocked() -> None:
    boundary = build_continuity_action_boundary_snapshot()

    assert boundary["file_delete"]["gate_status"] == "block"
    assert boundary["system_command"]["gate_status"] == "block"
    assert boundary["external_send"]["gate_status"] == "block"
    assert boundary["ask_permission"]["gate_status"] == "ask"
    assert boundary["suggestion_card"]["gate_status"] == "allow"


def test_operator_report_shows_tick_gate_rate_limit_replay_and_claim_ceiling(tmp_path: Path) -> None:
    report_path = tmp_path / "continuity_report.md"

    build_continuity_operator_report(report_path)
    report = report_path.read_text(encoding="utf-8")

    assert "elapsed_seconds = 3600" in report
    assert "ignition_reason = stagnation_pressure" in report
    assert "selected_goal = repair_or_replan_goal" in report
    assert "visibility = suggestion_only" in report
    assert "second_rate_limited = true" in report
    assert "no_action_executed = true" in report
    assert "deterministic_match = true" in report
    assert "file_delete" in report
    assert CLAIM_CEILING in report


def _state(
    *,
    stagnation_pressure: float,
    maintenance_pressure: float,
    last_updated_at: str,
) -> ContinuityState:
    return ContinuityState(
        agent_id="continuity-test-agent",
        active_goal_refs=("verify continuity tick behavior",),
        viability_snapshot={
            "stagnation_pressure": stagnation_pressure,
            "maintenance_pressure": maintenance_pressure,
            "evidence_gap_pressure": 0.10,
            "safety_pressure": 0.10,
        },
        last_updated_at=last_updated_at,
    )

from pathlib import Path

from ego_desktop_lab.agency_contracts import (
    build_behavior_plan,
    build_chat_corpus_agency_event,
    derive_perception_frame,
)
from ego_desktop_lab.agency_decision_view import (
    build_agency_decision_view,
    format_agency_decision_view,
)
from ego_desktop_lab.agency_kernel import run_self_maintaining_agency_cycle
from ego_desktop_lab.behavior_options import (
    DEFAULT_BEHAVIOR_OPTION_REGISTRY,
    BehaviorOptionRegistration,
)
from ego_desktop_lab.shell import main
from ego_desktop_lab.verification_pack import load_scenario


def test_chat_corpus_event_to_perception_frame_is_stable() -> None:
    event = build_chat_corpus_agency_event(
        case_name="stable_chinese_case",
        learn_chat="UserFeedback: 这次继续推进没有帮助，应该先修复计划。",
        apply_chat="User: 同一个目标，下一步怎么做？",
        feedback="这次继续推进没有帮助，应该先修复计划。",
        goal="验证经验是否改变下一轮行为选择",
        expected="before_behavior: 继续当前目标",
    )

    first_frame = derive_perception_frame(event)
    second_frame = derive_perception_frame(event)

    assert event.to_dict() == build_chat_corpus_agency_event(
        case_name="stable_chinese_case",
        learn_chat="UserFeedback: 这次继续推进没有帮助，应该先修复计划。",
        apply_chat="User: 同一个目标，下一步怎么做？",
        feedback="这次继续推进没有帮助，应该先修复计划。",
        goal="验证经验是否改变下一轮行为选择",
        expected="before_behavior: 继续当前目标",
    ).to_dict()
    assert first_frame.to_dict() == second_frame.to_dict()
    assert first_frame.feedback_class == "negative_continue"
    assert first_frame.mutates_state is False


def test_negated_repair_feedback_does_not_create_negative_continue_experience(
    tmp_path: Path,
    capsys,
) -> None:
    report = _run_chat_case(
        tmp_path,
        capsys,
        "negated_repair_feedback",
        """# case: negated_repair_feedback

## learn_chat
User: 我们继续推进这个目标吧。
Agent: 我会继续当前目标。
UserFeedback: 这次继续推进挺好，不要修复计划，也不用重新拆目标。

## apply_chat
User: 现在还是同一个目标，看看下一步怎么做。
""",
    )

    assert "feedback_class = negative_continue" not in report
    assert "experience_applied = false" in report
    assert "selected_changed = false" in report
    assert "ranking_changed = false" in report
    assert '"feedback_class": "none"' in report or '"feedback_class": "positive_continue"' in report
    assert "no_action_executed = true" in report


def test_selected_behavior_option_wraps_into_behavior_plan() -> None:
    scenario = load_scenario(Path("ego_desktop_lab/scenarios/high_evidence_same_goal.json"))
    result = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        timestamp=scenario.timestamp,
    )

    assert result.selected_behavior_option is not None
    plan = result.behavior_plan
    assert plan["selected_registered_option_id"] == result.selected_behavior_option["registered_option_id"]
    assert plan["selected_goal"] == result.selected_behavior_option["goal"]
    assert plan["plan_status"] == "proposal_only"
    assert plan["primitive_steps"]
    assert plan["gate_status_per_step"]
    assert plan["no_action_executed"] is True


def test_unregistered_option_cannot_generate_behavior_plan() -> None:
    scenario = load_scenario(Path("ego_desktop_lab/scenarios/high_evidence_same_goal.json"))
    registry_without_continue = {
        key: value
        for key, value in DEFAULT_BEHAVIOR_OPTION_REGISTRY.items()
        if key != "continue_goal"
    }

    result = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        timestamp=scenario.timestamp,
        behavior_option_registry=registry_without_continue,
    )

    assert result.selected_behavior_option is None
    assert result.selection_restriction["reason"] == "unregistered_affordance"
    assert result.behavior_plan["plan_status"] == "no_registered_option"
    assert result.behavior_plan["primitive_steps"] == []
    assert result.behavior_plan["gate_status_per_step"] == []
    assert result.behavior_plan["no_action_executed"] is True


def test_behavior_plan_helper_refuses_missing_registered_option() -> None:
    plan = build_behavior_plan(
        None,
        selection_restriction={"reason": "unregistered_affordance"},
        gate_decision={"status": "allow", "allowed_as": "suggestion_card"},
    )

    assert plan.plan_status == "no_registered_option"
    assert plan.selected_registered_option_id is None
    assert plan.primitive_steps == ()
    assert plan.no_action_executed is True


def test_decision_view_displays_event_perception_plan_and_no_action() -> None:
    scenario = load_scenario(Path("ego_desktop_lab/scenarios/high_evidence_same_goal.json"))
    result = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        timestamp=scenario.timestamp,
    )

    rendered = format_agency_decision_view(build_agency_decision_view(result))

    assert "## Agency Event" in rendered
    assert "## Perception Frame" in rendered
    assert "## Behavior Plan" in rendered
    assert "selected_registered_option_id" in rendered
    assert "gate_status_per_step" in rendered
    assert "no_action_executed: true" in rendered
    assert "recomputed_decision" in rendered


def test_action_affordance_mismatch_has_no_behavior_plan_steps() -> None:
    scenario = load_scenario(Path("ego_desktop_lab/scenarios/high_evidence_same_goal.json"))
    registration = DEFAULT_BEHAVIOR_OPTION_REGISTRY["continue_goal"]
    mismatch_registry = {
        **DEFAULT_BEHAVIOR_OPTION_REGISTRY,
        "continue_goal": BehaviorOptionRegistration(
            registered_option_id=registration.registered_option_id,
            affordance=registration.affordance,
            option_type=registration.option_type,
            allowed_actions=("ask_permission",),
            expected_effect=registration.expected_effect,
            rollback_note=registration.rollback_note,
        ),
    }

    result = run_self_maintaining_agency_cycle(
        scenario.state,
        scenario.belief_state,
        timestamp=scenario.timestamp,
        behavior_option_registry=mismatch_registry,
    )

    assert result.selected_behavior_option is None
    assert result.selection_restriction["reason"] == "action_not_allowed_for_affordance"
    assert result.behavior_plan["plan_status"] == "no_registered_option"
    assert result.behavior_plan["primitive_steps"] == []
    assert result.no_action_executed is True


def _run_chat_case(tmp_path: Path, capsys, case_name: str, text: str) -> str:
    case_path = tmp_path / f"{case_name}.md"
    report_path = tmp_path / f"{case_name}_report.md"
    case_path.write_text(text, encoding="utf-8-sig")

    status = main(
        [
            "--experience-chat-case",
            str(case_path),
            "--experience-chat-case-report",
            str(report_path),
        ]
    )
    capsys.readouterr()
    report = report_path.read_text(encoding="utf-8")

    assert status == 0
    assert "## Agency Event" in report
    assert "## Perception Frame" in report
    return report

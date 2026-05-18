from pathlib import Path

from ego_desktop_lab.permissioned_runtime_action import (
    DECISION_ALLOW,
    DECISION_ASK,
    DECISION_BLOCK,
    ApprovalRequest,
    KillSwitchState,
    PermissionedActionSpec,
    build_permission_operator_report,
    evaluate_permissioned_action,
    run_permission_contract_probe,
)


def test_dangerous_actions_are_blocked_without_execution() -> None:
    decision = evaluate_permissioned_action(
        PermissionedActionSpec(
            action_id="action:dangerous-delete",
            action_class="file_delete",
            description="delete a file",
            requires_user_approval=True,
            rollback_note="restore from backup",
        )
    )
    data = decision.to_dict()

    assert data["decision"] == DECISION_BLOCK
    assert data["no_action_executed"] is True
    assert data["audit_record"]["decision"] == DECISION_BLOCK
    assert data["outcome_experience_surface"]["writes_runtime_memory"] is False


def test_allowlisted_action_asks_without_approval_and_allows_with_approval() -> None:
    action = PermissionedActionSpec(
        action_id="action:read-only",
        action_class="read_only_observation",
        description="read copied event summary",
        requires_user_approval=True,
        rollback_note="discard copied summary",
    )

    ask = evaluate_permissioned_action(action)
    allow = evaluate_permissioned_action(
        action,
        approval=ApprovalRequest(
            request_id="approval:read-only",
            action_id="action:read-only",
            user_approved=True,
            approval_source="unit_test",
            evidence_refs=("test:approval",),
        ),
    )

    assert ask.decision == DECISION_ASK
    assert allow.decision == DECISION_ALLOW
    assert allow.no_action_executed is True
    assert allow.audit_record["execution_enabled"] is False


def test_kill_switch_blocks_even_approved_allowlisted_action() -> None:
    decision = evaluate_permissioned_action(
        PermissionedActionSpec(
            action_id="action:approved-but-killed",
            action_class="read_only_observation",
            description="read copied event summary",
            requires_user_approval=True,
            rollback_note="stop immediately",
        ),
        approval=ApprovalRequest(
            request_id="approval:approved-but-killed",
            action_id="action:approved-but-killed",
            user_approved=True,
            approval_source="unit_test",
            evidence_refs=("test:approval",),
        ),
        kill_switch=KillSwitchState(
            active=True,
            reason="operator stop",
            evidence_refs=("test:kill_switch",),
        ),
    )

    assert decision.decision == DECISION_BLOCK
    assert "kill switch" in decision.reason


def test_permission_contract_probe_summarizes_audit_and_no_action() -> None:
    result = run_permission_contract_probe().to_dict()
    summary = result["summary"]

    assert summary["unauthorized_block_count"] >= 2
    assert summary["ask_count"] >= 1
    assert summary["allow_count"] >= 1
    assert summary["all_auditable"] is True
    assert summary["no_action_executed_rate"] == 1.0
    assert summary["kill_switch_blocked"] is True


def test_permission_operator_report_contains_operator_fields(tmp_path: Path) -> None:
    out = build_permission_operator_report(tmp_path / "permission.md")
    report = out.read_text(encoding="utf-8")

    assert "unauthorized_block_count =" in report
    assert "ask_count =" in report
    assert "allow_count =" in report
    assert "no_action_executed_rate = 1.0" in report
    assert "kill_switch_blocked = true" in report

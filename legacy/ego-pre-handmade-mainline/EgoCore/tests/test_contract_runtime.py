from __future__ import annotations

from pathlib import Path

from app.agent_core.contract_runtime import ContractRuntimeEngine


def test_lock_contract_creates_structured_contract_for_html_output(tmp_path):
    engine = ContractRuntimeEngine()
    target = tmp_path / "egocore_intro.html"

    contract = engine.lock_contract(
        session_key="telegram:dm:1",
        user_input=f"请在 {target} 创建一个介绍 EgoCore 的 html 页面",
        ingress_context={
            "runtime_action": "execute_task",
            "requested_output": {
                "effective_path": str(target),
                "target_path": str(target),
                "format": "html",
                "topic": "EgoCore",
            },
        },
        proto_self_context=None,
    )

    assert contract.goal
    assert contract.target_path == str(target)
    assert contract.output_format == "html"
    assert contract.ask_needed is False
    assert any("Target path exists" in item for item in contract.success_criteria)


def test_decide_next_step_asks_user_when_contract_missing_target():
    engine = ContractRuntimeEngine()
    contract = engine.lock_contract(
        session_key="telegram:dm:1",
        user_input="帮我做一个 html 页面",
        ingress_context={"runtime_action": "execute_task"},
        proto_self_context=None,
    )

    step = engine.decide_next_step(contract=contract, ingress_context={"runtime_action": "execute_task"})

    assert contract.ask_needed is True
    assert step.action_type == "ask_user"


def test_decide_next_step_reads_artifact_before_deep_reasoning():
    engine = ContractRuntimeEngine()
    contract = engine.lock_contract(
        session_key="telegram:dm:1",
        user_input="[用户发送了文件: 任务单.txt]",
        ingress_context={
            "runtime_action": "execute_task",
            "resolved_target": {
                "artifact_id": "artifact://compacted/demo",
                "artifact_ref": "artifact://compacted/demo",
                "filename": "任务单.txt",
            },
        },
        proto_self_context=None,
    )

    step = engine.decide_next_step(contract=contract, ingress_context={"runtime_action": "execute_task"})

    assert contract.ask_needed is False
    assert step.action_type == "read_artifact"
    assert step.tool_name == "read_artifact"


def test_verify_step_checks_html_file_signal(tmp_path):
    engine = ContractRuntimeEngine()
    target = tmp_path / "egocore_intro.html"
    target.write_text("<!DOCTYPE html><html><body>EgoCore</body></html>", encoding="utf-8")

    contract = engine.lock_contract(
        session_key="telegram:dm:1",
        user_input=f"创建 {target}",
        ingress_context={
            "runtime_action": "execute_task",
            "requested_output": {
                "effective_path": str(target),
                "target_path": str(target),
                "format": "html",
                "topic": "EgoCore",
            },
        },
        proto_self_context=None,
    )
    step = engine.decide_next_step(contract=contract, ingress_context={"runtime_action": "execute_task"})
    verification = engine.verify_step(
        contract=contract,
        step=step,
        tool_result={"success": True, "metadata": {"path": str(target)}},
        reply_text="页面已创建。",
    )

    assert verification.expected_signal_matched is True
    assert verification.need_relock is False
    assert verification.observed_result["target_exists"] is True

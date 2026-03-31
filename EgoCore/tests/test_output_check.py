from app.response_contract import apply_output_check, build_direct_response_plan, build_runtime_result_response_plan
from app.runtime_v2.run_items import build_run_items_from_request
from app.runtime_v2.state import RuntimeV2State
from app.telegram_runtime_result import TelegramTurnReply, TelegramTurnResult


def test_output_check_falls_back_to_completion_summary_for_terminal_result(tmp_path) -> None:
    state = RuntimeV2State(session_id="s")
    state.ingress_context = {
        "runtime_action": "execute_task",
        "requested_output": {"target_directory": str(tmp_path)},
    }
    run_items = build_run_items_from_request(
        f"在 {tmp_path} 目录下创建 demo.txt。最后做一个print hello world.py文件",
        ingress_context=state.ingress_context,
    )
    for item in run_items:
        item.status = "verified"
    state.set_run_items(run_items)

    result = TelegramTurnResult(
        status="completed_verified",
        state=state,
        reply=TelegramTurnReply(reply_text="", delivery_kind="final", status="completed_verified"),
    )
    plan = build_runtime_result_response_plan(result, state)
    verdict = apply_output_check(plan, state)

    assert verdict.passed is True
    assert verdict.delivery_kind == "final"
    assert verdict.used_host_fallback is True
    assert "已完成这些任务" in verdict.reply_text


def test_output_check_falls_back_to_blocked_summary_for_blocked_result(tmp_path) -> None:
    state = RuntimeV2State(session_id="s")
    state.ingress_context = {
        "runtime_action": "execute_task",
        "requested_output": {"target_directory": str(tmp_path)},
    }
    run_items = build_run_items_from_request(
        f"在 {tmp_path} 目录下创建 demo.txt。然后再创建一个参照youtube的html页面",
        ingress_context=state.ingress_context,
    )
    state.set_run_items(run_items)
    state.ensure_active_run_item_started()

    result = TelegramTurnResult(
        status="blocked",
        state=state,
        reply=TelegramTurnReply(reply_text="", delivery_kind="final", status="blocked"),
    )
    plan = build_runtime_result_response_plan(result, state)
    verdict = apply_output_check(plan, state)

    assert verdict.passed is True
    assert verdict.used_host_fallback is True
    assert "当前任务无法继续推进" in verdict.reply_text


def test_output_check_preserves_non_empty_direct_reply() -> None:
    state = RuntimeV2State(session_id="s")
    plan = build_direct_response_plan(
        "当前没有运行中的任务。",
        kind="status_probe",
        delivery_kind="final",
        authority_source="test",
    )
    verdict = apply_output_check(plan, state)
    assert verdict.passed is True
    assert verdict.used_host_fallback is False
    assert verdict.reply_text == "当前没有运行中的任务。"


def test_output_check_rewrites_directory_listing_to_verbatim_output() -> None:
    state = RuntimeV2State(session_id="s")
    state.last_tool_result = {
        "success": True,
        "tool": "shell",
        "stdout": " Directory of D:\\Project\\AIProject\\MyProject\\Test2\n03/31/2026  04:18 PM               12 demo.txt",
        "metadata": {
            "command": r"dir D:\Project\AIProject\MyProject\Test2",
            "working_directory": r"D:\Project\AIProject\MyProject\Test2",
            "truncated": False,
        },
    }
    plan = build_direct_response_plan(
        "已列出 D:\\Project\\AIProject\\MyProject\\Test2 目录下的文件。",
        kind="completed_verified",
        delivery_kind="final",
        authority_source="test",
    )

    verdict = apply_output_check(plan, state)

    assert verdict.passed is True
    assert verdict.is_evidence_bearing is True
    assert verdict.used_host_verbatim is True
    assert verdict.fidelity_mode == "verbatim"
    assert verdict.fidelity_gap is False
    assert verdict.reply_text.startswith("目录内容如下：\n")
    assert "demo.txt" in verdict.reply_text

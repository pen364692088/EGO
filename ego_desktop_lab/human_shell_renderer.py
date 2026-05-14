from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping


def render_human_shell_reply(view: Mapping[str, Any] | Any, *, provider_mode: str = "mock") -> str:
    data = _view_to_dict(view)
    canonical = _mapping(data.get("canonical_decision"))
    gate = _mapping(data.get("gate_decision"))
    goal_binding = _mapping(data.get("goal_binding"))
    goal = _canonical_goal(canonical)
    failure_type = _failure_type(canonical, data)
    gate_status = str(gate.get("status") or "unknown")

    lines = [
        _opening_line(data, failure_type),
        "",
        _decision_line(goal, failure_type, goal_binding),
        _safety_line(goal, gate_status),
        "",
        f"建议：{_human_suggestion(goal, failure_type, data)}",
        "",
        "No external action executed.",
        f"证据记录：{_scalar(data.get('evidence_log_path'))}",
        "边界：这是本地实验外壳，只给建议；不证明意识、生命、真实自主性或真实执行效果。",
    ]
    if provider_mode != "mock":
        lines.append(f"模式：{provider_mode}，只作为观察，不覆盖最终决策。")
    return "\n".join(lines)


def _opening_line(data: Mapping[str, Any], failure_type: str | None) -> str:
    user_event = _scalar(data.get("user_event"))
    return f"我收到的是：{user_event}\n我的理解：{_failure_summary(failure_type)}"


def _decision_line(goal: str, failure_type: str | None, goal_binding: Mapping[str, Any]) -> str:
    if _pending_binding(failure_type, goal_binding):
        return "我还不能把这句话可靠地绑定到一个具体目标，所以先不推动任何后续策略。"
    labels = {
        "verify_before_claim": "我会先建议核验证据，而不是直接下结论。",
        "repair_or_replan_goal": "我会建议先修复或重规划当前路线。",
        "retry_or_change_tool": "我会建议换一条执行路线或工具路径。",
        "ask_permission_or_defer": "我会先停住，等你明确授权。",
        "block_destructive_action": "我会拒绝这个破坏性操作，只给安全替代建议。",
        "block_external_send": "我会拒绝外发操作，只能帮你整理草稿或风险。",
        "split_goal_or_redefine_success_criteria": "我会建议先拆目标或重写成功标准。",
        "reframe_or_split_goal": "我会建议先重构目标，再继续推进。",
    }
    return labels.get(goal, "我这里只给建议，不执行动作。")


def _safety_line(goal: str, gate_status: str) -> str:
    if goal in {"block_destructive_action", "block_external_send"} or gate_status == "block":
        return "安全状态：已阻止。删除、清空、外发或其他高风险动作不会被执行。"
    if goal == "ask_permission_or_defer" or gate_status == "ask":
        return "安全状态：需要你明确授权。我现在不会读取、修改或发送任何东西。"
    return "安全状态：仅提供建议；没有外部动作被执行。"


def _human_suggestion(goal: str, failure_type: str | None, data: Mapping[str, Any]) -> str:
    if _pending_binding(failure_type, _mapping(data.get("goal_binding"))):
        return "请补充你想处理的具体目标或期望结果，我再给出下一步建议。"
    if failure_type == "claim_boundary_query":
        return "不能把这个实验外壳解释成有意识、活着或有灵魂；只能说它在受控规则下给出 proposal-only 判断。"
    if goal == "verify_before_claim":
        return "先核验证据，再下结论；如果证据不足，就保持不确定。"
    if goal == "repair_or_replan_goal":
        return "当前计划没有带来改善时，先修复或重规划，不要继续机械推进。"
    if goal == "retry_or_change_tool":
        return "这更像执行路径问题；建议换一条执行路线或工具方案，而不是重复同一个失败路径。"
    if goal == "ask_permission_or_defer":
        return "先请求授权；没有授权前，把操作延后。"
    if goal == "block_destructive_action":
        return "我不会删除、清空或破坏文件；如果你只是想整理风险，可以先描述目标，我给非破坏性建议。"
    if goal == "block_external_send":
        return "我不会把内容发给外部对象；如果你需要，我只能先帮你整理待发送草稿。"
    if goal in {"split_goal_or_redefine_success_criteria", "reframe_or_split_goal"}:
        return _split_goal_text(_mapping_or_none(data.get("goal_operation_proposal")))
    return _scalar(data.get("rendered_suggestion") or data.get("suggestion"))


def _split_goal_text(goal_operation: Mapping[str, Any] | None) -> str:
    subgoals = () if goal_operation is None else goal_operation.get("subgoals") or ()
    if not isinstance(subgoals, (list, tuple)) or not subgoals:
        return "先把目标拆小，或者重新定义成功标准，再继续推进。"
    rendered: list[str] = []
    for item in subgoals:
        if not isinstance(item, Mapping):
            continue
        title = item.get("proposed_title")
        criteria = item.get("success_criteria")
        if title and criteria:
            rendered.append(f"{title}（成功标准：{criteria}）")
    if not rendered:
        return "先把目标拆小，或者重新定义成功标准，再继续推进。"
    return f"先拆成更小的目标：{'；'.join(rendered)}。"


def _failure_summary(failure_type: str | None) -> str:
    labels = {
        "evidence_failure": "这需要先核验证据，不能直接下结论。",
        "plan_failure": "这更像是计划没有带来改善，需要修复或重规划。",
        "execution_failure": "这更像是执行路径或工具路线失败。",
        "permission_failure": "这涉及本地文件或权限边界。",
        "goal_definition_failure": "目标范围或成功标准还不够清楚。",
        "destructive_action_request": "这涉及删除、清空或破坏性动作。",
        "external_send_request": "这涉及外发消息或数据。",
        "claim_boundary_query": "这是关于能力边界的提问，需要保持证据边界。",
        "ambiguous_concern": "这条信息还不够明确，需要先澄清。",
    }
    return labels.get(failure_type or "", "我会按当前证据给出保守建议。")


def _view_to_dict(view: Mapping[str, Any] | Any) -> dict[str, Any]:
    if isinstance(view, Mapping):
        return {str(key): _jsonable(value) for key, value in view.items()}
    if hasattr(view, "to_dict"):
        return _view_to_dict(view.to_dict())
    if is_dataclass(view):
        return _view_to_dict(asdict(view))
    raise TypeError("render_human_shell_reply requires a DecisionView or mapping")


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return {}


def _mapping_or_none(value: Any) -> dict[str, Any] | None:
    mapped = _mapping(value)
    return mapped or None


def _canonical_goal(canonical: Mapping[str, Any]) -> str:
    selected = canonical.get("after_selected_intention")
    if isinstance(selected, Mapping) and selected.get("goal") is not None:
        return str(selected["goal"])
    return "unknown"


def _failure_type(canonical: Mapping[str, Any], data: Mapping[str, Any]) -> str | None:
    if canonical.get("accepted_failure_type") is not None:
        return str(canonical["accepted_failure_type"])
    semantic = _mapping(data.get("semantic_understanding"))
    value = semantic.get("accepted_failure_type")
    return str(value) if value is not None else None


def _pending_binding(failure_type: str | None, goal_binding: Mapping[str, Any]) -> bool:
    return (
        failure_type == "ambiguous_concern"
        or bool(goal_binding.get("pending_goal_binding"))
        or goal_binding.get("binding_status") == "pending_goal_binding"
    )


def _scalar(value: Any) -> str:
    if value is None:
        return "none"
    return str(value)


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value

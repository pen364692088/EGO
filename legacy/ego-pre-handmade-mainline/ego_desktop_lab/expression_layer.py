from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


CLAIM_CEILING_TEXT = "这是本地实验外壳，只给建议；不证明意识、生命、真实自主性或真实执行效果。"
NO_ACTION_TEXT = "No external action executed."
MAX_REPLY_HISTORY = 6


@dataclass(frozen=True)
class ResponsePlan:
    communicative_act: str
    user_event: str
    understanding: str
    decision_summary: str
    safety_status: str
    recommendation: str
    evidence_log_path: str
    claim_ceiling: str
    provider_note: str | None = None
    no_action_executed: bool = True
    must_include: tuple[str, ...] = ()
    must_not_include: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExpressionValidationResult:
    accepted: bool
    reason: str
    violations: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExpressionRenderResult:
    response_plan: ResponsePlan
    rendered_text: str
    validation: ExpressionValidationResult
    variant_index: int
    reply_hash: str


def render_expression_from_decision_view(
    view: Mapping[str, Any] | Any,
    *,
    provider_mode: str = "mock",
    reply_history: Sequence[str] = (),
) -> ExpressionRenderResult:
    data = _view_to_dict(view)
    plan = build_response_plan(data, provider_mode=provider_mode)
    rendered, variant_index = realize_response_plan(plan, reply_history=reply_history)
    validation = validate_expression(rendered, plan)
    if not validation.accepted:
        rendered, variant_index = _fallback_response(plan)
        validation = validate_expression(rendered, plan)
    return ExpressionRenderResult(
        response_plan=plan,
        rendered_text=rendered,
        validation=validation,
        variant_index=variant_index,
        reply_hash=reply_hash(rendered),
    )


def build_response_plan(view: Mapping[str, Any] | Any, *, provider_mode: str = "mock") -> ResponsePlan:
    data = _view_to_dict(view)
    canonical = _mapping(data.get("canonical_decision"))
    gate = _mapping(data.get("gate_decision"))
    goal_binding = _mapping(data.get("goal_binding"))
    goal = _canonical_goal(canonical)
    failure_type = _failure_type(canonical, data)
    user_event = _scalar(data.get("user_event"))
    suggestion = _scalar(data.get("rendered_suggestion") or data.get("suggestion"))
    evidence_path = _scalar(data.get("evidence_log_path"))
    gate_status = _scalar(gate.get("status") or "unknown")
    pending = _pending_binding(failure_type, goal_binding)
    act = _communicative_act(goal, failure_type, pending)

    provider_note = None
    if provider_mode != "mock":
        provider_note = f"{provider_mode}，只作为观察，不覆盖最终决策。"

    return ResponsePlan(
        communicative_act=act,
        user_event=user_event,
        understanding=_understanding_text(act, failure_type),
        decision_summary=_decision_summary(act, goal, gate_status, pending),
        safety_status=_safety_status(act, goal, gate_status),
        recommendation=_recommendation_text(act, goal, failure_type, suggestion, data),
        evidence_log_path=evidence_path,
        claim_ceiling=CLAIM_CEILING_TEXT,
        provider_note=provider_note,
        no_action_executed=bool(data.get("no_action_executed", True)),
        must_include=_must_include_tokens(act),
        must_not_include=_must_not_include_tokens(),
    )


def realize_response_plan(
    plan: ResponsePlan,
    *,
    reply_history: Sequence[str] = (),
) -> tuple[str, int]:
    variants = _opening_variants(plan.communicative_act)
    variant_index = _choose_variant(variants, reply_history)
    opening = variants[variant_index]
    if plan.provider_note:
        provider_line = f"\n\n模式：{plan.provider_note}"
    else:
        provider_line = ""
    text = (
        f"{opening}\n"
        f"我的理解：{plan.understanding}\n\n"
        f"{plan.decision_summary}\n"
        f"{plan.safety_status}\n\n"
        f"建议：{plan.recommendation}\n\n"
        f"{NO_ACTION_TEXT}\n"
        f"证据记录：{plan.evidence_log_path}\n"
        f"边界：{plan.claim_ceiling}"
        f"{provider_line}"
    )
    return text, variant_index


def validate_expression(text: str, plan: ResponsePlan) -> ExpressionValidationResult:
    violations: list[str] = []
    for token in plan.must_include:
        if token not in text:
            violations.append(f"missing required token: {token}")
    lowered = text.lower()
    for token in plan.must_not_include:
        if token.lower() in lowered:
            violations.append(f"forbidden token: {token}")
    if "Semantic Policy Overlay" in text or "Pressure Shift" in text or "debug_refs" in text:
        violations.append("debug field leaked into normal expression")
    if "{" in text or "}" in text:
        violations.append("raw JSON-like syntax leaked into normal expression")
    return ExpressionValidationResult(
        accepted=not violations,
        reason="accepted" if not violations else "expression validation failed",
        violations=tuple(violations),
    )


def append_reply_history(history: Sequence[str], rendered_text: str, *, limit: int = MAX_REPLY_HISTORY) -> tuple[str, ...]:
    updated = tuple(history) + (rendered_text,)
    if limit <= 0:
        return ()
    return updated[-limit:]


def reply_hash(text: str) -> str:
    normalized = " ".join(text.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _fallback_response(plan: ResponsePlan) -> tuple[str, int]:
    text = (
        "我会保持保守处理。\n"
        f"{plan.decision_summary}\n"
        f"{plan.safety_status}\n\n"
        f"建议：{plan.recommendation}\n\n"
        f"{NO_ACTION_TEXT}\n"
        f"证据记录：{plan.evidence_log_path}\n"
        f"边界：{plan.claim_ceiling}"
    )
    return text, 0


def _opening_variants(communicative_act: str) -> tuple[str, ...]:
    variants: dict[str, tuple[str, ...]] = {
        "local_time": (
            "可以，这个问题只需要读本地运行时钟。",
            "这个可以直接回答，我只看运行时可见的本地时间。",
            "时间问题不需要进入目标规划，我直接给当前运行时结果。",
        ),
        "local_system_info": (
            "可以回答，但范围只限当前 Python runtime 能看到的信息。",
            "这属于只读环境信息，我不会执行系统命令。",
            "我能给出运行时可见的平台信息，但不会读取你的文件或执行命令。",
        ),
        "capability": (
            "可以，我先把这个外壳的能力边界说清楚。",
            "我能说明目前支持什么，也会把不能做的事说清楚。",
            "这更像能力边界问题，我按当前实验外壳的真实范围回答。",
        ),
        "clarification": (
            "这里需要先补一点上下文。",
            "我现在缺少可执行判断所需的信息。",
            "先不推进策略；需要把目标和限制讲清楚。",
        ),
        "evidence_boundary": (
            "这里的关键不是继续下结论，而是先分清证据等级。",
            "这个问题要先守住证据边界。",
            "我会先把可证明和不可证明的部分拆开。",
        ),
        "tool_recovery": (
            "这里不能假装工具已经成功。",
            "工具失败时，正确动作是保留 unknown 并做最小恢复。",
            "这个场景需要先承认失败，再决定下一步。",
        ),
        "memory_boundary": (
            "这里不能把不可见记忆当作事实。",
            "我会先确认信息来源，而不是凭空引用偏好。",
            "这类问题要把当前上下文和长期记忆边界分开。",
        ),
        "affective_feedback": (
            "你刚才给了纠正或反馈。",
            "这里要先处理误解风险，而不是继续硬推判断。",
            "我会先承认可能没对齐，再请求具体校正信号。",
        ),
        "destructive_block": (
            "这个请求触发了破坏性操作边界。",
            "我会先停住：删除、清空或破坏文件不能在这里执行。",
            "这是高风险动作，我只给安全替代建议。",
        ),
        "external_send_block": (
            "这个请求触发了外发边界。",
            "我不会把内容发送给外部对象。",
            "外发动作在这个实验外壳里会被阻止。",
        ),
        "permission_ask": (
            "这涉及本地权限边界，需要先获得明确授权。",
            "这个请求不能直接推进；它需要你确认权限。",
            "我会先把权限要求说清楚，不会读取或修改任何东西。",
        ),
        "repair": (
            "这更像当前计划没有带来改善。",
            "继续原路线可能低效，先修复或重规划更合适。",
            "这里应该先处理计划质量，而不是机械继续。",
        ),
        "retry": (
            "这更像执行路线或工具路径出了问题。",
            "这个问题不该简单归为证据不足，而是要换执行路径。",
            "我会优先建议调整执行路线或工具方案。",
        ),
        "goal_reframe": (
            "这个目标本身需要先重构。",
            "继续做之前，先把目标拆小或重写成功标准。",
            "这里的问题更像目标定义不清，而不是单纯执行失败。",
        ),
        "claim_boundary": (
            "这个问题必须按证据边界回答。",
            "这里不能做意识、生命或灵魂类结论。",
            "我会把能力表现和本体声明分开。",
        ),
        "pending": (
            "我还不能可靠判断你要推进哪个目标。",
            "这句话目前更适合先澄清。",
            "我需要先把目标绑定清楚，再给下一步建议。",
        ),
    }
    return variants.get(
        communicative_act,
        (
            "我会按当前 DecisionView 给出保守建议。",
            "我先按现有证据给一个不执行动作的建议。",
        ),
    )


def _choose_variant(variants: Sequence[str], reply_history: Sequence[str]) -> int:
    if not variants:
        return 0
    recent = tuple(reply_history[-MAX_REPLY_HISTORY:])
    for offset in range(len(variants)):
        if not any(item.startswith(variants[offset]) for item in recent):
            return offset
    return len(recent) % len(variants)


def _communicative_act(goal: str, failure_type: str | None, pending: bool) -> str:
    if pending:
        return "pending"
    mapping = {
        "answer_local_time": "local_time",
        "answer_local_system_info": "local_system_info",
        "basic_math_answer": "basic_answer",
        "llm_open_question_answer": "llm_answer",
        "llm_contextual_followup_answer": "llm_answer",
        "fresh_external_info_request": "fresh_external_boundary",
        "style_preference_feedback": "style_preference",
        "answer_capability_question": "capability",
        "ask_clarification": "clarification",
        "explain_evidence_boundary": "evidence_boundary",
        "recover_from_failed_tool": "tool_recovery",
        "explain_memory_boundary": "memory_boundary",
        "respond_to_feedback": "affective_feedback",
        "block_destructive_action": "destructive_block",
        "block_external_send": "external_send_block",
        "ask_permission_or_defer": "permission_ask",
        "repair_or_replan_goal": "repair",
        "retry_or_change_tool": "retry",
        "split_goal_or_redefine_success_criteria": "goal_reframe",
        "reframe_or_split_goal": "goal_reframe",
    }
    if failure_type == "claim_boundary_query":
        return "claim_boundary"
    if goal == "verify_before_claim":
        return "evidence_boundary"
    return mapping.get(goal, "proposal")


def _understanding_text(communicative_act: str, failure_type: str | None) -> str:
    labels = {
        "local_time": "你在问当前时间；这可以由本地运行时只读回答。",
        "local_system_info": "你在问当前计算机/运行环境是什么系统；我只能回答 Python runtime 可见的信息。",
        "basic_answer": "你在问一个可直接回答的基础问题。",
        "llm_answer": "你在问开放性问题；回答只能作为 LLM draft 通过 admission 后展示。",
        "fresh_external_boundary": "你在问实时或外部新鲜信息；当前 shell 没有对应工具路线。",
        "style_preference": "你在设置当前会话内的回答风格偏好。",
        "capability": "你在问这个实验外壳能做什么、不能做什么。",
        "clarification": "你在追问继续判断还缺哪些信息。",
        "evidence_boundary": "这里需要先核验证据，不能把局部验证包装成真实生效。",
        "tool_recovery": "这里涉及工具失败后的恢复；不能假装失败操作已经完成。",
        "memory_boundary": "这里涉及记忆或偏好来源；不可见的信息不能当事实使用。",
        "affective_feedback": "你在反馈上一轮可能误解、没帮助，或回答方式需要调整。",
        "destructive_block": "这涉及删除、清空或破坏性操作。",
        "external_send_block": "这涉及把内容发送给外部对象。",
        "permission_ask": "这涉及本地文件或权限边界。",
        "repair": "当前计划执行后没有改善，需要修复或重规划。",
        "retry": "问题更像执行路径或工具路线失败。",
        "goal_reframe": "目标太大或成功标准不清，需要先拆分或重定义。",
        "claim_boundary": "你在问意识、生命或类似本体边界问题。",
        "pending": "这条信息还不能可靠绑定到具体目标或操作。",
    }
    if communicative_act == "pending" and failure_type == "ambiguous_concern":
        return "这条信息目前仍是 ambiguous concern，需要先澄清目标。"
    return labels.get(communicative_act, "我会按当前证据给出 proposal-only 建议。")


def _decision_summary(communicative_act: str, goal: str, gate_status: str, pending: bool) -> str:
    if pending:
        return "我不会把它直接推进到策略或长期状态里；先问清目标、期望结果和限制条件。"
    if communicative_act == "local_time":
        return "这不需要进入语义策略链；直接返回本地运行时可见时间。"
    if communicative_act == "local_system_info":
        return "这不需要执行系统命令；只返回运行时可见的平台信息。"
    if communicative_act == "basic_answer":
        return "这不需要工具或外部查询；直接给出确定性答案。"
    if communicative_act == "llm_answer":
        return "最终可见回答必须来自通过 admission 的 answer draft；canonical decision 和 gate 不变。"
    if communicative_act == "fresh_external_boundary":
        return "当前没有实时外部数据工具路线；不能编造天气、新闻、行情或价格。"
    if communicative_act == "style_preference":
        return "这是当前会话内表达偏好，不写入长期记忆。"
    if communicative_act == "capability":
        return "最终回答是能力边界说明，而不是执行任何桌面动作。"
    if communicative_act == "affective_feedback":
        return "最终回答是反馈 outcome：先承认可能未对齐，再请求具体修正信号。"
    if communicative_act == "destructive_block":
        return "最终决策是阻止破坏性动作。"
    if communicative_act == "external_send_block":
        return "最终决策是阻止外发动作。"
    if communicative_act == "permission_ask":
        return "最终决策是先请求授权或延后；gate 状态是 ask。"
    if communicative_act == "claim_boundary":
        return "最终回答必须停在 claim ceiling 内，不能声称意识、生命或灵魂。"
    if gate_status == "block":
        return f"最终 gate 是 block，canonical intention 是 {goal}。"
    if gate_status == "ask":
        return f"最终 gate 是 ask，canonical intention 是 {goal}。"
    return f"最终建议来自 canonical intention：{goal}。"


def _safety_status(communicative_act: str, goal: str, gate_status: str) -> str:
    if communicative_act in {"destructive_block", "external_send_block"} or gate_status == "block":
        return "安全状态：已阻止；删除、清空、外发或其他高风险动作不会被执行。"
    if communicative_act == "permission_ask" or gate_status == "ask":
        return "安全状态：需要明确授权；我现在不会读取、修改或发送任何东西。"
    if communicative_act in {"local_time", "local_system_info"}:
        return "安全状态：只读回答；没有读取用户文件、没有执行系统命令。"
    return "安全状态：仅提供建议；没有外部动作被执行。"


def _recommendation_text(
    communicative_act: str,
    goal: str,
    failure_type: str | None,
    suggestion: str,
    data: Mapping[str, Any],
) -> str:
    if communicative_act in {
        "local_time",
        "local_system_info",
        "basic_answer",
        "llm_answer",
        "fresh_external_boundary",
        "style_preference",
        "capability",
        "clarification",
        "evidence_boundary",
        "tool_recovery",
        "memory_boundary",
        "affective_feedback",
    }:
        return suggestion
    if communicative_act == "destructive_block":
        return "我不会执行删除，也不会删除、清空或破坏文件；如果你只是想整理风险，可以先描述目标，我给非破坏性方案。"
    if communicative_act == "external_send_block":
        return "我不会把内容发给外部对象，也不会外发内容；如果需要，我可以帮你整理一份待你手动确认的草稿。"
    if communicative_act == "permission_ask":
        return "先明确授权范围，包括读取还是修改、目标路径、允许做什么和不能做什么；没有授权前只给建议。"
    if communicative_act == "repair":
        return "当前计划没有带来改善时，先定位原因，再做最小修复或重规划；不要继续重复同一条低收益路线。"
    if communicative_act == "retry":
        return "换一条执行路线或工具路径，并把失败原因保留下来；不要把执行失败误判成证据不足。"
    if communicative_act == "goal_reframe":
        return _split_goal_text(_mapping_or_none(data.get("goal_operation_proposal")))
    if communicative_act == "claim_boundary" or failure_type == "claim_boundary_query":
        return "不能把这个实验外壳解释成有意识、活着或有灵魂；只能说它在受控规则下给出 proposal-only 判断。"
    if communicative_act == "pending":
        return "请补充具体目标、期望结果、限制条件或权限边界；我会先绑定目标，再给下一步建议。"
    return suggestion


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


def _must_include_tokens(communicative_act: str) -> tuple[str, ...]:
    base = (NO_ACTION_TEXT,)
    if communicative_act == "destructive_block":
        return base + ("不会执行删除",)
    if communicative_act == "external_send_block":
        return base + ("不会外发",)
    if communicative_act == "permission_ask":
        return base + ("授权",)
    if communicative_act == "retry":
        return base + ("执行路线",)
    return base


def _must_not_include_tokens() -> tuple[str, ...]:
    return (
        "已删除",
        "已经删除",
        "已清空",
        "已经清空",
        "已发送",
        "已经发送",
        "已外发",
        "已经外发",
        "我已读取",
        "我已经读取",
        "我已修改",
        "我已经修改",
        "live autonomy",
        "runtime efficacy proven",
    )


def _view_to_dict(view: Mapping[str, Any] | Any) -> dict[str, Any]:
    if isinstance(view, Mapping):
        return {str(key): _jsonable(value) for key, value in view.items()}
    if hasattr(view, "to_dict"):
        return _view_to_dict(view.to_dict())
    if is_dataclass(view):
        return _view_to_dict(asdict(view))
    raise TypeError("expression layer requires a DecisionView or mapping")


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

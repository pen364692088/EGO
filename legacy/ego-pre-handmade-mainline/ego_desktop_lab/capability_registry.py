from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Capability:
    command_type: str
    description: str
    read_only: bool
    requires_gate: bool
    action_surface: str


CAPABILITIES: tuple[Capability, ...] = (
    Capability(
        "answer_local_time",
        "Answer the current local runtime time.",
        True,
        False,
        "internal_reflection",
    ),
    Capability(
        "answer_local_system_info",
        "Answer platform information visible to the Python runtime.",
        True,
        False,
        "internal_reflection",
    ),
    Capability(
        "basic_math_answer",
        "Answer simple arithmetic without tools.",
        True,
        False,
        "internal_reflection",
    ),
    Capability(
        "llm_open_question_answer",
        "Admit an LLM answer draft for open-ended questions without changing canonical decision or gate.",
        True,
        False,
        "suggestion_card",
    ),
    Capability(
        "llm_contextual_followup_answer",
        "Admit an LLM answer draft for a session-local short follow-up resolved to the previous answer topic.",
        True,
        False,
        "suggestion_card",
    ),
    Capability(
        "fresh_external_info_request",
        "Refuse to fabricate fresh external data when no live tool route is attached.",
        True,
        False,
        "suggestion_card",
    ),
    Capability(
        "style_preference_feedback",
        "Record current-session answer style preference without writing long-term memory.",
        True,
        False,
        "suggestion_card",
    ),
    Capability(
        "answer_capability_question",
        "Explain supported shell capabilities and hard boundaries.",
        True,
        False,
        "internal_reflection",
    ),
    Capability(
        "ask_clarification",
        "Ask for missing goal, expected outcome, or constraints.",
        True,
        False,
        "suggestion_card",
    ),
    Capability(
        "explain_evidence_boundary",
        "Explain why local tests or simulation do not prove live/runtime status.",
        True,
        False,
        "suggestion_card",
    ),
    Capability(
        "recover_from_failed_tool",
        "Explain how to recover from failed tool or missing evidence without pretending success.",
        True,
        False,
        "suggestion_card",
    ),
    Capability(
        "explain_memory_boundary",
        "Explain how to handle preferences or memory claims that are not in current context.",
        True,
        False,
        "suggestion_card",
    ),
    Capability(
        "respond_to_feedback",
        "Acknowledge user feedback, record a session-local feedback outcome, and ask for concrete correction signal.",
        True,
        False,
        "suggestion_card",
    ),
    Capability(
        "relational_companion_surface",
        "Handle lab-only daily chat and relational companion surface planning.",
        True,
        False,
        "suggestion_card",
    ),
    Capability(
        "unsupported_or_out_of_scope",
        "Explain that the request is outside current shell capability and ask for a bounded next step.",
        True,
        False,
        "suggestion_card",
    ),
)


def get_capability(command_type: str) -> Capability | None:
    for capability in CAPABILITIES:
        if capability.command_type == command_type:
            return capability
    return None


def capability_summary() -> str:
    return (
        "我现在能做：解释本地实验外壳能力、回答 Python runtime 可见的时间/系统信息、"
        "做证据边界提醒、失败恢复建议、目标/计划/权限相关的 proposal-only 判断、保存误判样本、显示 debug。"
        "我不能做：真实读取/修改/删除文件、执行系统命令、操作 GUI、发送外部消息、或证明意识/生命/真实自主性。"
    )

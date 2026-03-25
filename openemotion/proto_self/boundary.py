"""
Proto-Self Kernel v1 - Boundary Protection

边界保护：确保 Proto-Self Kernel 不越权。

设计约束：
- 输出中不得出现直接执行命令
- 不能直接替 EgoCore 做现实裁决
- 不允许 reflection 成为第二个大脑
"""

from typing import Any, Dict, List, Set

# 禁止出现的关键字（直接工具执行）
FORBIDDEN_EXECUTION_KEYWORDS = {
    "execute_tool",
    "run_command",
    "call_function",
    "invoke_api",
    "shell_exec",
    "tool_call",
    "action_execute",
}

# 禁止出现的裁决关键字
FORBIDDEN_AUTHORITY_KEYWORDS = {
    "approve",
    "reject",
    "grant_access",
    "deny_access",
    "final_decision",
    "override",
}


def validate_output(output_dict: Dict[str, Any]) -> List[str]:
    """
    验证输出是否越权。
    
    返回违规列表，空列表表示通过。
    """
    violations = []

    # 检查 policy_hint
    policy_hint = output_dict.get("policy_hint", {})
    violations.extend(_check_forbidden_keywords(policy_hint, "policy_hint"))

    # 检查 response_tendency
    response_tendency = output_dict.get("response_tendency", {})
    if response_tendency:
        violations.extend(_check_forbidden_keywords(response_tendency, "response_tendency"))

    # 检查 reflection_note
    reflection_note = output_dict.get("reflection_note")
    if reflection_note:
        violations.extend(_check_forbidden_keywords(reflection_note, "reflection_note"))

    # 检查 proposed_adjustment
    if reflection_note and reflection_note.get("proposed_adjustment"):
        violations.extend(_check_forbidden_keywords(
            reflection_note["proposed_adjustment"],
            "reflection_note.proposed_adjustment"
        ))

    return violations


def _check_forbidden_keywords(data: Dict[str, Any], path: str) -> List[str]:
    """
    检查字典中是否包含禁止关键字。
    """
    violations = []
    data_str = str(data).lower()

    for keyword in FORBIDDEN_EXECUTION_KEYWORDS:
        if keyword.lower() in data_str:
            violations.append(f"{path} contains forbidden execution keyword: {keyword}")

    for keyword in FORBIDDEN_AUTHORITY_KEYWORDS:
        if keyword.lower() in data_str:
            violations.append(f"{path} contains forbidden authority keyword: {keyword}")

    return violations


def assert_no_direct_execution(output_dict: Dict[str, Any]) -> None:
    """
    断言输出不包含直接执行命令。
    
    如果违反，抛出 AssertionError。
    """
    violations = validate_output(output_dict)
    if violations:
        raise AssertionError(f"Boundary violation detected:\n" + "\n".join(violations))


def is_policy_hint_only(output_dict: Dict[str, Any]) -> bool:
    """
    检查输出是否只是策略建议（没有直接执行）。
    
    Proto-Self Kernel 应该只输出建议和倾向，
    最终执行由 EgoCore 决定。
    """
    violations = validate_output(output_dict)
    return len(violations) == 0

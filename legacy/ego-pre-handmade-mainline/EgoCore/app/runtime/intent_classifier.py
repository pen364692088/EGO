import asyncio
import json
from typing import Dict, Any

from app.config import load_config, get_config
from app.llm_client import get_llm_client


INTENT_SCHEMA_HINT = {
    "turn_type": "chat|new_task|follow_up|unresolved_request_query|instruction|ambiguous",
    "intent_type": "general_chat|create_artifact|edit_artifact_property|inspect_artifact|batch_edit_artifacts|status_query|other",
    "reuse_task_context": False,
    "reuse_artifact_context": False,
    "target_path": None,
    "target_scope": None,
    "property": None,
    "operation": None,
    "value": None,
    "value_policy": None,
    "needs_clarification": False,
    "plan_outline": []
}


async def classify_intent_llm(user_input: str, session_state: Dict[str, Any]) -> Dict[str, Any]:
    try:
        get_config()
    except Exception:
        load_config(validate=False)

    system_prompt = """你是 EgoCore 的语义意图分类器。\n你的任务不是直接回复用户，而是把当前 turn 分类成结构化 JSON。\n\n要求：\n1. 只输出单个 JSON 对象，不要 markdown\n2. 不要输出解释文字\n3. turn_type 只能是: chat | new_task | follow_up | unresolved_request_query | instruction | ambiguous\n4. intent_type 只能是: general_chat | create_artifact | edit_artifact_property | inspect_artifact | batch_edit_artifacts | status_query | other\n5. 如果消息是在问上一条为什么没回，turn_type 必须是 unresolved_request_query\n6. 如果消息带明确文件路径并要求修改/查看，优先判为 new_task 或 follow_up，不要判成 chat\n7. 对“你好/在吗/还记得我吗”这类普通寒暄，判为 chat\n8. 对“再大一点/看一下/继续/还是太小”这类相对表达，若存在 artifact context，优先判为 follow_up\n9. 输出字段必须包含：turn_type, intent_type, reuse_task_context, reuse_artifact_context, target_path, target_scope, property, operation, value, value_policy, needs_clarification, plan_outline\n"""

    payload = {
        "user_input": user_input,
        "session_state": {
            "active_task_id": session_state.get("active_task_id"),
            "plan_steps_count": len(session_state.get("plan_steps", []) or []),
            "active_target": session_state.get("active_target"),
            "artifact_paths": list((session_state.get("artifact_context_by_path") or {}).keys())[:10],
            "has_artifact_context": bool(session_state.get("artifact_context_by_path")),
        },
        "output_schema": INTENT_SCHEMA_HINT,
    }

    client = get_llm_client()
    resp = await asyncio.to_thread(
        client.generate,
        json.dumps(payload, ensure_ascii=False, indent=2),
        system_prompt,
        temperature=0.1,
        max_tokens=300,
        timeout=45,
    )
    content = (resp.content or "").strip()
    try:
        cleaned = content
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if len(lines) >= 3:
                cleaned = "\n".join(lines[1:-1]).strip()
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()
        start = cleaned.find('{')
        end = cleaned.rfind('}')
        parsed = json.loads(cleaned[start:end+1])
    except Exception:
        parsed = {
            "turn_type": "ambiguous",
            "intent_type": "other",
            "reuse_task_context": False,
            "reuse_artifact_context": False,
            "target_path": None,
            "target_scope": None,
            "property": None,
            "operation": None,
            "value": None,
            "value_policy": None,
            "needs_clarification": False,
            "plan_outline": []
        }
    return parsed

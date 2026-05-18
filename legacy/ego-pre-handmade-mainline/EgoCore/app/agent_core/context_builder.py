from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.session_store import SessionLogManager


SYSTEM_PROMPT = """你是 EgoCore 的原生执行循环。
你的职责：
1. 优先完成用户明确任务
2. 能用工具完成时，使用原生 tool calling
3. 信息不足才提问
4. 不要输出内部协议或多余解释
5. 对单文件写入/修改任务，保持动作直接、内容简洁、结果可验证
6. 任务执行遵守 Contract Lock -> Next Step -> Verify -> Re-lock
7. 每轮只做一个最小动作
"""


class NativeContextBuilder:
    def __init__(self, session_log_manager: Optional[SessionLogManager] = None) -> None:
        self.session_log_manager = session_log_manager or SessionLogManager()

    def build_messages(
        self,
        *,
        session_key: str,
        user_input: str,
        ingress_context: Optional[Dict[str, Any]] = None,
        proto_self_context: Optional[Dict[str, Any]] = None,
        task_contract: Optional[Dict[str, Any]] = None,
        next_step: Optional[Dict[str, Any]] = None,
        verification_result: Optional[Dict[str, Any]] = None,
        max_events: int = 12,
    ) -> List[Dict[str, Any]]:
        history = self.session_log_manager.get_log(session_key).tail(max_events)
        messages: List[Dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]

        if ingress_context:
            messages.append(
                {
                    "role": "system",
                    "content": f"canonical_ingress={ingress_context}",
                }
            )
            resolved_artifact_text = ingress_context.get("resolved_artifact_text")
            if resolved_artifact_text:
                artifact_name = ingress_context.get("resolved_artifact_filename") or "artifact"
                messages.append(
                    {
                        "role": "system",
                        "content": (
                            f"resolved_artifact_filename={artifact_name}\n"
                            "Use this artifact content as the authoritative task/reference source for this turn. "
                            "Do not scan unrelated workspace files to infer the task.\n"
                            f"resolved_artifact_content:\n{resolved_artifact_text}"
                        ),
                    }
                )
        if proto_self_context:
            messages.append(
                {
                    "role": "system",
                    "content": f"proto_self={proto_self_context}",
                }
            )
        if task_contract:
            messages.append(
                {
                    "role": "system",
                    "content": f"task_contract={task_contract}",
                }
            )
        if next_step:
            messages.append(
                {
                    "role": "system",
                    "content": f"next_step={next_step}",
                }
            )
        if verification_result:
            messages.append(
                {
                    "role": "system",
                    "content": f"verification_result={verification_result}",
                }
            )

        for event in history:
            kind = event.get("kind")
            payload = event.get("payload") or {}
            if kind == "telegram_ingress":
                preview = payload.get("text_preview")
                if preview:
                    messages.append({"role": "user", "content": preview})
            elif kind == "telegram_delivery":
                text = payload.get("text")
                if text:
                    messages.append({"role": "assistant", "content": text})

        messages.append({"role": "user", "content": user_input})
        return messages

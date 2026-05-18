from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from .action_protocol import RuntimeV2Action
from .progress_events import ProgressEvent, ProgressEventType, build_progress_event
from .runtime_reply import RuntimeV2Reply, RuntimeV2TurnResult
from .run_items import CompletionGateResult, build_run_item_summary_text, path_matches_canonical, verify_run_item
from .state import RuntimeV2State
from .tool_broker import RuntimeV2ToolBroker
from .verifier import RuntimeV2Verifier

# stdout 截断阈值
MAX_STDOUT_IN_STATE = 2000  # 字符
MAX_STDERR_IN_STATE = 500
EXPLICIT_OUTPUT_FILENAME_RE = re.compile(r"(?<![A-Za-z0-9_.\\/\\-])([A-Za-z0-9][A-Za-z0-9 _.-]{0,120}\.[A-Za-z0-9]{1,8})")
WINDOWS_TARGET_DIRECTORY_RE = re.compile(r"([A-Za-z]:\\[^\"\n\r]+?)(?=\s*目录下)")


def _truncate_tool_result(tool_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    截断 tool_result 的大字段，防止上下文膨胀。
    
    只保留：
    - stdout 前 2000 字符
    - stderr 前 500 字符
    - 其他元数据不变
    """
    if not tool_result:
        return tool_result
    
    result = dict(tool_result)
    
    # 截断 stdout
    stdout = result.get("stdout", "")
    if isinstance(stdout, str) and len(stdout) > MAX_STDOUT_IN_STATE:
        result["stdout"] = stdout[:MAX_STDOUT_IN_STATE] + f"\n... [截断，原文 {len(stdout)} 字符]"
        result["stdout_truncated"] = True
        result["stdout_full_length"] = len(stdout)
    
    # 截断 stderr
    stderr = result.get("stderr", "")
    if isinstance(stderr, str) and len(stderr) > MAX_STDERR_IN_STATE:
        result["stderr"] = stderr[:MAX_STDERR_IN_STATE] + f"\n... [截断]"
        result["stderr_truncated"] = True
    
    # raw 里可能也有大字段
    raw = result.get("raw", {})
    if isinstance(raw, dict):
        raw_stdout = raw.get("output") or raw.get("stdout", "")
        if isinstance(raw_stdout, str) and len(raw_stdout) > MAX_STDOUT_IN_STATE:
            result["raw"] = {
                k: v for k, v in raw.items()
                if k not in ("output", "stdout")
            }
            result["raw"]["output_truncated"] = True
    
    return result


def _extract_explicit_output_filenames(text: str) -> List[str]:
    if not text:
        return []
    filenames: List[str] = []
    for match in EXPLICIT_OUTPUT_FILENAME_RE.findall(text):
        candidate = match.strip().strip("\"'`")
        lowered = candidate.lower()
        if lowered.endswith((".txt", ".py", ".html", ".htm", ".md", ".json", ".js", ".css")):
            filenames.append(candidate)
    deduped: List[str] = []
    seen = set()
    for filename in filenames:
        key = filename.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(filename)
    return deduped


def _infer_target_directory(state: RuntimeV2State) -> Optional[Path]:
    ingress_context = state.ingress_context or {}
    requested_output = ingress_context.get("requested_output") or {}
    resolved_target = ingress_context.get("resolved_target") or {}

    for candidate in (
        requested_output.get("target_directory"),
        requested_output.get("directory_path"),
        resolved_target.get("path"),
        state.last_explicit_target,
    ):
        if not isinstance(candidate, str) or not candidate.strip():
            continue
        path = Path(candidate.strip())
        return path if path.suffix == "" else path.parent

    last_user_turn = state.last_user_turn or ""
    match = WINDOWS_TARGET_DIRECTORY_RE.search(last_user_turn)
    if match:
        return Path(match.group(1))
    return None


def _verify_declared_outputs_exist(state: RuntimeV2State) -> Optional[Dict[str, Any]]:
    if (state.ingress_context or {}).get("runtime_action") != "execute_task":
        return None
    if (state.ingress_context or {}).get("request_mode") == "analyze":
        return None

    obligations = list(state.output_obligations or [])
    filenames = [str(item.get("name") or "") for item in obligations if str(item.get("name") or "").strip()]
    if not filenames:
        filenames = _extract_explicit_output_filenames(state.last_user_turn or "")
    if not filenames:
        return None

    base_dir = _infer_target_directory(state)
    if base_dir is None:
        return None

    missing: List[str] = []
    stale: List[str] = []
    checked_paths: List[str] = []
    task_started_at = state.last_task_started_at or 0.0

    obligation_by_name = {
        str(item.get("name") or "").lower(): item
        for item in obligations
        if str(item.get("name") or "").strip()
    }

    for filename in filenames:
        obligation = obligation_by_name.get(filename.lower()) or {}
        obligation_path_value = obligation.get("path")
        output_path = Path(obligation_path_value) if isinstance(obligation_path_value, str) and obligation_path_value.strip() else (
            Path(filename) if Path(filename).is_absolute() else base_dir / filename
        )
        checked_paths.append(str(output_path))
        if not output_path.exists():
            missing.append(filename)
            continue
        if task_started_at and output_path.stat().st_mtime + 1.0 < task_started_at:
            stale.append(filename)
            continue
        if obligation:
            obligation["status"] = "verified"

    if missing:
        return {
            "passed": False,
            "reason": "declared_output_missing",
            "verifier": "declared_outputs",
            "target": str(base_dir),
            "evidence": {
                "base_dir": str(base_dir),
                "checked_paths": checked_paths,
                "missing_outputs": missing,
            },
            "warnings": [],
        }
    if stale:
        return {
            "passed": False,
            "reason": "declared_output_not_updated",
            "verifier": "declared_outputs",
            "target": str(base_dir),
            "evidence": {
                "base_dir": str(base_dir),
                "checked_paths": checked_paths,
                "stale_outputs": stale,
            },
            "warnings": [],
        }
    return {
        "passed": True,
        "reason": "declared_outputs_verified",
        "verifier": "declared_outputs",
        "target": str(base_dir),
        "evidence": {
            "base_dir": str(base_dir),
            "checked_paths": checked_paths,
        },
        "warnings": [],
    }


def _evaluate_run_items_completion(state: RuntimeV2State) -> Optional[CompletionGateResult]:
    run_items = state.get_run_items() if hasattr(state, "get_run_items") else []
    if not run_items:
        return None

    active_item = state.get_active_run_item() if hasattr(state, "get_active_run_item") else None
    if active_item is not None and active_item.status == "running":
        observation = state.observe_active_run_item_progress()
        active_item = state.get_active_run_item() if hasattr(state, "get_active_run_item") else active_item
        if active_item is not None and active_item.status == "running":
            return CompletionGateResult(
                passed=False,
                reason="current_item_pending",
                pending_items=[
                    item.description for item in state.get_run_items() if item.status != "verified"
                ],
                verification_result=observation,
            )

    active_item = state.get_active_run_item() if hasattr(state, "get_active_run_item") else active_item
    if active_item is not None and active_item.status == "completed":
        verification = verify_run_item(active_item)
        if verification.get("passed"):
            state.mark_active_run_item_verified(verification)
        else:
            state.mark_active_run_item_blocked(verification)
            return CompletionGateResult(
                passed=False,
                reason=verification.get("reason") or "run_item_verification_failed",
                pending_items=[
                    item.description for item in state.get_run_items() if item.status != "verified"
                ],
                verification_result=verification,
            )
    elif active_item is not None and active_item.status == "blocked":
        verification = active_item.verification_result or {}
        return CompletionGateResult(
            passed=False,
            reason=verification.get("reason") or "blocked_current_item",
            pending_items=[
                item.description for item in state.get_run_items() if item.status != "verified"
            ],
            verification_result=verification,
        )

    state.ensure_active_run_item_started()
    remaining_items = [item.description for item in state.get_run_items() if item.status != "verified"]
    if remaining_items:
        return CompletionGateResult(
            passed=False,
            reason="next_item_pending",
            pending_items=remaining_items,
            verification_result={
                "passed": True,
                "reason": "current_item_verified",
                "evidence": {"remaining_items": remaining_items},
            },
        )

    return CompletionGateResult(
        passed=True,
        reason="run_items_verified",
        pending_items=[],
        verification_result={
            "passed": True,
            "reason": "run_items_verified",
            "evidence": {"checked_items": [item.description for item in state.get_run_items()]},
        },
    )


def _build_host_completion_summary(state: RuntimeV2State, fallback_summary: Optional[str]) -> str:
    run_items = state.get_run_items() if hasattr(state, "get_run_items") else []
    if not run_items:
        return fallback_summary or "已完成。"
    verified_items = [item for item in run_items if item.status == "verified"]
    if not verified_items:
        return fallback_summary or "已完成。"
    lines = ["已完成这些任务："]
    for index, item in enumerate(verified_items, start=1):
        lines.append(f"{index}. {build_run_item_summary_text(item)}")
    return "\n".join(lines)


def _build_host_blocked_summary(state: RuntimeV2State, verification: Optional[Dict[str, Any]]) -> str:
    summary = state.get_run_item_status_summary() if hasattr(state, "get_run_item_status_summary") else {}
    completed = list(summary.get("completed") or [])
    active = summary.get("active")
    pending = list(summary.get("pending") or [])
    reason = str((verification or {}).get("reason") or "").strip()
    lines = ["当前任务无法继续推进。"]
    if completed:
        lines.append(f"已完成：{', '.join(completed)}。")
    if active:
        lines.append(f"当前卡住：{active}。")
    if pending:
        lines.append(f"还未开始：{', '.join(pending)}。")
    if reason:
        lines.append(f"失败原因：{reason}。")
    return "\n".join(lines)


class RuntimeV2TransitionEngine:
    def __init__(self, tool_broker: RuntimeV2ToolBroker, verifier: RuntimeV2Verifier) -> None:
        self.tool_broker = tool_broker
        self.verifier = verifier

    async def apply(self, state: RuntimeV2State, action: RuntimeV2Action) -> Dict[str, Any]:
        if action.type == "chat":
            state.task_status = "chat"
            state.last_delivery_type = "chat"
            return {"done": True, "result": RuntimeV2TurnResult(status="chat", state=state, reply=RuntimeV2Reply(reply_text=action.message or "", delivery_kind="chat", status="chat"))}

        if action.type == "ask":
            state.task_status = "waiting_input"
            state.waiting_for_user_input = True
            state.last_delivery_type = "ask"
            return {"done": True, "result": RuntimeV2TurnResult(status="waiting_input", state=state, reply=RuntimeV2Reply(reply_text=action.question or "", delivery_kind="ask", status="waiting_input"))}

        if action.type == "plan":
            state.current_goal = action.goal or state.current_goal
            state.current_step = action.steps[0] if action.steps else state.current_step
            
            # WS-4: 目标选定事件
            if state.last_inferred_target:
                target_event = build_progress_event(
                    ProgressEventType.TARGET_SELECTED,
                    context="task" if state.last_inferred_action == "execute" else "spec",
                    filename=state.last_inferred_target,
                )
                state.push_progress_event(target_event)
            
            return {"done": False}

        if action.type == "act":
            state.mark_task_started(goal=state.current_goal or state.last_user_turn)

            # 递增步骤计数器
            state.current_step_number += 1

            # WS-4: 执行步骤事件（传递动态步骤编号）
            step_event = build_progress_event(
                ProgressEventType.EXECUTING_STEP,
                context="step",
                step=state.current_step_number,
                action=action.tool or "执行",
            )
            state.push_progress_event(step_event)
            
            tool_result = await self.tool_broker.execute(action.tool or "", action.input)
            
            # P0: 截断后再存储
            truncated_result = _truncate_tool_result(tool_result)
            state.last_tool_result = truncated_result
            state.task_status = "running"
            state.current_step = f"tool:{action.tool}"
            
            # WS-4: 检查是否卡住
            if not tool_result.get("success"):
                blocked_reason = tool_result.get("stderr") or tool_result.get("error") or "执行失败"
                blocked_event = build_progress_event(
                    ProgressEventType.BLOCKED,
                    reason="default",
                )
                blocked_event.message = f"这里卡住了：{blocked_reason[:100]}"
                state.push_progress_event(blocked_event)
            
            # P3: history 记录也要截断
            state.record("tool", truncated_result)
            if self._has_host_owned_run_items(state):
                authority_failure = self._enforce_active_run_item_authority(
                    state=state,
                    action=action,
                    tool_result=truncated_result,
                )
                if authority_failure is not None:
                    state.last_verification_result = authority_failure
                    state.record("system", {"run_item_authority_failed": authority_failure})
                    state.mark_active_run_item_blocked(authority_failure)
                    state.task_status = "blocked"
                    state.waiting_for_user_input = False
                    state.last_delivery_type = "blocked"
                    return {
                        "done": True,
                        "result": RuntimeV2TurnResult(
                            status="blocked",
                            state=state,
                            reply=RuntimeV2Reply(
                                reply_text=_build_host_blocked_summary(state, authority_failure),
                                delivery_kind="final",
                                status="blocked",
                            ),
                        ),
                    }
                state.observe_active_run_item_progress(
                    tool_result=truncated_result,
                    tool_name=action.tool,
                    tool_input=action.input,
                )
            return {"done": False}

        if action.type == "complete":
            # WS-4: 验证事件
            verify_event = build_progress_event(ProgressEventType.VERIFYING_RESULT)
            state.push_progress_event(verify_event)

            completion_gate = _evaluate_run_items_completion(state)
            if completion_gate is not None:
                if not completion_gate.passed and completion_gate.reason != "next_item_pending":
                    verification = {
                        "passed": False,
                        "reason": completion_gate.reason,
                        "verifier": "run_items",
                        "target": state.get_active_run_item().canonical_path if state.get_active_run_item() else None,
                        "evidence": {
                            "remaining_items": completion_gate.pending_items,
                            "item_verification": completion_gate.verification_result or {},
                        },
                        "warnings": [],
                    }
                elif not completion_gate.passed:
                    state.last_verification_result = completion_gate.to_dict()
                    state.record("system", {"run_items_pending": completion_gate.pending_items})
                    return {"done": False}
                else:
                    verification = {
                        "passed": True,
                        "reason": completion_gate.reason,
                        "verifier": "run_items",
                        "target": None,
                        "evidence": (completion_gate.verification_result or {}).get("evidence") or {},
                        "warnings": [],
                    }
            else:
                verification = self.verifier.verify_complete(action.verification, state.last_tool_result)

            declared_outputs_verification = None if state.get_run_items() else _verify_declared_outputs_exist(state)
            if verification.get("passed") and declared_outputs_verification and not declared_outputs_verification.get("passed"):
                verification = declared_outputs_verification
            state.last_verification_result = verification
            if verification.get("passed"):
                state.mark_task_completed()
                state.last_delivery_type = "completed"
                
                # WS-4: 完成事件
                completed_event = build_progress_event(ProgressEventType.COMPLETED)
                state.push_progress_event(completed_event)
                
                return {
                    "done": True,
                    "result": RuntimeV2TurnResult(
                        status="completed_verified",
                        state=state,
                        reply=RuntimeV2Reply(
                            reply_text=_build_host_completion_summary(state, action.summary or ""),
                            delivery_kind="final",
                            status="completed_verified",
                        ),
                    ),
                }
            
            # 验证失败，记录
            state.record("system", {"verification_failed": verification})
            state.last_delivery_type = "blocked"
            
            # WS-4: 阻塞事件
            blocked_event = build_progress_event(
                ProgressEventType.BLOCKED,
                reason="default",
            )
            blocked_event.message = f"验证失败：{verification.get('reason', '原因未知')}"
            state.push_progress_event(blocked_event)
            
            return {"done": False}

        return {"done": False}

    def _has_host_owned_run_items(self, state: RuntimeV2State) -> bool:
        return bool(state.get_run_items())

    def _enforce_active_run_item_authority(
        self,
        *,
        state: RuntimeV2State,
        action: RuntimeV2Action,
        tool_result: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        active_item = state.get_active_run_item()
        if active_item is None or not active_item.canonical_path:
            return None

        metadata = dict(tool_result.get("metadata") or {})
        actual_path = metadata.get("path") or (action.input or {}).get("path")
        if active_item.kind == "file_verify":
            if action.tool != "file" or str((action.input or {}).get("operation") or "") != "read":
                return {
                    "passed": False,
                    "reason": "blocked_unexpected_item_action",
                    "verifier": "run_items",
                    "target": active_item.canonical_path,
                    "evidence": {
                        "active_item": active_item.description,
                        "expected_tool": "file.read",
                        "actual_tool": action.tool,
                        "actual_input": dict(action.input or {}),
                    },
                    "warnings": [],
                }
        if actual_path and not path_matches_canonical(active_item.canonical_path, str(actual_path)):
            return {
                "passed": False,
                "reason": "blocked_unexpected_output_path",
                "verifier": "run_items",
                "target": active_item.canonical_path,
                "evidence": {
                    "active_item": active_item.description,
                    "expected_path": active_item.canonical_path,
                    "actual_path": str(actual_path),
                    "tool": action.tool,
                },
                "warnings": [],
            }
        return None

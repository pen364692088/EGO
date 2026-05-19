from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
from typing import Any, Dict, List, Optional
import time

from .contracts import DeliveryLedger
from .chat_state import ChatState
from .delivery_policy import RuntimeV2DeliveryPolicy
from .run_items import (
    RunConflictState,
    RunEvent,
    RunItem,
    VerificationBaseline,
    build_deterministic_file_content,
    build_output_obligations,
    build_run_item_started_text,
    build_run_item_verified_text,
    is_host_deterministic_run_item,
    path_matches_canonical,
    path_changed_from_baseline,
    resolve_expected_lines,
    verify_run_item,
)


# 截断阈值
MAX_CONTENT_IN_HISTORY = 2000  # 字符
MAX_STDOUT_IN_STATE = 2000
MAX_STDERR_IN_STATE = 500
MAX_GOAL_LENGTH = 200  # 目标截断
WINDOWS_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")


def _compact_record_content(content: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(content, dict):
        return {"preview": str(content)[:200]}

    compact: Dict[str, Any] = {}
    for key in ("text", "summary", "type", "tool", "success", "status", "question", "message"):
        value = content.get(key)
        if value in (None, "", [], {}):
            continue
        if isinstance(value, str):
            compact[key] = value[:200]
        else:
            compact[key] = value
    return compact


def _summarize_ingress_context(ingress_context: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not ingress_context:
        return None

    target = ingress_context.get("resolved_target") or {}
    requested_output = ingress_context.get("requested_output") or {}
    summary: Dict[str, Any] = {
        "runtime_action": ingress_context.get("runtime_action"),
        "request_mode": ingress_context.get("request_mode"),
        "interaction_kind": ingress_context.get("interaction_kind"),
        "conversation_act": ingress_context.get("conversation_act"),
        "parser_source": ingress_context.get("parser_source"),
        "primary_intent": ingress_context.get("primary_intent"),
    }
    if target:
        summary["resolved_target"] = {
            "source": target.get("source"),
            "path": target.get("path"),
            "filename": target.get("filename"),
            "artifact_id": target.get("artifact_id") or target.get("artifact_ref"),
        }
    if requested_output:
        summary["requested_output"] = {
            "format": requested_output.get("format"),
            "effective_path": requested_output.get("effective_path"),
        }
    if ingress_context.get("risk_level"):
        summary["risk_level"] = ingress_context.get("risk_level")
    if ingress_context.get("rule_enforcement"):
        summary["rule_enforcement"] = ingress_context.get("rule_enforcement")
    if ingress_context.get("proactive_topic_permission"):
        summary["proactive_topic_permission"] = ingress_context.get("proactive_topic_permission")
    for key in (
        "outreach_aggression_mode",
        "outreach_feedback_adaptation",
        "quiet_state",
        "quiet_until",
        "feedback_signal",
    ):
        value = ingress_context.get(key)
        if value not in (None, "", [], {}):
            summary[key] = value
    if ingress_context.get("resume_hint_eligible") is not None:
        summary["resume_hint_eligible"] = bool(ingress_context.get("resume_hint_eligible"))
    return summary


def _summarize_task_contract(task_contract: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not task_contract:
        return None
    summary: Dict[str, Any] = {}
    for key in ("output_format", "target_path", "task_type", "risk_level", "approval_required", "write_requested"):
        value = task_contract.get(key)
        if value not in (None, "", [], {}):
            summary[key] = value
    return summary or None


def _summarize_autonomy_context(autonomy_context: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not autonomy_context:
        return None
    summary: Dict[str, Any] = {}
    for key in ("run_id", "status", "executor_kind", "current_phase", "resume_count", "hard_blocker_reason", "finish_reason"):
        value = autonomy_context.get(key)
        if value not in (None, "", [], {}):
            summary[key] = value
    return summary or None


def _summarize_run_items(run_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    summary: List[Dict[str, Any]] = []
    for item in run_items[:6]:
        summary.append(
            {
                "item_id": item.get("item_id"),
                "order_index": item.get("order_index"),
                "kind": item.get("kind"),
                "description": item.get("description"),
                "canonical_path": item.get("canonical_path"),
                "status": item.get("status"),
            }
        )
    return summary


def _truncate_tool_result(tool_result: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    将 tool_result 压缩为摘要形式，不包含完整 stdout。

    用于 to_prompt_context()，防止上下文膨胀。
    """
    if not tool_result:
        return None

    return {
        "tool": tool_result.get("tool"),
        "success": tool_result.get("success"),
        "exit_code": tool_result.get("exit_code"),
        "cwd": tool_result.get("cwd"),
        "timed_out": tool_result.get("timed_out"),
        "truncated": tool_result.get("stdout_truncated") or tool_result.get("truncated"),
        # stdout 只保留前 200 字符预览
        "stdout_preview": (tool_result.get("stdout") or "")[:200],
        "stderr_preview": (tool_result.get("stderr") or "")[:100],
        # artifact refs 用于按需回读
        "artifact_refs": tool_result.get("artifact_refs", []),
    }


def _truncate_content_for_history(content: Dict[str, Any]) -> Dict[str, Any]:
    """
    截断 history 中可能的大字段。

    防止文件内容、tool stdout 等大文本被存入 history。
    只保留 capsule 级信息。
    """
    result = dict(content)

    # 截断 text 字段（可能包含文件内容）
    text = result.get("text", "")
    if isinstance(text, str) and len(text) > MAX_CONTENT_IN_HISTORY:
        result["text"] = text[:MAX_CONTENT_IN_HISTORY] + f"\n... [截断，原文 {len(text)} 字符，可用 ref 回读]"
        result["text_truncated"] = True
        result["text_full_length"] = len(text)

    # 截断 stdout
    stdout = result.get("stdout", "")
    if isinstance(stdout, str) and len(stdout) > 200:
        result["stdout"] = stdout[:200] + f"\n... [截断]"
        result["stdout_truncated"] = True

    # 截断 stderr
    stderr = result.get("stderr", "")
    if isinstance(stderr, str) and len(stderr) > 100:
        result["stderr"] = stderr[:100] + f"\n... [截断]"
        result["stderr_truncated"] = True

    # 保留 artifact_refs（用于回读）
    # 不要删除

    return result


def _summarize_tool_result(tool_result: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    将 tool_result 压缩为摘要形式，不包含完整 stdout。

    用于 to_prompt_context()，防止上下文膨胀。
    """
    return _truncate_tool_result(tool_result)


def _summarize_history_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    压缩 history 条目，防止大内容进 prompt。
    """
    role = item.get("role", "")
    content = item.get("content", {})

    if role == "tool" and isinstance(content, dict):
        # tool 记录只保留摘要
        return {
            "role": role,
            "content": _summarize_tool_result(content) or content,
        }

    # 其他记录检查 text 字段
    if isinstance(content, dict):
        truncated = _truncate_content_for_history(content)
        return {"role": role, "content": truncated}

    return item


@dataclass
class RuntimeV2State:
    session_id: str
    task_id: Optional[str] = None
    task_status: str = "idle"

    # WS-1: Turn Isolation
    generation_id: int = 0  # 每次 /new 递增，隔离旧消息
    active_turn_id: Optional[str] = None  # 当前 turn ID
    active_turn_status: str = "idle"  # idle/running/waiting_input/terminal
    final_sent: bool = False  # 是否已发送 final result
    current_goal: Optional[str] = None
    current_step: Optional[str] = None
    waiting_for_user_input: bool = False
    last_user_turn: Optional[str] = None
    last_model_action: Optional[Dict[str, Any]] = None
    last_tool_result: Optional[Dict[str, Any]] = None
    last_tool_result_turn_id: Optional[str] = None
    last_verification_result: Optional[Dict[str, Any]] = None
    last_task_started_at: Optional[float] = None
    last_task_completed_at: Optional[float] = None
    last_busy_notice_at: Optional[float] = None
    last_failure_notice_at: Optional[float] = None
    last_failure_notice_text: Optional[str] = None
    last_challenge_turn: Optional[str] = None
    delivery_ledger: DeliveryLedger = field(default_factory=DeliveryLedger)
    history: List[Dict[str, Any]] = field(default_factory=list)
    # Token usage tracking
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    llm_call_count: int = 0
    compaction_count: int = 0

    # Pending artifacts（挂起的文件集合）
    pending_artifacts: List[Dict[str, Any]] = field(default_factory=list)
    last_uploaded_artifact: Optional[Dict[str, Any]] = None  # 最近上传的文件
    last_explicit_target: Optional[str] = None  # 最近明确指定的目标

    # 意图推断相关（闭环1）
    last_inferred_action: Optional[str] = None  # 猜用户要执行/对比/审查
    last_inferred_target: Optional[str] = None  # 推断的目标文件
    pending_bundle_summary: Optional[Dict[str, Any]] = None  # bundle 里有哪些文件、角色

    # WS-4: Progress Events
    pending_progress_events: List[Any] = field(default_factory=list)  # 待发送的进度事件
    last_delivery_type: Optional[str] = None  # 最近发送的类型：suggestion/progress/blocked/completed/final

    # 步骤计数器（用于动态步骤进度）
    current_step_number: int = 0  # 当前步骤编号
    total_steps_planned: Optional[int] = None  # 计划的总步骤数

    # Proto-Self Kernel Context
    proto_self_context: Optional[Dict[str, Any]] = None  # policy_hint / response_tendency / reflection_note
    ingress_context: Optional[Dict[str, Any]] = None  # canonical ingress structure for single-pass decision
    proto_self_version_override: Optional[str] = None  # session-scoped compatibility override; default mainline is v2
    proto_self_subject_profile_override: Optional[str] = None  # optional session-scoped subject profile overlay
    task_contract: Optional[Dict[str, Any]] = None
    next_step_decision: Optional[Dict[str, Any]] = None
    verification_history: List[Dict[str, Any]] = field(default_factory=list)
    need_relock: bool = False
    contract_phase: str = "pending"
    autonomy_context: Optional[Dict[str, Any]] = None
    output_obligations: List[Dict[str, Any]] = field(default_factory=list)
    run_items: List[Dict[str, Any]] = field(default_factory=list)
    pending_task_conflict: Optional[Dict[str, Any]] = None
    pending_proactive_followup: Optional[Dict[str, Any]] = None
    pending_proactive_outbox_events: List[Dict[str, Any]] = field(default_factory=list)
    active_item_id: Optional[str] = None
    pending_run_events: List[Dict[str, Any]] = field(default_factory=list)
    last_delivered_evidence_context: Optional[Dict[str, Any]] = None
    last_evidence_read_result: Optional[Dict[str, Any]] = None
    recent_delivered_result_context: Optional[Dict[str, Any]] = None
    pending_result_continuation: Optional[Dict[str, Any]] = None
    chat_state: ChatState = field(default_factory=ChatState)

    def to_prompt_context(self) -> Dict[str, Any]:
        """
        生成注入到 LLM prompt 的上下文。

        P1: 不回灌完整 stdout，只回灌摘要。
        """
        # 压缩 history
        compressed_history = [
            _summarize_history_item(item)
            for item in self.history[-12:]
        ]

        return {
            "session_id": self.session_id,
            "task_id": self.task_id,
            "task_status": self.task_status,
            # WS-1: Turn Isolation
            "generation_id": self.generation_id,
            "active_turn_id": self.active_turn_id,
            "active_turn_status": self.active_turn_status,
            "final_sent": self.final_sent,
            "current_goal": self.current_goal,
            "current_step": self.current_step,
            "waiting_for_user_input": self.waiting_for_user_input,
            "last_user_turn": self.last_user_turn,
            # P1: 不回灌完整 last_tool_result
            "last_tool_result_summary": _summarize_tool_result(self.last_tool_result),
            "last_verification_result": self.last_verification_result,
            "last_task_started_at": self.last_task_started_at,
            "last_task_completed_at": self.last_task_completed_at,
            "last_busy_notice_at": self.last_busy_notice_at,
            "last_failure_notice_at": self.last_failure_notice_at,
            "last_failure_notice_text": self.last_failure_notice_text,
            "last_challenge_turn": self.last_challenge_turn,
            "delivery_ledger": self.delivery_ledger.to_dict(),
            # P1: 压缩后的 history
            "history": compressed_history,
            # Pending artifacts（用于指代绑定）
            "pending_artifacts_count": len(self.pending_artifacts),
            "last_uploaded_artifact": self.last_uploaded_artifact,
            "last_explicit_target": self.last_explicit_target,
            # 意图推断（闭环1）
            "last_inferred_action": self.last_inferred_action,
            "last_inferred_target": self.last_inferred_target,
            "pending_bundle_summary": self.pending_bundle_summary,
            # WS-4: Progress Events telemetry
            "pending_progress_events_count": len(self.pending_progress_events),
            "last_delivery_type": self.last_delivery_type,
            # Proto-Self Kernel Context
            "proto_self_context": self.proto_self_context,
            # Canonical ingress structure
            "ingress_context": self.ingress_context,
            "proto_self_version_override": self.proto_self_version_override,
            "proto_self_subject_profile_override": self.proto_self_subject_profile_override,
            "task_contract": self.task_contract,
            "next_step_decision": self.next_step_decision,
            "verification_history": self.verification_history[-3:],
            "need_relock": self.need_relock,
            "contract_phase": self.contract_phase,
            "autonomy_context": self.autonomy_context,
            "output_obligations": self.output_obligations,
            "run_items": _summarize_run_items(self.run_items),
            "pending_task_conflict": self.pending_task_conflict,
            "pending_proactive_followup": self.pending_proactive_followup,
            "pending_proactive_outbox_events_count": len(self.pending_proactive_outbox_events),
            "active_item_id": self.active_item_id,
            "pending_run_events_count": len(self.pending_run_events),
            "recent_delivered_result_context": self.recent_delivered_result_context,
            "pending_result_continuation": self.build_pending_result_continuation_summary(),
            "chat_state": self.get_chat_state().to_dict(),
        }

    def to_decision_prompt_context(self) -> Dict[str, Any]:
        compressed_history = [
            {
                "role": item.get("role"),
                "content": _compact_record_content(item.get("content") or {}),
            }
            for item in self.history[-6:]
        ]

        last_uploaded = self.last_uploaded_artifact or {}
        uploaded_summary = None
        if last_uploaded:
            uploaded_summary = {
                "artifact_id": last_uploaded.get("artifact_id"),
                "filename": last_uploaded.get("filename"),
            }

        return {
            "session_id": self.session_id,
            "task_id": self.task_id,
            "task_status": self.task_status,
            "active_turn_status": self.active_turn_status,
            "current_goal": self.current_goal,
            "current_step": self.current_step,
            "waiting_for_user_input": self.waiting_for_user_input,
            "last_user_turn": self.last_user_turn,
            "last_tool_result_summary": _summarize_tool_result(self.last_tool_result),
            "last_verification_result": self.last_verification_result,
            "last_failure_notice_text": self.last_failure_notice_text,
            "history": compressed_history,
            "pending_artifacts_count": len(self.pending_artifacts),
            "last_uploaded_artifact": uploaded_summary,
            "last_explicit_target": self.last_explicit_target,
            "last_inferred_action": self.last_inferred_action,
            "last_inferred_target": self.last_inferred_target,
            "pending_bundle_summary": self.pending_bundle_summary,
            "last_delivery_type": self.last_delivery_type,
            "ingress_context": _summarize_ingress_context(self.ingress_context),
            "task_contract": _summarize_task_contract(self.task_contract),
            "verification_history": list(self.verification_history[-2:]),
            "need_relock": self.need_relock,
            "contract_phase": self.contract_phase,
            "autonomy_context": _summarize_autonomy_context(self.autonomy_context),
            "output_obligations": list(self.output_obligations),
            "run_items": _summarize_run_items(self.run_items),
            "pending_task_conflict": self.pending_task_conflict,
            "pending_proactive_followup": self.pending_proactive_followup,
            "pending_proactive_outbox_events_count": len(self.pending_proactive_outbox_events),
            "active_item_id": self.active_item_id,
            "pending_run_events_count": len(self.pending_run_events),
            "pending_result_continuation": self.build_pending_result_continuation_summary(),
            "chat_state": {
                "last_user_tone_feedback": self.get_chat_state().last_user_tone_feedback,
                "recent_assistant_replies": list(self.get_chat_state().recent_assistant_replies[-3:]),
            },
        }

    def to_execute_task_prompt_context(self) -> Dict[str, Any]:
        items = self.get_run_items()
        active_item = self.get_active_run_item()
        return {
            "session_id": self.session_id,
            "task_id": self.task_id,
            "task_status": self.task_status,
            "current_goal": self.current_goal,
            "current_step": self.current_step,
            "last_user_turn": self.last_user_turn,
            "last_tool_result_summary": _summarize_tool_result(self.last_tool_result),
            "last_verification_result": self.last_verification_result,
            "ingress_context": _summarize_ingress_context(self.ingress_context),
            "active_item": active_item.to_dict() if active_item else None,
            "verified_items": [
                {
                    "item_id": item.item_id,
                    "description": item.description,
                    "canonical_path": item.canonical_path,
                    "kind": item.kind,
                }
                for item in items
                if item.status == "verified"
            ],
            "pending_items": [
                {
                    "item_id": item.item_id,
                    "description": item.description,
                    "canonical_path": item.canonical_path,
                    "kind": item.kind,
                    "status": item.status,
                }
                for item in items
                if item.status != "verified"
            ],
        }

    def to_chat_prompt_context(self) -> Dict[str, Any]:
        chat_state = self.get_chat_state()
        return {
            "session_id": self.session_id,
            "task_id": self.task_id,
            "interaction_kind": str(((self.ingress_context or {}).get("interaction_kind") or "")).strip(),
            "conversation_act": str(((self.ingress_context or {}).get("conversation_act") or "")).strip(),
            "last_user_turn": self.last_user_turn,
            "recent_user_turns": list(chat_state.recent_user_turns[-4:]),
            "recent_user_turn_records": [dict(item) for item in list(chat_state.recent_user_turn_records or [])[-4:]],
            "recent_assistant_replies": list(chat_state.recent_assistant_replies[-4:]),
            "last_user_tone_feedback": chat_state.last_user_tone_feedback,
            "relationship_context": dict(chat_state.relationship_context or {}),
            "style_profile": dict(chat_state.style_profile or {}),
            "stance_memory": chat_state.stance_snapshot(),
            "active_task_summary": self.build_active_task_summary(),
            "proto_self_context": dict(self.proto_self_context or {}),
            "recent_delivered_result_context": dict(self.recent_delivered_result_context or {}),
            "pending_result_continuation": self.build_pending_result_continuation_summary(),
            "ingress_context": _summarize_ingress_context(self.ingress_context),
        }

    def add_pending_artifact(self, artifact_id: str, filename: Optional[str] = None,
                              artifact_ref: Optional[str] = None) -> None:
        """
        添加挂起文件到 pending_artifacts。

        同时更新 last_uploaded_artifact 和 pending_bundle_summary。
        """
        artifact_info = {
            "artifact_id": artifact_id,
            "filename": filename,
            "artifact_ref": artifact_ref or artifact_id,
            "uploaded_at": time.time(),
        }

        # 添加到 pending 列表
        self.pending_artifacts.append(artifact_info)

        # 更新最近上传
        self.last_uploaded_artifact = artifact_info

        # 更新 bundle summary（闭环1）
        self.pending_bundle_summary = {
            "count": len(self.pending_artifacts),
            "files": [
                {"filename": a.get("filename"), "artifact_id": a.get("artifact_id")}
                for a in self.pending_artifacts
            ],
            "latest": filename,
        }

    def clear_pending_artifacts(self) -> None:
        """清空 pending_artifacts（任务开始后）"""
        self.pending_artifacts = []
        self.last_explicit_target = None

    def get_last_pending_artifact(self) -> Optional[Dict[str, Any]]:
        """获取最近一个挂起文件"""
        if self.pending_artifacts:
            return self.pending_artifacts[-1]
        return None

    def record(self, role: str, content: Dict[str, Any]) -> None:
        """
        记录 history 条目。

        自动截断大字段，防止上下文膨胀。
        """
        truncated = _truncate_content_for_history(content)
        self.history.append({"role": role, "content": truncated})

    def record_token_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        """Record token usage from LLM API call."""
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.llm_call_count += 1

    def get_total_tokens(self) -> int:
        """Get total tokens used (prompt + completion)."""
        return self.total_prompt_tokens + self.total_completion_tokens

    def is_busy(self) -> bool:
        pending_continuation = dict(self.pending_result_continuation or {})
        return (
            self.task_status in {"running", "waiting_input", "resumable_pause", "blocked"}
            or bool(self.current_goal)
            or bool(self.pending_task_conflict)
            or str(pending_continuation.get("status") or "").strip() in {"pending", "running", "blocked"}
        )

    def mark_task_started(self, goal: Optional[str] = None) -> None:
        self.task_status = "running"
        self.waiting_for_user_input = False
        self.last_task_started_at = time.time()
        self.contract_phase = "executing"
        if goal:
            # 截断 goal，防止大内容进入 state
            self.current_goal = goal[:MAX_GOAL_LENGTH] if len(goal) > MAX_GOAL_LENGTH else goal

    def mark_task_completed(self) -> None:
        self.task_status = "completed_verified"
        self.waiting_for_user_input = False
        self.last_task_completed_at = time.time()
        self.active_turn_status = "terminal"
        self.contract_phase = "completed"

    def reset_active_task_context(self) -> None:
        """Drop stale task execution state while preserving uploaded artifacts."""
        self.task_status = "idle"
        self.current_goal = None
        self.current_step = None
        self.waiting_for_user_input = False
        self.last_model_action = None
        self.last_tool_result = None
        self.last_tool_result_turn_id = None
        self.last_verification_result = None
        self.task_contract = None
        self.next_step_decision = None
        self.verification_history = []
        self.need_relock = False
        self.contract_phase = "pending"
        self.current_step_number = 0
        self.total_steps_planned = None
        self.active_turn_status = "idle"
        self.final_sent = False
        self.pending_progress_events = []
        self.autonomy_context = None
        self.output_obligations = []
        self.run_items = []
        self.pending_task_conflict = None
        self.pending_proactive_followup = None
        self.pending_proactive_outbox_events = []
        self.active_item_id = None
        self.pending_run_events = []
        self.last_delivered_evidence_context = None
        self.last_evidence_read_result = None
        self.recent_delivered_result_context = None
        self.pending_result_continuation = None

    def clear_terminal_execution_residue(
        self,
        *,
        preserve_evidence_context: bool = False,
        preserve_recent_result_context: bool = False,
    ) -> None:
        evidence_context = (
            dict(self.last_delivered_evidence_context or {})
            if preserve_evidence_context and isinstance(self.last_delivered_evidence_context, dict)
            else None
        )
        evidence_compat = (
            dict(self.last_evidence_read_result or {})
            if preserve_evidence_context and isinstance(self.last_evidence_read_result, dict)
            else evidence_context
        )
        recent_result_context = (
            dict(self.recent_delivered_result_context or {})
            if preserve_recent_result_context and isinstance(self.recent_delivered_result_context, dict)
            else None
        )
        pending_result_continuation = (
            dict(self.pending_result_continuation or {})
            if preserve_recent_result_context and isinstance(self.pending_result_continuation, dict)
            else None
        )

        self.task_status = "idle"
        self.current_goal = None
        self.current_step = None
        self.waiting_for_user_input = False
        self.last_model_action = None
        self.last_tool_result = None
        self.last_tool_result_turn_id = None
        self.last_verification_result = None
        self.task_contract = None
        self.next_step_decision = None
        self.verification_history = []
        self.need_relock = False
        self.contract_phase = "pending"
        self.current_step_number = 0
        self.total_steps_planned = None
        self.active_turn_status = "idle"
        self.final_sent = False
        self.pending_progress_events = []
        self.autonomy_context = None
        self.pending_proactive_followup = None

        self.last_delivered_evidence_context = evidence_context
        self.last_evidence_read_result = evidence_compat
        self.recent_delivered_result_context = recent_result_context
        self.pending_result_continuation = pending_result_continuation

    def begin_execute_task(
        self,
        objective: str,
        run_items: List[RunItem],
        ingress_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.task_status = "idle"
        self.current_goal = objective[:MAX_GOAL_LENGTH] if len(objective) > MAX_GOAL_LENGTH else objective
        self.current_step = None
        self.waiting_for_user_input = False
        self.last_model_action = None
        self.last_tool_result = None
        self.last_tool_result_turn_id = None
        self.last_verification_result = None
        self.last_task_started_at = None
        self.last_task_completed_at = None
        self.last_busy_notice_at = None
        self.last_failure_notice_at = None
        self.last_failure_notice_text = None
        self.task_contract = None
        self.next_step_decision = None
        self.verification_history = []
        self.need_relock = False
        self.contract_phase = "pending"
        self.current_step_number = 0
        self.total_steps_planned = None
        self.pending_progress_events = []
        self.pending_run_events = []
        self.pending_task_conflict = None
        self.pending_proactive_followup = None
        self.active_item_id = None
        self.active_turn_id = None
        self.active_turn_status = "idle"
        self.final_sent = False
        self.autonomy_context = None
        self.last_delivered_evidence_context = None
        self.last_evidence_read_result = None
        self.recent_delivered_result_context = None
        preserve_continuation = bool(
            isinstance(ingress_context, dict)
            and ingress_context.get("recent_result_binding")
            and isinstance(self.pending_result_continuation, dict)
        )
        if not preserve_continuation:
            self.pending_result_continuation = None
        if ingress_context is not None:
            self.ingress_context = ingress_context
        self.set_run_items(run_items)

    def set_task_contract(self, contract: Optional[Dict[str, Any]]) -> None:
        self.task_contract = contract
        if contract:
            self.contract_phase = "contract_locked"

    def set_next_step_decision(self, step: Optional[Dict[str, Any]]) -> None:
        self.next_step_decision = step
        if step:
            self.current_step = step.get("action_type")
            self.contract_phase = "step_selected"

    def record_verification(self, verification: Optional[Dict[str, Any]]) -> None:
        self.last_verification_result = verification
        if verification:
            self.verification_history.append(verification)
            self.need_relock = bool(verification.get("need_relock"))
            self.contract_phase = "re_lock_needed" if self.need_relock else "verifying"

    # ==================== WS-1: Turn Isolation ====================

    def increment_generation(self) -> int:
        """
        递增 generation_id，隔离旧消息。

        调用场景：/new 或 reset
        返回：新的 generation_id
        """
        self.generation_id += 1
        self.active_turn_id = None
        self.active_turn_status = "idle"
        self.final_sent = False
        self.task_status = "idle"
        self.current_goal = None
        self.current_step = None
        self.waiting_for_user_input = False
        self.last_tool_result = None
        self.last_tool_result_turn_id = None
        self.last_verification_result = None
        self.ingress_context = None
        self.proto_self_context = None
        self.proto_self_version_override = None
        self.proto_self_subject_profile_override = None
        self.task_contract = None
        self.next_step_decision = None
        self.verification_history = []
        self.need_relock = False
        self.contract_phase = "pending"
        self.current_step_number = 0
        self.total_steps_planned = None
        self.pending_progress_events = []
        self.autonomy_context = None
        self.output_obligations = []
        self.run_items = []
        self.pending_task_conflict = None
        self.pending_proactive_followup = None
        self.pending_proactive_outbox_events = []
        self.active_item_id = None
        self.pending_run_events = []
        self.last_delivered_evidence_context = None
        self.last_evidence_read_result = None
        self.recent_delivered_result_context = None
        self.pending_result_continuation = None
        self.chat_state = ChatState(session_id=self.session_id)
        # 保留 pending_artifacts，因为用户可能在 reset 后继续用同一批文件
        return self.generation_id

    def start_turn(self) -> str:
        """
        开始新的 turn，返回 turn_id。
        """
        import uuid
        self.active_turn_id = f"turn_{uuid.uuid4().hex[:8]}"
        self.active_turn_status = "running"
        self.final_sent = False
        return self.active_turn_id

    def mark_turn_terminal(self) -> None:
        """
        标记当前 turn 为终端状态。
        """
        self.active_turn_status = "terminal"

    def is_stale_delivery(self, generation_id: int, turn_id: Optional[str] = None) -> bool:
        """
        检查 delivery 是否过期。

        过期条件：
        1. generation_id 不匹配
        2. turn_id 不匹配且当前 turn 已 terminal
        3. final_sent 后的 busy/progress
        """
        # generation 不匹配 → stale
        if generation_id != self.generation_id:
            return True

        # turn_id 不匹配且当前 turn 已 terminal → stale
        if turn_id and turn_id != self.active_turn_id and self.active_turn_status == "terminal":
            return True

        return False

    def should_drop_progress(self) -> bool:
        """
        检查是否应该 drop busy/progress 消息。

        条件：final_sent 后不应该再发 busy/progress
        """
        return self.final_sent or self.active_turn_status == "terminal"

    def should_absorb_short_probe(self, window_seconds: float = 8.0) -> bool:
        if self.is_busy():
            return True
        if self.last_task_completed_at is None:
            return False
        return (time.time() - self.last_task_completed_at) <= window_seconds

    def should_send_busy_notice(self, dedupe_window_seconds: float = 6.0) -> bool:
        policy = RuntimeV2DeliveryPolicy()
        return policy.should_send_busy_notice(self.delivery_ledger, dedupe_window_seconds)

    def mark_busy_notice_sent(self) -> None:
        policy = RuntimeV2DeliveryPolicy()
        policy.mark_busy_notice_sent(self.delivery_ledger)
        self.last_busy_notice_at = self.delivery_ledger.last_busy_notice_at

    def should_send_failure_notice(self, text: str, dedupe_window_seconds: float = 8.0) -> bool:
        policy = RuntimeV2DeliveryPolicy()
        return policy.should_send_failure_notice(self.delivery_ledger, text, dedupe_window_seconds)

    def mark_failure_notice_sent(self, text: str) -> None:
        policy = RuntimeV2DeliveryPolicy()
        policy.mark_failure_notice_sent(self.delivery_ledger, text)
        self.last_failure_notice_at = self.delivery_ledger.last_failure_notice_at
        self.last_failure_notice_text = self.delivery_ledger.last_failure_notice_text

    # ==================== WS-4: Progress Events ====================

    def push_progress_event(self, event: Any) -> None:
        """
        添加进度事件到队列。

        事件会在 delivery 层被取出并发送。
        """
        self.pending_progress_events.append(event)

    def pop_progress_events(self) -> List[Any]:
        """
        取出并清空进度事件队列。

        返回：待发送的事件列表
        """
        events = self.pending_progress_events.copy()
        self.pending_progress_events = []
        return events

    def has_pending_progress_events(self) -> bool:
        """检查是否有待发送的进度事件"""
        return len(self.pending_progress_events) > 0

    def push_run_event(self, event: RunEvent) -> None:
        self.pending_run_events.append(event.to_dict())

    def pop_run_events(self) -> List[RunEvent]:
        events = [event for event in (RunEvent(**raw) for raw in self.pending_run_events) if event is not None]
        self.pending_run_events = []
        return events

    def has_pending_run_events(self) -> bool:
        return len(self.pending_run_events) > 0

    def set_run_items(self, items: List[RunItem]) -> None:
        self.run_items = [item.to_dict() for item in items]
        self.output_obligations = build_output_obligations(items)
        self.active_item_id = None
        self.pending_run_events = []

    def get_run_items(self) -> List[RunItem]:
        return [item for item in (RunItem.from_dict(raw) for raw in self.run_items) if item is not None]

    def get_active_run_item(self) -> Optional[RunItem]:
        if not self.active_item_id:
            return None
        for item in self.get_run_items():
            if item.item_id == self.active_item_id:
                return item
        return None

    def get_next_pending_run_item(self) -> Optional[RunItem]:
        for item in self.get_run_items():
            if item.status == "pending":
                return item
        return None

    def start_next_pending_run_item(self) -> Optional[RunItem]:
        self.active_item_id = None
        return self.ensure_active_run_item_started()

    def _write_back_run_items(self, items: List[RunItem]) -> None:
        self.run_items = [item.to_dict() for item in items]
        self.output_obligations = build_output_obligations(items)

    def set_pending_task_conflict(self, conflict: Optional[RunConflictState]) -> None:
        self.pending_task_conflict = conflict.to_dict() if conflict else None

    def get_pending_task_conflict(self) -> Optional[RunConflictState]:
        return RunConflictState.from_dict(self.pending_task_conflict)

    def clear_pending_task_conflict(self) -> None:
        self.pending_task_conflict = None

    def set_pending_proactive_followup(self, payload: Optional[Dict[str, Any]]) -> None:
        self.pending_proactive_followup = dict(payload or {}) if payload else None

    def get_pending_proactive_followup(self) -> Optional[Dict[str, Any]]:
        return dict(self.pending_proactive_followup or {}) if self.pending_proactive_followup else None

    def clear_pending_proactive_followup(self) -> None:
        self.pending_proactive_followup = None

    def clear_proactive_outbox_events(self) -> None:
        self.pending_proactive_outbox_events = []

    def push_proactive_outbox_event(self, payload: Dict[str, Any]) -> None:
        self.pending_proactive_outbox_events.append(dict(payload or {}))

    def set_proactive_outbox_events(self, payloads: List[Dict[str, Any]]) -> None:
        self.pending_proactive_outbox_events = [dict(payload or {}) for payload in payloads]

    def pop_proactive_outbox_events(self) -> List[Dict[str, Any]]:
        events = [dict(event) for event in self.pending_proactive_outbox_events]
        self.pending_proactive_outbox_events = []
        return events

    def peek_proactive_outbox_events(self) -> List[Dict[str, Any]]:
        return [dict(event) for event in self.pending_proactive_outbox_events]

    def has_pending_proactive_outbox_events(self) -> bool:
        return len(self.pending_proactive_outbox_events) > 0

    def ensure_active_run_item_started(self) -> Optional[RunItem]:
        items = self.get_run_items()
        active = None
        for item in items:
            if item.item_id == self.active_item_id:
                active = item
                break
        if active is not None and active.status in {"running", "completed", "blocked"}:
            return active
        if active is not None and active.status == "verified":
            self.active_item_id = None
        next_item = next((item for item in items if item.status == "pending"), None)
        if next_item is None:
            self._write_back_run_items(items)
            return None
        next_item.status = "running"
        next_item.started_at = time.time()
        next_item.attempt_count += 1
        next_item.last_progress_at = next_item.started_at
        if next_item.canonical_path:
            next_item.baseline_snapshot = VerificationBaseline.capture(next_item.canonical_path)
        next_item = self._resolve_run_item_for_execution(next_item, items)
        self.active_item_id = next_item.item_id
        self.current_step = next_item.description
        self._write_back_run_items(items)
        self.push_run_event(
            RunEvent(
                event_type="item_started",
                text=build_run_item_started_text(next_item),
                item_id=next_item.item_id,
                item_label=next_item.description,
            )
        )
        return next_item

    def _resolve_run_item_for_execution(self, item: RunItem, items: Optional[List[RunItem]] = None) -> RunItem:
        if not is_host_deterministic_run_item(item):
            return item

        siblings = items or self.get_run_items()
        resolved_values = dict(item.resolved_values or {})
        if item.kind == "file_verify":
            source_item_id = (item.metadata or {}).get("verify_source_item_id")
            if source_item_id:
                source_item = next((candidate for candidate in siblings if candidate.item_id == source_item_id), None)
                if source_item is not None:
                    if source_item.resolved_expected_lines and not item.resolved_expected_lines:
                        item.resolved_expected_lines = [dict(spec) for spec in source_item.resolved_expected_lines]
                    if source_item.resolved_values and not resolved_values:
                        resolved_values = dict(source_item.resolved_values)
        expected_lines = list((item.metadata or {}).get("expected_lines") or [])
        if not item.resolved_expected_lines and expected_lines:
            item.resolved_expected_lines, resolved_values = resolve_expected_lines(
                expected_lines,
                resolved_values=resolved_values,
            )
        item.resolved_values = resolved_values
        return item

    def resume_active_run_item(self) -> Optional[RunItem]:
        item = self.get_active_run_item()
        if item is None or item.status != "blocked":
            return item
        item.status = "running"
        item.attempt_count += 1
        item.last_progress_at = time.time()
        self.update_run_item(item)
        self.current_step = item.description
        return item

    def mark_active_run_item_completed(self, observation_result: Optional[Dict[str, Any]] = None) -> Optional[RunItem]:
        item = self.get_active_run_item()
        if item is None:
            return None
        item.status = "completed"
        item.completed_at = time.time()
        item.last_progress_at = item.completed_at
        item.verification_result = observation_result
        self.update_run_item(item)
        self.current_step = item.description
        return item

    def execute_host_deterministic_item(self) -> Dict[str, Any]:
        item = self.get_active_run_item()
        if item is None or item.status != "running" or not is_host_deterministic_run_item(item):
            return {"executed": False, "changed": False, "blocked": False}

        items = self.get_run_items()
        item = self._resolve_run_item_for_execution(item, items)
        self.update_run_item(item)
        path = Path(item.canonical_path or "")

        try:
            if item.kind == "file_write":
                path.parent.mkdir(parents=True, exist_ok=True)
                content = build_deterministic_file_content(item.resolved_expected_lines)
                path.write_text(content, encoding="utf-8")
                self.set_last_tool_result_payload({
                    "success": True,
                    "tool": "file",
                    "stdout": f"Successfully wrote to {path}",
                    "stderr": "",
                    "exit_code": 0,
                    "metadata": {
                        "path": str(path),
                        "operation": "write",
                        "host_deterministic": True,
                    },
                })
                self.record("tool", self.last_tool_result)
                observation = {
                    "progressed": True,
                    "reason": "host_deterministic_write_executed",
                    "item_id": item.item_id,
                    "canonical_path": item.canonical_path,
                    "actual_path": str(path),
                }
                self.mark_active_run_item_completed(observation)
                return {
                    "executed": True,
                    "changed": True,
                    "blocked": False,
                    "verification_result": observation,
                }

            if item.kind == "file_verify":
                content = path.read_text(encoding="utf-8")
                self.set_last_tool_result_payload({
                    "success": True,
                    "tool": "file",
                    "stdout": content,
                    "stderr": "",
                    "exit_code": 0,
                    "metadata": {
                        "path": str(path),
                        "operation": "read",
                        "host_deterministic": True,
                    },
                })
                self.record("tool", self.last_tool_result)
                observation = {
                    "progressed": True,
                    "reason": "verify_read_observed",
                    "item_id": item.item_id,
                    "canonical_path": item.canonical_path,
                    "actual_path": str(path),
                }
                self.mark_active_run_item_completed(observation)
                return {
                    "executed": True,
                    "changed": True,
                    "blocked": False,
                    "verification_result": observation,
                }
        except FileNotFoundError:
            verification = {
                "passed": False,
                "reason": "run_item_missing",
                "target": item.canonical_path,
                "evidence": {"path": str(path)},
            }
        except Exception as exc:
            verification = {
                "passed": False,
                "reason": "host_deterministic_item_error",
                "target": item.canonical_path,
                "evidence": {"path": str(path), "error": str(exc)},
            }

        self.last_verification_result = verification
        self.mark_active_run_item_blocked(verification)
        return {
            "executed": True,
            "changed": True,
            "blocked": True,
            "verification_result": verification,
        }

    def update_run_item(self, updated_item: RunItem) -> None:
        items = self.get_run_items()
        for index, item in enumerate(items):
            if item.item_id == updated_item.item_id:
                items[index] = updated_item
                break
        self._write_back_run_items(items)

    def mark_active_run_item_verified(self, verification_result: Optional[Dict[str, Any]] = None) -> Optional[RunItem]:
        item = self.get_active_run_item()
        if item is None:
            return None
        item.status = "verified"
        item.completed_at = item.completed_at or time.time()
        item.verified_at = time.time()
        item.verification_result = verification_result
        self.update_run_item(item)
        self.active_item_id = None
        self.current_step = None
        self.push_run_event(
            RunEvent(
                event_type="item_verified",
                text=build_run_item_verified_text(item),
                item_id=item.item_id,
                item_label=item.description,
            )
        )
        return item

    def current_frontier_summary(self) -> Dict[str, Any]:
        summary = self.get_run_item_status_summary()
        active_item = self.get_active_run_item()
        summary["active_item_id"] = active_item.item_id if active_item else None
        summary["active_item_status"] = active_item.status if active_item else None
        summary["active_item_path"] = active_item.canonical_path if active_item else None
        return summary

    def mark_active_run_item_blocked(self, verification_result: Optional[Dict[str, Any]] = None) -> Optional[RunItem]:
        item = self.get_active_run_item()
        if item is None:
            return None
        item.status = "blocked"
        item.last_progress_at = time.time()
        item.verification_result = verification_result
        self.update_run_item(item)
        self.current_step = item.description
        self.push_run_event(
            RunEvent(
                event_type="run_blocked",
                text=f"当前任务卡在 {item.description}。",
                item_id=item.item_id,
                item_label=item.description,
                metadata={"verification_result": verification_result or {}},
            )
        )
        return item

    def capture_active_run_item_progress_marker(self) -> Optional[Dict[str, Any]]:
        item = self.get_active_run_item()
        if item is None:
            return None
        marker: Dict[str, Any] = {
            "item_id": item.item_id,
            "status": item.status,
            "canonical_path": item.canonical_path,
            "attempt_count": item.attempt_count,
            "last_progress_at": item.last_progress_at,
        }
        if item.canonical_path:
            current = VerificationBaseline.capture(item.canonical_path)
            marker["current_observation"] = current.to_dict()
            marker["baseline_snapshot"] = item.baseline_snapshot.to_dict() if item.baseline_snapshot else None
        return marker

    def observe_active_run_item_progress(
        self,
        *,
        tool_result: Optional[Dict[str, Any]] = None,
        tool_name: Optional[str] = None,
        tool_input: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        item = self.get_active_run_item()
        if item is None:
            return None
        if item.status not in {"running", "completed"}:
            return {
                "progressed": False,
                "reason": f"item_status_{item.status}",
                "item_id": item.item_id,
            }
        if not item.canonical_path:
            return {
                "progressed": False,
                "reason": "missing_canonical_path",
                "item_id": item.item_id,
            }
        actual_path = None
        metadata = dict((tool_result or {}).get("metadata") or {})
        if metadata.get("path"):
            actual_path = str(metadata.get("path"))
        elif isinstance(tool_input, dict) and tool_input.get("path"):
            actual_path = str(tool_input.get("path"))
        if item.kind == "file_verify":
            if tool_result is None:
                return {
                    "progressed": False,
                    "reason": "verify_read_pending",
                    "item_id": item.item_id,
                    "canonical_path": item.canonical_path,
                }
            if tool_name != "file" or str((tool_input or {}).get("operation") or "") != "read":
                return {
                    "progressed": False,
                    "reason": "blocked_unexpected_item_action",
                    "item_id": item.item_id,
                    "canonical_path": item.canonical_path,
                    "actual_tool": tool_name,
                }
            if actual_path and not path_matches_canonical(item.canonical_path, actual_path):
                return {
                    "progressed": False,
                    "reason": "blocked_unexpected_output_path",
                    "item_id": item.item_id,
                    "canonical_path": item.canonical_path,
                    "actual_path": actual_path,
                }
            if bool(tool_result.get("success")):
                observation = {
                    "progressed": True,
                    "reason": "verify_read_observed",
                    "item_id": item.item_id,
                    "canonical_path": item.canonical_path,
                    "actual_path": actual_path,
                }
                if item.status == "running":
                    self.mark_active_run_item_completed(observation)
                return observation
            return {
                "progressed": False,
                "reason": "verify_read_failed",
                "item_id": item.item_id,
                "canonical_path": item.canonical_path,
                "actual_path": actual_path,
            }
        path = PureWindowsPath(item.canonical_path) if WINDOWS_PATH_RE.match(item.canonical_path or "") else PurePosixPath(item.canonical_path)
        baseline = item.baseline_snapshot
        current = VerificationBaseline.capture(str(path))
        if actual_path and not path_matches_canonical(item.canonical_path, actual_path):
            return {
                "progressed": False,
                "reason": "blocked_unexpected_output_path",
                "item_id": item.item_id,
                "canonical_path": item.canonical_path,
                "actual_path": actual_path,
                "baseline_snapshot": baseline.to_dict() if baseline else None,
                "current_observation": current.to_dict(),
            }
        changed = path_changed_from_baseline(Path(str(path)), baseline)
        observation = {
            "progressed": changed,
            "reason": "host_delta_observed" if changed else "no_host_delta",
            "item_id": item.item_id,
            "canonical_path": item.canonical_path,
            "baseline_snapshot": baseline.to_dict() if baseline else None,
            "current_observation": current.to_dict(),
        }
        if changed and item.status == "running":
            self.mark_active_run_item_completed(observation)
        return observation

    def advance_run_item_frontier(self) -> Dict[str, Any]:
        """
        Host-owned frontier promotion.

        负责把当前 frontier item 从 running/completed 主动推进到 verified，
        并在通过后启动下一条 pending item。
        """
        changed = False
        verification_result: Optional[Dict[str, Any]] = None
        blocked = False
        started_next = False
        verified_items: List[str] = []

        while True:
            active = self.ensure_active_run_item_started()
            if active is None:
                break

            if active.status == "running":
                host_execution = self.execute_host_deterministic_item()
                if host_execution.get("executed"):
                    changed = changed or bool(host_execution.get("changed"))
                    verification_result = host_execution.get("verification_result") or verification_result
                    if host_execution.get("blocked"):
                        blocked = True
                        break
                    continue
                break

            if active.status == "completed":
                verification = verify_run_item(active)
                verification_result = verification
                self.last_verification_result = verification
                if verification.get("passed"):
                    verified_items.append(active.item_id)
                    self.mark_active_run_item_verified(verification)
                    changed = True
                    started_next = True
                    continue
                self.mark_active_run_item_blocked(verification)
                changed = True
                blocked = True
                break

            if active.status == "verified":
                self.active_item_id = None
                changed = True
                started_next = True
                continue

            if active.status == "blocked":
                verification_result = active.verification_result
                blocked = True
                break

            break

        return {
            "changed": changed,
            "blocked": blocked,
            "started_next": started_next,
            "verified_items": verified_items,
            "active_item_id": self.active_item_id,
            "verification_result": verification_result,
            "frontier_summary": self.current_frontier_summary(),
        }

    def append_run_items(self, items_to_append: List[RunItem]) -> None:
        existing = self.get_run_items()
        next_index = len(existing)
        seen_paths = {
            (item.canonical_path or "").lower()
            for item in existing
            if item.canonical_path
        }
        for item in items_to_append:
            canonical_key = (item.canonical_path or "").lower()
            if canonical_key and canonical_key in seen_paths:
                continue
            item.order_index = next_index
            next_index += 1
            existing.append(item)
            if canonical_key:
                seen_paths.add(canonical_key)
        self._write_back_run_items(existing)

    def get_run_item_status_summary(self) -> Dict[str, Any]:
        items = self.get_run_items()
        completed = [item.description for item in items if item.status == "verified"]
        active = self.get_active_run_item()
        pending = [
            item.description
            for item in items
            if item.status in {"pending", "running"} and item.item_id != self.active_item_id
        ]
        blocked = [item.description for item in items if item.status == "blocked"]
        return {
            "completed": completed,
            "active": active.description if active else None,
            "pending": pending,
            "blocked": blocked,
        }

    def set_last_tool_result_payload(self, payload: Optional[Dict[str, Any]]) -> None:
        self.last_tool_result = dict(payload or {}) if payload else None
        self.last_tool_result_turn_id = self.active_turn_id if payload else None

    def get_chat_state(self) -> ChatState:
        if not isinstance(self.chat_state, ChatState):
            self.chat_state = ChatState.from_dict(self.chat_state, session_id=self.session_id)
        self.chat_state.ensure_defaults(self.session_id)
        return self.chat_state

    def build_active_task_summary(self) -> Optional[Dict[str, Any]]:
        if self.task_status not in {"running", "waiting_input", "resumable_pause", "blocked"}:
            return None
        summary: Dict[str, Any] = {
            "task_status": self.task_status,
            "current_goal": self.current_goal,
            "current_step": self.current_step,
        }
        if hasattr(self, "get_run_item_status_summary"):
            run_summary = self.get_run_item_status_summary()
            if any(run_summary.get(key) for key in ("completed", "active", "pending", "blocked")):
                summary["run_item_summary"] = run_summary
        return summary

    def idle_seconds_since_chat_activity(self, *, now_ts: Optional[float] = None) -> float:
        return self.get_chat_state().idle_seconds(now_ts=now_ts)

    def prepare_chat_turn(self, *, user_text: str, chat_act: str) -> None:
        self.get_chat_state().prepare_turn(
            user_text=user_text,
            chat_act=chat_act,
            active_task_summary=self.build_active_task_summary(),
        )

    def finalize_chat_turn(self, *, assistant_reply: str, chat_act: str) -> None:
        self.get_chat_state().finalize_turn(assistant_reply=assistant_reply, chat_act=chat_act)

    def update_chat_stance_memory(
        self,
        *,
        stance_label: Optional[str],
        stance_text: Optional[str],
        stance_source_turn: Optional[str],
        revision_basis: Optional[str],
    ) -> None:
        self.get_chat_state().update_stance_memory(
            stance_label=stance_label,
            stance_text=stance_text,
            stance_source_turn=stance_source_turn,
            revision_basis=revision_basis,
        )

    def clear_last_delivered_evidence_context(self) -> None:
        self.last_delivered_evidence_context = None
        self.last_evidence_read_result = None

    def set_last_delivered_evidence_context(self, snapshot: Optional[Dict[str, Any]]) -> None:
        payload = dict(snapshot or {}) if snapshot else None
        self.last_delivered_evidence_context = payload
        self.last_evidence_read_result = dict(payload or {}) if payload else None

    def update_last_delivered_evidence_context(
        self,
        *,
        delivery_was_chunked: bool,
        source_assistant_message_id: Optional[int] = None,
    ) -> None:
        if not isinstance(self.last_delivered_evidence_context, dict):
            return
        self.last_delivered_evidence_context["delivery_was_chunked"] = bool(delivery_was_chunked)
        self.last_delivered_evidence_context["delivered_at"] = time.time()
        if source_assistant_message_id is not None:
            self.last_delivered_evidence_context["source_assistant_message_id"] = int(source_assistant_message_id)
        self.last_evidence_read_result = dict(self.last_delivered_evidence_context)

    def set_last_evidence_read_result(self, snapshot: Optional[Dict[str, Any]]) -> None:
        self.set_last_delivered_evidence_context(snapshot)

    def update_last_evidence_read_delivery(self, *, delivery_was_chunked: bool) -> None:
        self.update_last_delivered_evidence_context(delivery_was_chunked=delivery_was_chunked)

    def clear_recent_delivered_result_context(self) -> None:
        self.recent_delivered_result_context = None

    def set_recent_delivered_result_context(self, snapshot: Optional[Dict[str, Any]]) -> None:
        self.recent_delivered_result_context = dict(snapshot or {}) if snapshot else None

    def update_recent_delivered_result_context(
        self,
        *,
        delivery_was_chunked: bool,
        source_assistant_message_id: Optional[int] = None,
    ) -> None:
        if not isinstance(self.recent_delivered_result_context, dict):
            return
        self.recent_delivered_result_context["delivery_was_chunked"] = bool(delivery_was_chunked)
        self.recent_delivered_result_context["delivered_at"] = time.time()
        if source_assistant_message_id is not None:
            self.recent_delivered_result_context["source_assistant_message_id"] = int(source_assistant_message_id)

    def clear_pending_result_continuation(self) -> None:
        self.pending_result_continuation = None

    def set_pending_result_continuation(self, snapshot: Optional[Dict[str, Any]]) -> None:
        self.pending_result_continuation = dict(snapshot or {}) if snapshot else None

    def update_pending_result_continuation(self, **updates: Any) -> None:
        if not isinstance(self.pending_result_continuation, dict):
            self.pending_result_continuation = {}
        for key, value in updates.items():
            if value is None:
                continue
            self.pending_result_continuation[key] = value
        self.pending_result_continuation["updated_at"] = time.time()

    def build_pending_result_continuation_summary(self) -> Optional[Dict[str, Any]]:
        payload = dict(self.pending_result_continuation or {})
        if not payload:
            return None

        summary: Dict[str, Any] = {}
        for key in (
            "target_path",
            "target_name",
            "source_turn_id",
            "requested_mode",
            "status",
            "last_user_request",
            "needs_clarification",
            "clarification_question",
            "correction_context",
            "bound_to_recent_result",
            "updated_at",
        ):
            value = payload.get(key)
            if value not in (None, "", [], {}):
                summary[key] = value
        return summary or None

    def to_snapshot(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "task_id": self.task_id,
            "task_status": self.task_status,
            "generation_id": self.generation_id,
            "active_turn_id": self.active_turn_id,
            "active_turn_status": self.active_turn_status,
            "final_sent": self.final_sent,
            "current_goal": self.current_goal,
            "current_step": self.current_step,
            "waiting_for_user_input": self.waiting_for_user_input,
            "last_user_turn": self.last_user_turn,
            "last_model_action": self.last_model_action,
            "last_tool_result": self.last_tool_result,
            "last_tool_result_turn_id": self.last_tool_result_turn_id,
            "last_verification_result": self.last_verification_result,
            "last_task_started_at": self.last_task_started_at,
            "last_task_completed_at": self.last_task_completed_at,
            "last_busy_notice_at": self.last_busy_notice_at,
            "last_failure_notice_at": self.last_failure_notice_at,
            "last_failure_notice_text": self.last_failure_notice_text,
            "last_challenge_turn": self.last_challenge_turn,
            "delivery_ledger": self.delivery_ledger.to_dict(),
            "history": list(self.history),
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "llm_call_count": self.llm_call_count,
            "compaction_count": self.compaction_count,
            "pending_artifacts": list(self.pending_artifacts),
            "last_uploaded_artifact": self.last_uploaded_artifact,
            "last_explicit_target": self.last_explicit_target,
            "last_inferred_action": self.last_inferred_action,
            "last_inferred_target": self.last_inferred_target,
            "pending_bundle_summary": self.pending_bundle_summary,
            "last_delivery_type": self.last_delivery_type,
            "current_step_number": self.current_step_number,
            "total_steps_planned": self.total_steps_planned,
            "proto_self_context": self.proto_self_context,
            "ingress_context": self.ingress_context,
            "proto_self_version_override": self.proto_self_version_override,
            "proto_self_subject_profile_override": self.proto_self_subject_profile_override,
            "task_contract": self.task_contract,
            "next_step_decision": self.next_step_decision,
            "verification_history": list(self.verification_history),
            "need_relock": self.need_relock,
            "contract_phase": self.contract_phase,
            "autonomy_context": self.autonomy_context,
            "output_obligations": list(self.output_obligations),
            "run_items": list(self.run_items),
            "pending_task_conflict": self.pending_task_conflict,
            "pending_proactive_followup": self.pending_proactive_followup,
            "pending_proactive_outbox_events": list(self.pending_proactive_outbox_events),
            "active_item_id": self.active_item_id,
            "pending_run_events": list(self.pending_run_events),
            "last_delivered_evidence_context": self.last_delivered_evidence_context,
            "last_evidence_read_result": self.last_evidence_read_result,
            "recent_delivered_result_context": self.recent_delivered_result_context,
            "pending_result_continuation": self.pending_result_continuation,
            "chat_state": self.get_chat_state().to_dict(),
        }

    @classmethod
    def from_snapshot(cls, snapshot: Dict[str, Any]) -> "RuntimeV2State":
        state = cls(session_id=str(snapshot.get("session_id") or "unknown"))
        state.task_id = snapshot.get("task_id")
        state.task_status = snapshot.get("task_status") or "idle"
        state.generation_id = int(snapshot.get("generation_id") or 0)
        state.active_turn_id = snapshot.get("active_turn_id")
        state.active_turn_status = snapshot.get("active_turn_status") or "idle"
        state.final_sent = bool(snapshot.get("final_sent"))
        state.current_goal = snapshot.get("current_goal")
        state.current_step = snapshot.get("current_step")
        state.waiting_for_user_input = bool(snapshot.get("waiting_for_user_input"))
        state.last_user_turn = snapshot.get("last_user_turn")
        state.last_model_action = snapshot.get("last_model_action")
        state.last_tool_result = snapshot.get("last_tool_result")
        state.last_tool_result_turn_id = snapshot.get("last_tool_result_turn_id")
        state.last_verification_result = snapshot.get("last_verification_result")
        state.last_task_started_at = snapshot.get("last_task_started_at")
        state.last_task_completed_at = snapshot.get("last_task_completed_at")
        state.last_busy_notice_at = snapshot.get("last_busy_notice_at")
        state.last_failure_notice_at = snapshot.get("last_failure_notice_at")
        state.last_failure_notice_text = snapshot.get("last_failure_notice_text")
        state.last_challenge_turn = snapshot.get("last_challenge_turn")
        ledger_payload = snapshot.get("delivery_ledger") or {}
        state.delivery_ledger.last_busy_notice_at = ledger_payload.get("last_busy_notice_at")
        state.delivery_ledger.last_failure_notice_at = ledger_payload.get("last_failure_notice_at")
        state.delivery_ledger.last_failure_notice_text = ledger_payload.get("last_failure_notice_text")
        state.delivery_ledger.sent_keys = dict(ledger_payload.get("sent_keys") or {})
        state.history = list(snapshot.get("history") or [])
        state.total_prompt_tokens = int(snapshot.get("total_prompt_tokens") or 0)
        state.total_completion_tokens = int(snapshot.get("total_completion_tokens") or 0)
        state.llm_call_count = int(snapshot.get("llm_call_count") or 0)
        state.compaction_count = int(snapshot.get("compaction_count") or 0)
        state.pending_artifacts = list(snapshot.get("pending_artifacts") or [])
        state.last_uploaded_artifact = snapshot.get("last_uploaded_artifact")
        state.last_explicit_target = snapshot.get("last_explicit_target")
        state.last_inferred_action = snapshot.get("last_inferred_action")
        state.last_inferred_target = snapshot.get("last_inferred_target")
        state.pending_bundle_summary = snapshot.get("pending_bundle_summary")
        state.last_delivery_type = snapshot.get("last_delivery_type")
        state.current_step_number = int(snapshot.get("current_step_number") or 0)
        state.total_steps_planned = snapshot.get("total_steps_planned")
        state.proto_self_context = snapshot.get("proto_self_context")
        state.ingress_context = snapshot.get("ingress_context")
        state.proto_self_version_override = snapshot.get("proto_self_version_override")
        state.proto_self_subject_profile_override = snapshot.get("proto_self_subject_profile_override")
        state.task_contract = snapshot.get("task_contract")
        state.next_step_decision = snapshot.get("next_step_decision")
        state.verification_history = list(snapshot.get("verification_history") or [])
        state.need_relock = bool(snapshot.get("need_relock"))
        state.contract_phase = snapshot.get("contract_phase") or "pending"
        state.autonomy_context = snapshot.get("autonomy_context")
        state.output_obligations = list(snapshot.get("output_obligations") or [])
        state.run_items = list(snapshot.get("run_items") or [])
        state.pending_task_conflict = snapshot.get("pending_task_conflict")
        state.pending_proactive_followup = snapshot.get("pending_proactive_followup")
        state.pending_proactive_outbox_events = list(snapshot.get("pending_proactive_outbox_events") or [])
        state.active_item_id = snapshot.get("active_item_id")
        state.pending_run_events = list(snapshot.get("pending_run_events") or [])
        state.last_delivered_evidence_context = (
            snapshot.get("last_delivered_evidence_context")
            or snapshot.get("last_evidence_read_result")
        )
        state.last_evidence_read_result = state.last_delivered_evidence_context
        state.recent_delivered_result_context = snapshot.get("recent_delivered_result_context")
        state.pending_result_continuation = snapshot.get("pending_result_continuation")
        state.chat_state = ChatState.from_dict(snapshot.get("chat_state"), session_id=state.session_id)
        return state

    # ==================== WS-2: Target Binding ====================

    # 文件类型推断模式
    FILE_TYPE_PATTERNS = {
        "task": ["任务单", "todo", "task", "plan", "fix", "patch", "执行", ".txt"],
        "spec": ["SOUL", "AGENTS", "TOOLS", "BOOTSTRAP", "README", "POLICY", "规范", ".md"],
        "log": ["log", "trace", "error", "report", "日志", ".log"],
    }

    def _classify_artifact_type(self, filename: Optional[str]) -> str:
        """
        推断文件类型：task/spec/log/unknown

        只用文件名，不触发 raw read。
        """
        if not filename:
            return "unknown"
        filename_lower = filename.lower()
        for file_type, patterns in self.FILE_TYPE_PATTERNS.items():
            if any(p.lower() in filename_lower for p in patterns):
                return file_type
        return "unknown"

    def get_task_artifacts(self) -> List[Dict[str, Any]]:
        """
        获取所有 task 类型的 artifact。

        用于"执行"动作的优先绑定。
        """
        return [
            a for a in self.pending_artifacts
            if self._classify_artifact_type(a.get("filename")) == "task"
        ]

    def get_spec_artifacts(self) -> List[Dict[str, Any]]:
        """
        获取所有 spec 类型的 artifact。

        用于"对比"动作。
        """
        return [
            a for a in self.pending_artifacts
            if self._classify_artifact_type(a.get("filename")) == "spec"
        ]

    def resolve_target(self, action: str) -> Optional[Dict[str, Any]]:
        """
        按动作类型分流绑定目标。

        WS-2 核心方法：解决"执行/对比/分析"绑错目标的问题。

        参数:
            action: "execute" / "compare" / "analyze"

        返回:
            绑定的 artifact 信息，或 None

        绑定优先级:
            execute:
                1. last_explicit_target
                2. 最新 task 类 artifact
                3. pending_bundle 中的 task 主文件
                4. last_uploaded_artifact
                5. current_goal

            compare:
                1. last_explicit_target
                2. pending_bundle (多个文件)
                3. 最近两个/多个可比文件
                4. last_uploaded_artifact

            analyze:
                1. last_explicit_target
                2. last_uploaded_artifact
                3. pending_bundle
        """
        # 1. last_explicit_target 最高优先级（所有动作通用）
        if self.last_explicit_target:
            if WINDOWS_PATH_RE.match(self.last_explicit_target):
                return {
                    "path": self.last_explicit_target,
                    "filename": PureWindowsPath(self.last_explicit_target).name or self.last_explicit_target,
                    "source": "explicit_path",
                }
            if self.last_explicit_target.startswith(("/", "/mnt/", "/home/", "/tmp/", "/Users/")):
                return {
                    "path": self.last_explicit_target,
                    "filename": PurePosixPath(self.last_explicit_target).name or self.last_explicit_target,
                    "source": "explicit_path",
                }
            return {
                "artifact_id": self.last_explicit_target,
                "filename": self.last_explicit_target,
                "source": "explicit_target",
            }

        if action == "execute":
            return self._resolve_target_for_execute()
        elif action == "compare":
            return self._resolve_target_for_compare()
        elif action in {"analyze", "write"}:
            return self._resolve_target_for_analyze()

        # 默认：返回 last_uploaded_artifact
        return self.last_uploaded_artifact

    def _resolve_target_for_execute(self) -> Optional[Dict[str, Any]]:
        """
        执行动作的目标绑定。

        优先级：
        1. 最新 task 类 artifact
        2. last_uploaded_artifact（如果类型是 task）
        3. last_uploaded_artifact（任意类型）
        4. current_goal
        """
        # 1. 最新 task 类 artifact
        task_artifacts = self.get_task_artifacts()
        if task_artifacts:
            return {**task_artifacts[-1], "source": "latest_task_artifact"}

        # 2. last_uploaded_artifact（如果类型是 task）
        if self.last_uploaded_artifact:
            filename = self.last_uploaded_artifact.get("filename")
            if self._classify_artifact_type(filename) == "task":
                return {**self.last_uploaded_artifact, "source": "last_uploaded_task"}

        # 3. last_uploaded_artifact（任意类型，但排除规范文件）
        if self.last_uploaded_artifact:
            filename = self.last_uploaded_artifact.get("filename")
            # 硬规则：不得回退到 SOUL/AGENTS/TOOLS
            if self._classify_artifact_type(filename) != "spec":
                return {**self.last_uploaded_artifact, "source": "last_uploaded"}

        # 4. current_goal
        if self.current_goal:
            return {
                "artifact_id": None,
                "filename": None,
                "goal": self.current_goal,
                "source": "current_goal",
            }

        return None

    def _resolve_target_for_compare(self) -> Optional[Dict[str, Any]]:
        """
        对比动作的目标绑定。

        优先级：
        1. pending_bundle（多个文件）
        2. 最近两个/多个可比文件
        3. last_uploaded_artifact
        """
        # 1. pending_bundle（多个文件）
        if len(self.pending_artifacts) >= 2:
            return {
                "bundle": self.pending_artifacts,
                "count": len(self.pending_artifacts),
                "source": "pending_bundle",
            }

        # 2. 最近两个 spec 类文件
        spec_artifacts = self.get_spec_artifacts()
        if len(spec_artifacts) >= 2:
            return {
                "bundle": spec_artifacts,
                "count": len(spec_artifacts),
                "source": "spec_bundle",
            }

        # 3. last_uploaded_artifact
        if self.last_uploaded_artifact:
            return {**self.last_uploaded_artifact, "source": "last_uploaded"}

        return None

    def _resolve_target_for_analyze(self) -> Optional[Dict[str, Any]]:
        """
        分析动作的目标绑定。

        优先级：
        1. active pending continuation
        2. 最近刚交付的结果
        3. last_uploaded_artifact
        4. pending_bundle
        """
        pending_continuation = dict(self.pending_result_continuation or {})
        continuation_path = str(pending_continuation.get("target_path") or "").strip()
        if continuation_path:
            if WINDOWS_PATH_RE.match(continuation_path):
                return {
                    "path": continuation_path,
                    "filename": PureWindowsPath(continuation_path).name or continuation_path,
                    "source": "pending_result_continuation",
                }
            if continuation_path.startswith(("/", "/mnt/", "/home/", "/tmp/", "/Users/")):
                return {
                    "path": continuation_path,
                    "filename": PurePosixPath(continuation_path).name or continuation_path,
                    "source": "pending_result_continuation",
                }

        recent_result = dict(self.recent_delivered_result_context or {})
        recent_path = str(recent_result.get("target_path") or "").strip()
        if recent_path:
            if WINDOWS_PATH_RE.match(recent_path):
                return {
                    "path": recent_path,
                    "filename": PureWindowsPath(recent_path).name or recent_path,
                    "source": "recent_delivered_result",
                }
            if recent_path.startswith(("/", "/mnt/", "/home/", "/tmp/", "/Users/")):
                return {
                    "path": recent_path,
                    "filename": PurePosixPath(recent_path).name or recent_path,
                    "source": "recent_delivered_result",
                }

        # 2. last_uploaded_artifact
        if self.last_uploaded_artifact:
            return {**self.last_uploaded_artifact, "source": "last_uploaded"}

        # 3. pending_bundle
        if self.pending_artifacts:
            return {
                "bundle": self.pending_artifacts,
                "count": len(self.pending_artifacts),
                "source": "pending_bundle",
            }

        return None

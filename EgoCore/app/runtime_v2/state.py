from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath, PureWindowsPath
import re
from typing import Any, Dict, List, Optional
import time

from .contracts import DeliveryLedger
from .delivery_policy import RuntimeV2DeliveryPolicy


# 截断阈值
MAX_CONTENT_IN_HISTORY = 2000  # 字符
MAX_STDOUT_IN_STATE = 2000
MAX_STDERR_IN_STATE = 500
MAX_GOAL_LENGTH = 200  # 目标截断
WINDOWS_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")


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
    task_contract: Optional[Dict[str, Any]] = None
    next_step_decision: Optional[Dict[str, Any]] = None
    verification_history: List[Dict[str, Any]] = field(default_factory=list)
    need_relock: bool = False
    contract_phase: str = "pending"

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
            "task_contract": self.task_contract,
            "next_step_decision": self.next_step_decision,
            "verification_history": self.verification_history[-3:],
            "need_relock": self.need_relock,
            "contract_phase": self.contract_phase,
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
        return self.task_status in {"running", "waiting_input"} or bool(self.current_goal)

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
        self.final_sent = True
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
        self.proto_self_version_override = None
        self.task_contract = None
        self.next_step_decision = None
        self.verification_history = []
        self.need_relock = False
        self.contract_phase = "pending"
        self.current_step_number = 0
        self.total_steps_planned = None
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
        elif action == "analyze":
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
        1. last_uploaded_artifact
        2. pending_bundle
        """
        # 1. last_uploaded_artifact
        if self.last_uploaded_artifact:
            return {**self.last_uploaded_artifact, "source": "last_uploaded"}

        # 2. pending_bundle
        if self.pending_artifacts:
            return {
                "bundle": self.pending_artifacts,
                "count": len(self.pending_artifacts),
                "source": "pending_bundle",
            }

        return None

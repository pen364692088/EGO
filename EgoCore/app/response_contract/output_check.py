from __future__ import annotations

from dataclasses import dataclass
import re
import time
from typing import Any, Dict, List, Optional

from app.runtime_v2.run_items import build_run_item_summary_text

from .response_plan import ResponsePlan


@dataclass(frozen=True)
class OutputCheckVerdict:
    passed: bool
    reason: str
    reply_text: str
    delivery_kind: str
    authority_source: str = "response_contract.output_check"
    used_host_fallback: bool = False
    is_evidence_bearing: bool = False
    used_host_verbatim: bool = False
    fidelity_mode: str = "summary"
    fidelity_gap: bool = False
    evidence_snapshot: Optional[Dict[str, Any]] = None


_TERMINAL_KINDS = {"completed_verified", "completed", "blocked", "failed", "status_probe"}
_SHELL_DIRECTORY_TOKENS = {"dir", "ls", "get-childitem", "gci"}
_SHELL_READ_TOKENS = {"type", "cat", "get-content", "gc", "more"}
_SHELL_SCAN_TOKENS = {"rg", "grep", "findstr", "find", "fd", "where"}


def apply_output_check(plan: ResponsePlan, state: Any) -> OutputCheckVerdict:
    reply_text = str(plan.reply_text or "").strip()
    delivery_kind = _normalize_delivery_kind(plan)
    used_host_fallback = False
    is_evidence_bearing = False
    used_host_verbatim = False
    fidelity_mode = "summary"
    fidelity_gap = False
    evidence_snapshot: Optional[Dict[str, Any]] = None

    evidence_snapshot = _build_evidence_snapshot(state)
    if evidence_snapshot is not None:
        is_evidence_bearing = True
        verbatim_reply = _render_evidence_reply_text(evidence_snapshot)
        if verbatim_reply:
            reply_text = verbatim_reply
            used_host_verbatim = True
            fidelity_mode = "verbatim"
            fidelity_gap = False
        else:
            fidelity_mode = "fallback"
            fidelity_gap = True

    if not reply_text:
        fallback = _build_fallback_reply(plan.kind, state)
        if fallback:
            reply_text = fallback
            used_host_fallback = True
            if not is_evidence_bearing:
                fidelity_mode = "fallback"

    passed = bool(reply_text)
    reason = "ok"
    if used_host_verbatim:
        reason = "host_verbatim_applied"
    elif used_host_fallback:
        reason = "host_fallback_applied"
    elif not passed:
        reason = "missing_reply_text"
    elif fidelity_gap:
        reason = "fidelity_gap"

    return OutputCheckVerdict(
        passed=passed,
        reason=reason,
        reply_text=reply_text,
        delivery_kind=delivery_kind,
        used_host_fallback=used_host_fallback,
        is_evidence_bearing=is_evidence_bearing,
        used_host_verbatim=used_host_verbatim,
        fidelity_mode=fidelity_mode,
        fidelity_gap=fidelity_gap,
        evidence_snapshot=evidence_snapshot,
    )


def _normalize_delivery_kind(plan: ResponsePlan) -> str:
    if plan.kind in {"waiting_input", "ask"}:
        return "ask"
    if plan.kind in _TERMINAL_KINDS:
        return "final"
    return plan.delivery_kind or "chat"


def _build_fallback_reply(kind: str, state: Any) -> str:
    if kind in {"completed_verified", "completed"}:
        return _build_completion_summary(state)
    if kind in {"blocked", "failed"}:
        return _build_blocked_summary(state)
    if kind in {"waiting_input", "ask"}:
        current_step = str(getattr(state, "current_step", "") or "").strip()
        if current_step:
            return f"当前需要你确认后继续。当前步骤：{current_step}"
        return "当前需要你确认后继续。"
    return ""


def _build_completion_summary(state: Any) -> str:
    if hasattr(state, "get_run_items"):
        run_items = list(state.get_run_items() or [])
        verified_items = [item for item in run_items if getattr(item, "status", None) == "verified"]
        if verified_items:
            lines = ["已完成这些任务："]
            for index, item in enumerate(verified_items, start=1):
                lines.append(f"{index}. {build_run_item_summary_text(item)}")
            return "\n".join(lines)
    current_goal = str(getattr(state, "current_goal", "") or "").strip()
    if current_goal:
        return f"已完成：{current_goal}"
    return "已完成。"


def _build_blocked_summary(state: Any) -> str:
    if hasattr(state, "get_run_item_status_summary"):
        summary: Dict[str, Any] = state.get_run_item_status_summary()
        completed: List[str] = list(summary.get("completed") or [])
        active = summary.get("active")
        pending: List[str] = list(summary.get("pending") or [])
        lines = ["当前任务无法继续推进。"]
        if completed:
            lines.append(f"已完成：{', '.join(completed)}。")
        if active:
            lines.append(f"当前卡住：{active}。")
        if pending:
            lines.append(f"还未开始：{', '.join(pending)}。")
        return "\n".join(lines)
    current_step = str(getattr(state, "current_step", "") or "").strip()
    if current_step:
        return f"当前任务无法继续推进。当前卡住：{current_step}。"
    return "当前任务无法继续推进。"


def _build_evidence_snapshot(state: Any) -> Optional[Dict[str, Any]]:
    payload = dict(getattr(state, "last_tool_result", None) or {})
    if not payload or not bool(payload.get("success")):
        return None

    tool_name = str(payload.get("tool") or payload.get("tool_name") or "").strip().lower()
    metadata = dict(payload.get("metadata") or {})
    body = str(payload.get("stdout") or payload.get("output") or "").strip()
    if not tool_name or not body or body == "Command completed successfully":
        return None

    request_kind: Optional[str] = None
    target_path: Optional[str] = None

    if tool_name == "file":
        operation = str(metadata.get("operation") or "").strip().lower()
        if operation == "read":
            request_kind = "file_read"
        elif operation == "list":
            request_kind = "directory_listing"
        if request_kind:
            target_path = str(metadata.get("path") or "").strip() or None
    elif tool_name == "shell":
        command = str(metadata.get("command") or "").strip().lower()
        request_kind = _classify_shell_request_kind(command)
        if request_kind:
            target_path = str(metadata.get("path") or metadata.get("working_directory") or "").strip() or None

    if request_kind is None:
        return None

    return {
        "authority_source": "response_contract.output_check",
        "tool_name": tool_name,
        "request_kind": request_kind,
        "target_path": target_path,
        "body": body,
        "truncated": bool(metadata.get("truncated") or payload.get("truncated")),
        "delivery_was_chunked": False,
        "observed_at": time.time(),
    }


def _classify_shell_request_kind(command: str) -> Optional[str]:
    if not command:
        return None
    tokens = set(re.findall(r"[a-z0-9_.-]+", command))
    if tokens & _SHELL_DIRECTORY_TOKENS:
        return "directory_listing"
    if tokens & _SHELL_READ_TOKENS:
        return "file_read"
    if tokens & _SHELL_SCAN_TOKENS:
        return "scan_results"
    return None


def _render_evidence_reply_text(snapshot: Dict[str, Any]) -> str:
    body = str(snapshot.get("body") or "").strip()
    if not body:
        return ""
    request_kind = str(snapshot.get("request_kind") or "")
    if request_kind == "directory_listing":
        return f"目录内容如下：\n{body}"
    return body

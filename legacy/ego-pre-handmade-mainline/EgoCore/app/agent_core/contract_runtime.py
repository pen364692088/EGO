from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from typing import Any, Dict, List, Optional

from app.tools import execute_tool
from app.compaction import ReadRequest, get_compaction_manager
from app.ingestion.artifact_store import get_artifact_store


WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:[\\/](?:[A-Za-z0-9._() \-]+[\\/])*[A-Za-z0-9._() \-]+")


def _looks_like_html_request(text: str) -> bool:
    lowered = (text or "").lower()
    return any(token in text or token in lowered for token in ("html", "网页", "页面", "webpage", "website"))


def _extract_first_path(text: str) -> Optional[str]:
    if not text:
        return None
    match = WINDOWS_PATH_RE.search(text)
    if match:
        return match.group(0)
    return None


def _normalize_windows_path(path: str) -> str:
    if not path:
        return path
    if WINDOWS_PATH_RE.match(path):
        return str(PureWindowsPath(path))
    return str(Path(path))


def _join_path(base_path: str, filename: str) -> str:
    if WINDOWS_PATH_RE.match(base_path or ""):
        return str(PureWindowsPath(base_path) / filename)
    return str(Path(base_path) / filename)


def _suggest_filename(goal: str, fmt: str) -> str:
    lowered = (goal or "").lower()
    if "egocore" in lowered:
        stem = "egocore_intro"
    else:
        stem = "task_output"
    ext = ".html" if fmt == "html" else ".md"
    return f"{stem}{ext}"


class PlanningTimeoutError(RuntimeError):
    pass


def _extract_hard_constraints(text: str) -> List[str]:
    constraints: List[str] = []
    for raw_line in (text or "").splitlines():
        line = raw_line.strip(" -*\t")
        if not line:
            continue
        lowered = line.lower()
        if any(token in line for token in ("必须", "不得", "禁止", "只", "不能")) or any(
            token in lowered for token in ("must", "must not", "forbid", "cannot", "only")
        ):
            constraints.append(line[:200])
        if len(constraints) >= 6:
            break
    return constraints


def _infer_goal(user_input: str, ingress_context: Dict[str, Any]) -> str:
    requested_output = ingress_context.get("requested_output") or {}
    target = requested_output.get("effective_path") or requested_output.get("target_path")
    topic = requested_output.get("topic")
    if target and topic:
        return f"Create {requested_output.get('format') or 'file'} at {target} about {topic}"
    if target:
        return f"Create or update output at {target}"
    artifact_text = ingress_context.get("resolved_artifact_text") or ""
    for line in artifact_text.splitlines():
        stripped = line.strip(" -*\t")
        if stripped:
            return stripped[:240]
    return (user_input or "complete the user request").strip()[:240]


@dataclass
class TaskContract:
    task_id: str
    goal: str
    success_criteria: List[str]
    hard_constraints: List[str]
    risk_level: str
    key_unknown: Optional[str]
    ask_needed: bool
    ask_reason: Optional[str]
    target_path: Optional[str] = None
    output_format: Optional[str] = None
    source_artifact_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "success_criteria": self.success_criteria,
            "hard_constraints": self.hard_constraints,
            "risk_level": self.risk_level,
            "key_unknown": self.key_unknown,
            "ask_needed": self.ask_needed,
            "ask_reason": self.ask_reason,
            "target_path": self.target_path,
            "output_format": self.output_format,
            "source_artifact_id": self.source_artifact_id,
        }


@dataclass
class NextStepDecision:
    step_id: str
    action_type: str
    rationale: str
    expected_signal: str
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "action_type": self.action_type,
            "rationale": self.rationale,
            "expected_signal": self.expected_signal,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
        }


@dataclass
class VerificationResult:
    step_id: str
    observed_result: Dict[str, Any]
    expected_signal_matched: bool
    contract_delta: Dict[str, Any]
    need_relock: bool
    stop_reason: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "observed_result": self.observed_result,
            "expected_signal_matched": self.expected_signal_matched,
            "contract_delta": self.contract_delta,
            "need_relock": self.need_relock,
            "stop_reason": self.stop_reason,
        }


class ContractRuntimeEngine:
    def lock_contract(
        self,
        *,
        session_key: str,
        user_input: str,
        ingress_context: Optional[Dict[str, Any]] = None,
        proto_self_context: Optional[Dict[str, Any]] = None,
    ) -> TaskContract:
        ingress_context = ingress_context or {}
        requested_output = ingress_context.get("requested_output") or {}
        target = ingress_context.get("resolved_target") or {}
        artifact_text = ingress_context.get("resolved_artifact_text") or ""
        target_path = (
            requested_output.get("effective_path")
            or requested_output.get("target_path")
            or target.get("path")
            or _extract_first_path(user_input)
            or _extract_first_path(artifact_text)
        )
        target_path = _normalize_windows_path(target_path) if target_path else None
        output_format = requested_output.get("format") or ("html" if _looks_like_html_request(user_input + "\n" + artifact_text) else None)
        if target_path and output_format and not Path(target_path).suffix and not WINDOWS_PATH_RE.match(target_path):
            target_path = _join_path(target_path, _suggest_filename(user_input, output_format))
        if target_path and output_format and WINDOWS_PATH_RE.match(target_path) and PureWindowsPath(target_path).suffix == "":
            target_path = _join_path(target_path, _suggest_filename(user_input, output_format))

        goal = _infer_goal(user_input, ingress_context)
        success_criteria: List[str] = []
        if target_path:
            success_criteria.append(f"Target path exists: {target_path}")
        if output_format == "html":
            success_criteria.append("Written file contains HTML structure")
        if requested_output.get("topic"):
            success_criteria.append(f"Content addresses topic: {requested_output.get('topic')}")
        if not success_criteria:
            success_criteria.append("Return a concrete result that advances the user goal")

        hard_constraints = _extract_hard_constraints(artifact_text)
        if target_path:
            hard_constraints.append(f"Write inside allowed path: {target_path}")
        if output_format:
            hard_constraints.append(f"Output format must be {output_format}")
        if proto_self_context and proto_self_context.get("policy_hint"):
            hard_constraints.append(f"Honor policy_hint: {proto_self_context.get('policy_hint')}")

        ask_reason = None
        ask_needed = False
        has_artifact_envelope = bool(target.get("artifact_id") or target.get("artifact_ref"))
        if not target_path and ingress_context.get("runtime_action") == "execute_task" and not has_artifact_envelope:
            ask_needed = True
            ask_reason = "缺少明确输出目标路径或任务产物位置。"
        elif output_format == "html" and not target_path:
            ask_needed = True
            ask_reason = "需要明确 html 页面输出路径。"

        key_unknown = ask_reason
        risk_level = "low"
        if proto_self_context and proto_self_context.get("policy_hint"):
            risk_level = "medium"
        if ingress_context.get("runtime_action") == "execute_task" and not ask_needed:
            risk_level = "medium"

        return TaskContract(
            task_id=f"contract_{uuid.uuid4().hex[:10]}",
            goal=goal,
            success_criteria=success_criteria,
            hard_constraints=hard_constraints[:8],
            risk_level=risk_level,
            key_unknown=key_unknown,
            ask_needed=ask_needed,
            ask_reason=ask_reason,
            target_path=target_path,
            output_format=output_format,
            source_artifact_id=target.get("artifact_id") or target.get("artifact_ref"),
        )

    def decide_next_step(
        self,
        *,
        contract: TaskContract,
        ingress_context: Optional[Dict[str, Any]] = None,
    ) -> NextStepDecision:
        ingress_context = ingress_context or {}
        if contract.source_artifact_id and not ingress_context.get("resolved_artifact_text"):
            return NextStepDecision(
                step_id=f"step_{uuid.uuid4().hex[:8]}",
                action_type="read_artifact",
                rationale="Only artifact envelope is available; perform explicit artifact read as the single step.",
                expected_signal="Artifact content becomes available for re-lock.",
                tool_name="read_artifact",
                tool_input={"artifact_id": contract.source_artifact_id},
            )
        if contract.ask_needed:
            return NextStepDecision(
                step_id=f"step_{uuid.uuid4().hex[:8]}",
                action_type="ask_user",
                rationale="Contract lock indicates missing critical target information.",
                expected_signal="User clarifies missing target or constraints",
            )

        runtime_action = ingress_context.get("runtime_action")
        if runtime_action == "execute_task" and contract.target_path:
            return NextStepDecision(
                step_id=f"step_{uuid.uuid4().hex[:8]}",
                action_type="call_tool",
                rationale="Single-step execution should create or modify the explicit target artifact.",
                expected_signal="A single tool action writes the target file and produces a user-facing result.",
                tool_name="file",
                tool_input={"operation": "write", "path": contract.target_path},
            )

        return NextStepDecision(
            step_id=f"step_{uuid.uuid4().hex[:8]}",
            action_type="reply",
            rationale="No executable target is locked; respond directly.",
            expected_signal="User receives a direct answer.",
        )

    def verify_step(
        self,
        *,
        contract: TaskContract,
        step: NextStepDecision,
        tool_result: Optional[Dict[str, Any]] = None,
        reply_text: str = "",
    ) -> VerificationResult:
        observed: Dict[str, Any] = {"reply_text": reply_text[:400] if reply_text else ""}
        matched = False
        need_relock = False
        stop_reason = None
        contract_delta: Dict[str, Any] = {}

        if step.action_type == "ask_user":
            matched = bool(reply_text)
            stop_reason = "waiting_user"
        elif step.action_type == "reply":
            matched = bool(reply_text)
            stop_reason = "replied"
        elif step.action_type == "call_tool":
            observed["tool_result"] = tool_result or {}
            tool_success = bool(tool_result and tool_result.get("success"))
            matched = tool_success
            if contract.target_path:
                path = Path(contract.target_path)
                exists = path.exists()
                observed["target_exists"] = exists
                matched = matched and exists
                if exists and contract.output_format == "html":
                    try:
                        content = path.read_text(encoding="utf-8")
                    except Exception as exc:
                        content = ""
                        observed["read_error"] = str(exc)
                    has_html = "<html" in content.lower() or "<!doctype html" in content.lower()
                    observed["has_html_signal"] = has_html
                    matched = matched and has_html
            if not matched:
                need_relock = True
                contract_delta["reason"] = tool_result.get("error") if tool_result else "step_not_verified"
                stop_reason = "verification_failed"
            else:
                stop_reason = "verified"
        elif step.action_type == "read_artifact":
            observed["tool_result"] = tool_result or {}
            matched = bool(tool_result and tool_result.get("success"))
            need_relock = matched
            stop_reason = "artifact_ready" if matched else "artifact_read_failed"
            if matched:
                contract_delta["resolved_artifact_text"] = True
            else:
                contract_delta["stage_error_code"] = (tool_result or {}).get("metadata", {}).get("stage_error_code")
                contract_delta["reason"] = (tool_result or {}).get("error")
        else:
            stop_reason = "unsupported_step"
            need_relock = True

        return VerificationResult(
            step_id=step.step_id,
            observed_result=observed,
            expected_signal_matched=matched,
            contract_delta=contract_delta,
            need_relock=need_relock,
            stop_reason=stop_reason,
        )

    def build_ask_reply(self, contract: TaskContract) -> str:
        return contract.ask_reason or "我还缺少一个关键信息，先告诉我缺的那部分。"

    def build_read_artifact_reply(self, contract: TaskContract, verification: VerificationResult) -> str:
        if verification.expected_signal_matched:
            return "任务单原文已读取，方向已重新锁定。请继续下一步执行。"
        stage_code = verification.contract_delta.get("stage_error_code") or "artifact_read_failed"
        return f"读取任务单原文失败，当前阶段错误码：{stage_code}。"

    def execute_artifact_read_step(self, artifact_id: str) -> Dict[str, Any]:
        started = time.time()
        metadata: Dict[str, Any] = {"artifact_id": artifact_id}
        try:
            if artifact_id.startswith("artifact://compacted/"):
                metadata["stage"] = "artifact_parse"
                result = get_compaction_manager().read(ReadRequest(artifact_id=artifact_id, mode="raw"))
                if not result.success:
                    metadata["stage_error_code"] = "artifact_parse_timeout"
                    return {
                        "success": False,
                        "output": "",
                        "error": result.error or "artifact read failed",
                        "metadata": metadata,
                        "execution_time_ms": (time.time() - started) * 1000,
                    }
                metadata["stage"] = "artifact_parse_completed"
                metadata["chars"] = len(result.content or "")
                return {
                    "success": True,
                    "output": (result.content or "")[:12000],
                    "error": None,
                    "metadata": metadata,
                    "execution_time_ms": (time.time() - started) * 1000,
                }
            if artifact_id.startswith("artifact://ingested/"):
                metadata["stage"] = "artifact_download"
                content = get_artifact_store().read_raw(artifact_id)
                if content is None:
                    metadata["stage_error_code"] = "artifact_download_timeout"
                    return {
                        "success": False,
                        "output": "",
                        "error": "artifact read failed",
                        "metadata": metadata,
                        "execution_time_ms": (time.time() - started) * 1000,
                    }
                metadata["stage"] = "artifact_download_completed"
                metadata["chars"] = len(content)
                return {
                    "success": True,
                    "output": content[:12000],
                    "error": None,
                    "metadata": metadata,
                    "execution_time_ms": (time.time() - started) * 1000,
                }
            metadata["stage_error_code"] = "artifact_unsupported_scheme"
            return {
                "success": False,
                "output": "",
                "error": f"Unsupported artifact id: {artifact_id}",
                "metadata": metadata,
                "execution_time_ms": (time.time() - started) * 1000,
            }
        except TimeoutError as exc:
            metadata["stage_error_code"] = "native_read_timeout"
            return {
                "success": False,
                "output": "",
                "error": str(exc),
                "metadata": metadata,
                "execution_time_ms": (time.time() - started) * 1000,
            }
        except Exception as exc:
            metadata["stage_error_code"] = "handoff_timeout" if "timeout" in str(exc).lower() else "artifact_read_failed"
            return {
                "success": False,
                "output": "",
                "error": str(exc),
                "metadata": metadata,
                "execution_time_ms": (time.time() - started) * 1000,
            }

    def build_execution_messages(
        self,
        *,
        base_messages: List[Dict[str, Any]],
        contract: TaskContract,
        step: NextStepDecision,
    ) -> List[Dict[str, Any]]:
        messages = list(base_messages)
        messages.append(
            {
                "role": "system",
                "content": (
                    "Contract Lock:\n"
                    f"{json.dumps(contract.to_dict(), ensure_ascii=False)}\n\n"
                    "Next Step Decision:\n"
                    f"{json.dumps(step.to_dict(), ensure_ascii=False)}\n\n"
                    "Rules:\n"
                    "1. This turn may execute at most one step.\n"
                    "2. If a tool is needed, call exactly one tool once.\n"
                    "3. Do not scan unrelated files.\n"
                    "4. If writing a file, write the final content directly.\n"
                    "5. After the single step, return a concise user-facing result.\n"
                ),
            }
        )
        return messages

    def execute_single_step_with_model(
        self,
        *,
        llm_client: Any,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        session_key: str,
        planning_timeout: int = 60,
        reply_timeout: int = 45,
    ) -> tuple[str, List[Dict[str, Any]], List[Dict[str, Any]], Optional[str]]:
        usage: List[Dict[str, Any]] = []
        try:
            response = llm_client.chat_with_tools(
                messages,
                tools,
                temperature=0.1,
                max_tokens=3000,
                timeout=planning_timeout,
            )
        except Exception as exc:
            if "timed out" in str(exc).lower() or isinstance(exc, TimeoutError):
                raise PlanningTimeoutError(str(exc)) from exc
            raise
        usage.append(response.usage or {})
        finish_reason = response.finish_reason
        tool_results: List[Dict[str, Any]] = []

        if response.has_tool_calls:
            call = response.tool_calls[0]
            result = execute_tool(
                call.get("name"),
                call.get("arguments") or {},
                None,
                f"contract_runtime_{session_key}",
            )
            result_dict = result.to_dict()
            tool_results.append(
                {
                    "tool_name": call.get("name"),
                    "arguments": call.get("arguments") or {},
                    "result": result_dict,
                }
            )
            followup_messages = list(messages)
            followup_messages.append(
                {
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": [
                        {
                            "id": call.get("id"),
                            "type": call.get("type", "function"),
                            "function": {
                                "name": call.get("name"),
                                "arguments": json.dumps(call.get("arguments") or {}, ensure_ascii=False),
                            },
                        }
                    ],
                }
            )
            followup_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id"),
                    "name": call.get("name"),
                    "content": json.dumps(result_dict, ensure_ascii=False),
                }
            )
            followup_messages.append(
                {
                    "role": "system",
                    "content": "The single step has been executed. Reply to the user briefly. Do not call more tools.",
                }
            )
            try:
                reply_response = llm_client.generate_with_messages(
                    followup_messages,
                    temperature=0.1,
                    max_tokens=800,
                    timeout=reply_timeout,
                )
            except Exception as exc:
                if "timed out" in str(exc).lower() or isinstance(exc, TimeoutError):
                    raise PlanningTimeoutError(str(exc)) from exc
                raise
            usage.append(reply_response.usage or {})
            finish_reason = reply_response.finish_reason or finish_reason
            return reply_response.content or "", tool_results, usage, finish_reason

        return response.content or "", tool_results, usage, finish_reason

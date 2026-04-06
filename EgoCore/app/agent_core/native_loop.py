from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from app.config import get_config, load_config
from app.llm_client import LLMClient, get_llm_client
from app.tools import execute_tool, get_registry, setup_tools

from .contract_runtime import ContractRuntimeEngine, NextStepDecision, PlanningTimeoutError, TaskContract, VerificationResult
from .context_builder import NativeContextBuilder


@dataclass
class NativeLoopResult:
    reply_text: str
    status: str = "completed_verified"
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    usage: List[Dict[str, Any]] = field(default_factory=list)
    finish_reason: Optional[str] = None
    task_contract: Optional[Dict[str, Any]] = None
    next_step_decision: Optional[Dict[str, Any]] = None
    verification_result: Optional[Dict[str, Any]] = None
    checkpoint_payload: Optional[Dict[str, Any]] = None


ProgressCallback = Callable[[str, Dict[str, Any]], Awaitable[None]]


class NativeToolCallingLoop:
    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        context_builder: Optional[NativeContextBuilder] = None,
    ) -> None:
        self.llm_client = llm_client or self._build_default_llm_client()
        self.context_builder = context_builder or NativeContextBuilder()
        self.contract_runtime = ContractRuntimeEngine()
        self._ensure_tools_ready()

    def _build_default_llm_client(self) -> LLMClient:
        repo_root = Path(__file__).resolve().parents[2]
        try:
            cfg = get_config()
        except Exception:
            cfg = load_config(
                config_dir=str(repo_root / "config"),
                env_file=str(repo_root / ".env"),
                validate=False,
            )
        use_case = cfg.get_llm_config_for_use_case("execution") if hasattr(cfg, "get_llm_config_for_use_case") else {}
        provider = use_case.get("provider") or getattr(cfg, "llm", {}).get("default_provider") or "openrouter"
        model = use_case.get("model") or getattr(cfg, "llm", {}).get("default_model") or "stepfun/step-3.5-flash:free"
        return get_llm_client(provider=str(provider), model=str(model))

    def _ensure_tools_ready(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        try:
            cfg = get_config()
        except Exception:
            cfg = load_config(
                config_dir=str(repo_root / "config"),
                env_file=str(repo_root / ".env"),
                validate=False,
            )
        registry = get_registry()
        if not registry.list_tools():
            setup_tools(cfg.get("tools", {}) if hasattr(cfg, "get") else {})

    def _build_tool_definitions(self) -> List[Dict[str, Any]]:
        registry = get_registry()
        definitions: List[Dict[str, Any]] = []
        for name, info in registry.get_tools_info().items():
            if not info.get("enabled"):
                continue
            definitions.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": info.get("description") or name,
                        "parameters": info.get("parameters_schema") or {"type": "object", "properties": {}},
                    },
                }
            )
        return definitions

    async def run_turn(
        self,
        *,
        session_key: str,
        user_input: str,
        ingress_context: Optional[Dict[str, Any]] = None,
        proto_self_context: Optional[Dict[str, Any]] = None,
        max_rounds: int = 6,
        resume_checkpoint: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> NativeLoopResult:
        async def emit_progress(phase: str, payload: Optional[Dict[str, Any]] = None) -> None:
            if progress_callback is None:
                return
            await progress_callback(phase, payload or {})

        resume_checkpoint = dict(resume_checkpoint or {})
        accumulated_tool_results: List[Dict[str, Any]] = list(resume_checkpoint.get("accumulated_tool_results") or [])
        ingress_context = dict(resume_checkpoint.get("ingress_context") or ingress_context or {})
        proto_self_context = dict(resume_checkpoint.get("proto_self_context") or proto_self_context or {})

        if resume_checkpoint.get("contract") and resume_checkpoint.get("next_step"):
            contract = TaskContract.from_dict(resume_checkpoint["contract"])
            next_step = NextStepDecision.from_dict(resume_checkpoint["next_step"])
        else:
            contract = self.contract_runtime.lock_contract(
                session_key=session_key,
                user_input=user_input,
                ingress_context=ingress_context,
                proto_self_context=proto_self_context,
            )
            next_step = self.contract_runtime.decide_next_step(contract=contract, ingress_context=ingress_context)
        await emit_progress(
            "locking_goal",
            {
                "target_path": contract.target_path,
                "source_artifact_id": contract.source_artifact_id,
                "action_type": next_step.action_type,
                "tool_name": next_step.tool_name,
            },
        )
        if contract.target_path or contract.source_artifact_id or (ingress_context or {}).get("resolved_target"):
            await emit_progress(
                "reading_context",
                {
                    "target_path": contract.target_path,
                    "source_artifact_id": contract.source_artifact_id,
                    "resolved_target": (ingress_context or {}).get("resolved_target"),
                },
            )
        if next_step.action_type == "ask_user":
            reply_text = self.contract_runtime.build_ask_reply(contract)
            verification = self.contract_runtime.verify_step(
                contract=contract,
                step=next_step,
                tool_result=None,
                reply_text=reply_text,
            )
            return NativeLoopResult(
                status="waiting_input",
                reply_text=reply_text,
                tool_results=[],
                usage=[],
                finish_reason="ask_user",
                task_contract=contract.to_dict(),
                next_step_decision=next_step.to_dict(),
                verification_result=verification.to_dict(),
            )
        if next_step.action_type == "read_artifact":
            await emit_progress(
                "reading_context",
                {
                    "source_artifact_id": contract.source_artifact_id,
                    "action_type": next_step.action_type,
                    "tool_name": next_step.tool_name,
                },
            )
            artifact_result = self.contract_runtime.execute_artifact_read_step(contract.source_artifact_id or "")
            accumulated_tool_results.append(
                {
                    "tool_name": "read_artifact",
                    "arguments": {"artifact_id": contract.source_artifact_id},
                    "result": artifact_result,
                }
            )
            if artifact_result.get("success") and artifact_result.get("output"):
                ingress_context = {**(ingress_context or {}), "resolved_artifact_text": artifact_result.get("output")}
                contract = self.contract_runtime.lock_contract(
                    session_key=session_key,
                    user_input=user_input,
                    ingress_context=ingress_context,
                    proto_self_context=proto_self_context,
                )
                next_step = self.contract_runtime.decide_next_step(contract=contract, ingress_context=ingress_context)
                if next_step.action_type == "ask_user":
                    reply_text = self.contract_runtime.build_ask_reply(contract)
                    verification = self.contract_runtime.verify_step(
                        contract=contract,
                        step=next_step,
                        tool_result=None,
                        reply_text=reply_text,
                    )
                    return NativeLoopResult(
                        status="waiting_input",
                        reply_text=reply_text,
                        tool_results=accumulated_tool_results,
                        usage=[],
                        finish_reason="ask_user_after_relock",
                        task_contract=contract.to_dict(),
                        next_step_decision=next_step.to_dict(),
                        verification_result=verification.to_dict(),
                    )
            else:
                verification = self.contract_runtime.verify_step(
                    contract=contract,
                    step=next_step,
                    tool_result=artifact_result,
                    reply_text="",
                )
                return NativeLoopResult(
                    status="blocked",
                    reply_text=self.contract_runtime.build_read_artifact_reply(contract, verification),
                    tool_results=accumulated_tool_results,
                    usage=[],
                    finish_reason="artifact_read_step",
                    task_contract=contract.to_dict(),
                    next_step_decision=next_step.to_dict(),
                    verification_result=verification.to_dict(),
                )

        await emit_progress(
            "executing_changes",
            {
                "action_type": next_step.action_type,
                "tool_name": next_step.tool_name,
                "target_path": contract.target_path,
            },
        )
        messages = self.context_builder.build_messages(
            session_key=session_key,
            user_input=user_input,
            ingress_context=ingress_context,
            proto_self_context=proto_self_context,
            task_contract=contract.to_dict(),
            next_step=next_step.to_dict(),
        )
        tools = self._build_tool_definitions()
        execution_messages = self.contract_runtime.build_execution_messages(
            base_messages=messages,
            contract=contract,
            step=next_step,
        )
        planning_timeout = 90 if contract.output_format == "html" and contract.target_path else 60
        reply_timeout = 60 if contract.output_format == "html" else 45
        try:
            reply_text, tool_results, usage, last_finish_reason = await asyncio.to_thread(
                self.contract_runtime.execute_single_step_with_model,
                llm_client=self.llm_client,
                messages=execution_messages,
                tools=tools,
                session_key=session_key,
                planning_timeout=planning_timeout,
                reply_timeout=reply_timeout,
            )
        except (PlanningTimeoutError, TimeoutError) as exc:
            checkpoint_payload = {
                "contract": contract.to_dict(),
                "next_step": next_step.to_dict(),
                "ingress_context": ingress_context,
                "proto_self_context": proto_self_context,
                "accumulated_tool_results": accumulated_tool_results,
            }
            return NativeLoopResult(
                status="resumable_pause",
                reply_text="",
                tool_results=accumulated_tool_results,
                usage=[],
                finish_reason="planning_timeout",
                task_contract=contract.to_dict(),
                next_step_decision=next_step.to_dict(),
                verification_result={
                    "step_id": next_step.step_id,
                    "observed_result": {"reply_text": "", "error": str(exc)},
                    "expected_signal_matched": False,
                    "contract_delta": {"reason": str(exc), "stage_error_code": "planning_timeout"},
                    "need_relock": False,
                    "stop_reason": "planning_timeout",
                },
                checkpoint_payload=checkpoint_payload,
            )
        if asyncio.iscoroutine(reply_text):
            reply_text, tool_results, usage, last_finish_reason = await reply_text
        await emit_progress(
            "verifying",
            {
                "action_type": next_step.action_type,
                "tool_name": next_step.tool_name,
                "tool_results_count": len(tool_results),
            },
        )
        tool_result_payload = tool_results[0]["result"] if tool_results else None
        verification = self.contract_runtime.verify_step(
            contract=contract,
            step=next_step,
            tool_result=tool_result_payload,
            reply_text=reply_text,
        )
        return NativeLoopResult(
            status="completed_verified",
            reply_text=reply_text,
            tool_results=accumulated_tool_results + tool_results,
            usage=usage,
            finish_reason=last_finish_reason,
            task_contract=contract.to_dict(),
            next_step_decision=next_step.to_dict(),
            verification_result=verification.to_dict(),
        )

from __future__ import annotations

import asyncio
import json
import logging
from typing import Dict, List, Optional, Tuple

import httpx

from app.config import ConfigError, get_config
from app.llm_client import get_llm_client

from .action_protocol import RUNTIME_V2_SYSTEM_PROMPT, RuntimeV2Action
from .prompt_files import RuntimeV2PromptFiles
from .state import RuntimeV2State

logger = logging.getLogger(__name__)


class RuntimeV2DecisionEngine:
    def __init__(self) -> None:
        self.prompt_files = RuntimeV2PromptFiles()
        self.llm_client = None

    def build_system_prompt(self) -> str:
        bundle = self.prompt_files.load()
        rendered = bundle.render()
        if rendered:
            return rendered + "\n\n## BUILTIN_RUNTIME_V2_CONTRACT\n" + RUNTIME_V2_SYSTEM_PROMPT
        return RUNTIME_V2_SYSTEM_PROMPT

    def build_policy_hint_context(self, proto_self_context: dict) -> str:
        """
        从 Proto-Self Kernel 输出构建 policy hint 注入文本。
        """
        if not proto_self_context:
            return ""
        
        policy_hint = proto_self_context.get("policy_hint", {})
        response_tendency = proto_self_context.get("response_tendency", {})
        reflection_note = proto_self_context.get("reflection_note")
        candidate_actions = list(proto_self_context.get("candidate_actions") or [])
        governor_hint = proto_self_context.get("governor_hint") or {}
        
        parts = []
        
        if policy_hint:
            risk_bias = policy_hint.get("risk_bias", "normal")
            closure_bias = policy_hint.get("closure_bias", False)
            ask_preferred = policy_hint.get("ask_preferred", False)
            subject_profile = policy_hint.get("subject_profile")

            if risk_bias == "high":
                parts.append("- 当前风险评估偏高，谨慎行事")
            if closure_bias:
                parts.append("- 有未完成任务，优先收尾")
            if ask_preferred:
                parts.append("- 建议在执行前向用户确认")
            if subject_profile == "seed_v0_2":
                parts.append("- 当前 Proto-Self Seed v0.2 已启用；candidate_actions 仅为主体建议，不等于已执行")

        if candidate_actions:
            action_types = [item.get("action_type") for item in candidate_actions[:3] if item.get("action_type")]
            if action_types:
                parts.append(f"- 当前主体候选动作: {', '.join(action_types)}")

        if governor_hint:
            status = governor_hint.get("status")
            reason = governor_hint.get("reason")
            if status:
                parts.append(f"- 当前主体治理建议: {status}")
            if reason:
                parts.append(f"- 治理原因: {reason}")
        
        if response_tendency:
            preferred_mode = response_tendency.get("preferred_mode", "respond")
            preferred_tone = response_tendency.get("preferred_tone", "calm")
            if preferred_mode == "repair":
                parts.append("- 系统处于修复模式，注意错误恢复")
            if preferred_tone == "cautious":
                parts.append("- 回复基调：谨慎")
        
        if reflection_note:
            trigger = reflection_note.get("trigger", "")
            if trigger == "external_failure":
                parts.append("- 刚才的操作失败，考虑重试或换方案")
            elif trigger == "identity_conflict":
                parts.append("- 检测到身份边界冲突，注意审查")
        
        if not parts:
            return ""
        
        return "\n## 主体倾向提示\n" + "\n".join(parts) + "\n"

    def build_profile_rule_context(self, ingress_context: dict) -> str:
        if not ingress_context:
            return ""

        matched_rules = ingress_context.get("matched_profile_rules") or []
        active_rules = ingress_context.get("active_profile_rules") or []
        rule_enforcement = ingress_context.get("rule_enforcement") or {}
        lines: List[str] = []

        if matched_rules:
            lines.append("## 当前命中的用户默认规则")
            for item in matched_rules[:3]:
                summary = item.get("summary")
                if summary:
                    lines.append(f"- {summary}")
        elif active_rules:
            lines.append("## 当前生效的用户默认规则")
            for item in active_rules[:3]:
                summary = item.get("summary")
                if summary:
                    lines.append(f"- {summary}")

        if rule_enforcement:
            kind = rule_enforcement.get("kind")
            if kind == "reply_only_once":
                lines.append("- 这轮若要执行宿主裁决，固定短句优先，且不继续展开。")
            elif kind == "read_only_preflight":
                lines.append("- 这轮受高风险默认规则约束：只读检查优先，不要直接改文件，先给最小验证动作。")

        if not lines:
            return ""
        return "\n" + "\n".join(lines) + "\n"

    def build_restore_context(self, ingress_context: dict) -> str:
        if not ingress_context:
            return ""

        restore_observation = ingress_context.get("restore_observation") or {}
        if not restore_observation:
            return ""

        lines: List[str] = [
            "## Restore 观察提示",
            "- 这轮是显式 restore 后的首条真实用户消息。",
            f"- restore_status: {restore_observation.get('restore_status', 'unknown')}",
        ]
        if restore_observation.get("recovery_hints_present"):
            lines.append("- restore 注入摘要显示存在 recovery hints，优先保持连续性。")
        for item in (restore_observation.get("standing_commitments_preview") or [])[:3]:
            if item:
                lines.append(f"- 恢复后的 standing commitment: {item}")
        return "\n" + "\n".join(lines) + "\n"

    def build_conversation_act_context(self, ingress_context: dict) -> str:
        if not ingress_context:
            return ""

        conversation_act = str(ingress_context.get("conversation_act") or "").strip()
        interaction_kind = str(ingress_context.get("interaction_kind") or "").strip()
        if not conversation_act and not interaction_kind:
            return ""

        lines: List[str] = ["## 对话行为提示"]
        if interaction_kind:
            lines.append(f"- interaction_kind: {interaction_kind}")
        if conversation_act:
            lines.append(f"- conversation_act: {conversation_act}")

        if conversation_act == "presence_check":
            lines.append("- 这是用户在确认你是否在线/在场，属于普通聊天，不是任务状态查询。")
            lines.append("- 正常自然地回应，可以简短，但不要把它当成固定模板句。")
            lines.append("- 不要回放旧工具结果、目录正文或任务总结，除非用户明确继续追问。")

        return "\n" + "\n".join(lines) + "\n"

    async def decide(self, state: RuntimeV2State) -> RuntimeV2Action:
        system_prompt = self.build_system_prompt()
        
        # 注入 Proto-Self Kernel policy hint
        policy_hint_context = self.build_policy_hint_context(state.proto_self_context or {})
        if policy_hint_context:
            system_prompt = system_prompt + policy_hint_context

        profile_rule_context = self.build_profile_rule_context(state.ingress_context or {})
        if profile_rule_context:
            system_prompt = system_prompt + profile_rule_context

        restore_context = self.build_restore_context(state.ingress_context or {})
        if restore_context:
            system_prompt = system_prompt + restore_context

        conversation_act_context = self.build_conversation_act_context(state.ingress_context or {})
        if conversation_act_context:
            system_prompt = system_prompt + conversation_act_context

        decision_state = (
            state.to_execute_task_prompt_context()
            if (state.ingress_context or {}).get("runtime_action") == "execute_task" and state.get_run_items()
            else state.to_decision_prompt_context()
        )
        instruction = "根据当前状态输出下一个 JSON action。若需要执行，优先 act；若执行后可验证完成，则 complete；若只是寒暄，chat。"
        if (state.ingress_context or {}).get("runtime_action") == "execute_task" and state.get_run_items():
            instruction += " 当前存在 host-owned ordered run_items，你只能推进 active_item，不能跳到后续 item，也不能写入与 active_item.canonical_path 不一致的路径。"

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "state": decision_state,
                        "instruction": instruction,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            },
        ]
        max_tokens = self._decide_max_tokens(state)
        timeout_seconds = self._decide_timeout_seconds(state)
        try:
            response = await self._generate_with_fallback(
                messages,
                max_tokens=max_tokens,
                timeout_seconds=timeout_seconds,
            )
            if response.usage:
                prompt_tokens = response.usage.get("prompt_tokens", 0) or response.usage.get("input_tokens", 0)
                completion_tokens = response.usage.get("completion_tokens", 0) or response.usage.get("output_tokens", 0)
                state.record_token_usage(prompt_tokens, completion_tokens)
            return RuntimeV2Action.from_model_output(response.content)
        except Exception as e:
            return self._build_error_action(e)

    def _decide_max_tokens(self, state: RuntimeV2State) -> int:
        ingress = state.ingress_context or {}
        requested_output = ingress.get("requested_output") or {}
        if requested_output.get("format") in {"html", "markdown"}:
            return 8000
        if ingress.get("request_mode") == "write":
            return 4000
        return 1200

    def _decide_timeout_seconds(self, state: RuntimeV2State) -> int:
        timeout_seconds = 60
        try:
            config = get_config()
            request_cfg = config.llm.get("request") or {}
            timeout_seconds = int(request_cfg.get("timeout") or 60)
        except (ConfigError, TypeError, ValueError):
            timeout_seconds = 60

        ingress = state.ingress_context or {}
        requested_output = ingress.get("requested_output") or {}
        output_format = requested_output.get("format")
        if output_format in {"html", "markdown"}:
            return max(timeout_seconds, 90)
        if ingress.get("request_mode") == "write":
            return max(timeout_seconds, 75)
        return timeout_seconds

    def _is_transient_decision_error(self, error: Exception) -> bool:
        if isinstance(error, httpx.HTTPStatusError):
            response = getattr(error, "response", None)
            status_code = getattr(response, "status_code", None)
            return status_code in {408, 429, 500, 502, 503, 504}
        return isinstance(
            error,
            (
                httpx.TimeoutException,
                httpx.NetworkError,
                TimeoutError,
                ConnectionError,
            ),
        )

    def _is_auth_or_config_error(self, error: Exception) -> bool:
        if isinstance(error, ValueError):
            return True
        if isinstance(error, httpx.HTTPStatusError):
            response = getattr(error, "response", None)
            status_code = getattr(response, "status_code", None)
            return status_code in {401, 403}
        return False

    def _resolve_runtime_v2_primary_spec(self) -> Tuple[str, str]:
        config = get_config()
        use_case = config.get_llm_config_for_use_case("execution")
        provider = use_case.get("provider") or config.llm.get("default_provider", "qianfan")
        model = use_case.get("model") or config.llm.get("default_model", "glm-5")
        return str(provider), str(model)

    def _resolve_provider_default_model(self, provider: str) -> Optional[str]:
        config = get_config()
        provider_cfg = (config.llm.get("providers") or {}).get(provider) or {}
        if provider_cfg.get("enabled") is False:
            return None
        for item in provider_cfg.get("models") or []:
            model_id = item.get("id")
            if model_id:
                return str(model_id)
        return None

    def _resolve_qianfan_runtime_v2_fallback_models(self) -> List[str]:
        config = get_config()
        provider_cfg = (config.llm.get("providers") or {}).get("qianfan") or {}
        models = []
        for item in provider_cfg.get("runtime_v2_fallback_models") or []:
            model = str(item).strip()
            if model:
                models.append(model)
        return models

    def _resolve_runtime_v2_client_specs(self) -> List[Tuple[str, str]]:
        primary_provider, primary_model = self._resolve_runtime_v2_primary_spec()
        specs: List[Tuple[str, str]] = [(primary_provider, primary_model)]
        if primary_provider == "qianfan":
            for model in self._resolve_qianfan_runtime_v2_fallback_models():
                if model != primary_model:
                    specs.append(("qianfan", model))
            return specs

        config = get_config()
        fallback_cfg = config.llm.get("fallback") or {}
        if not fallback_cfg.get("enabled"):
            return specs

        for provider in fallback_cfg.get("providers") or []:
            provider_name = str(provider)
            if provider_name == primary_provider:
                continue
            model = self._resolve_provider_default_model(provider_name)
            if model:
                specs.append((provider_name, model))
        return specs

    def _resolve_runtime_v2_clients(self) -> List[Tuple[str, str, object]]:
        if self.llm_client is not None:
            return [("injected", "injected", self.llm_client)]

        clients: List[Tuple[str, str, object]] = []
        for provider, model in self._resolve_runtime_v2_client_specs():
            try:
                clients.append((provider, model, get_llm_client(provider=provider, model=model)))
            except Exception as e:
                logger.warning(
                    "runtime_v2.decision.client_unavailable provider=%s model=%s err=%s",
                    provider,
                    model,
                    e,
                )
        return clients

    async def _generate_with_fallback(
        self,
        messages: List[Dict[str, str]],
        *,
        max_tokens: int,
        timeout_seconds: int,
    ):
        candidates = self._resolve_runtime_v2_clients()
        if not candidates:
            raise RuntimeError("No configured runtime_v2 decision providers are available")

        primary_error: Optional[Exception] = None
        last_error: Optional[Exception] = None
        for index, (provider, model, client) in enumerate(candidates):
            try:
                return await asyncio.to_thread(
                    client.generate_with_messages,
                    messages,
                    temperature=0.1,
                    max_tokens=max_tokens,
                    timeout=timeout_seconds,
                )
            except Exception as e:
                last_error = e
                is_primary = index == 0
                if is_primary:
                    primary_error = e
                    if not self._is_transient_decision_error(e):
                        raise
                    if index + 1 >= len(candidates):
                        raise
                    next_provider, next_model, _next_client = candidates[index + 1]
                    logger.warning(
                        "runtime_v2.decision.transient provider=%s model=%s fallback_provider=%s fallback_model=%s err=%s",
                        provider,
                        model,
                        next_provider,
                        next_model,
                        e,
                    )
                    continue

                if self._is_auth_or_config_error(e):
                    logger.warning(
                        "runtime_v2.decision.fallback_unavailable provider=%s model=%s err=%s",
                        provider,
                        model,
                        e,
                    )
                    continue

                if self._is_transient_decision_error(e):
                    logger.warning(
                        "runtime_v2.decision.fallback_transient provider=%s model=%s err=%s",
                        provider,
                        model,
                        e,
                    )
                    continue

                logger.warning(
                    "runtime_v2.decision.fallback_nontransient provider=%s model=%s err=%s",
                    provider,
                    model,
                    e,
                )
                continue

        if primary_error is not None:
            raise primary_error
        if last_error is not None:
            raise last_error
        raise RuntimeError("Runtime v2 decision fallback exhausted without candidates")

    def _build_error_action(self, error: Exception) -> RuntimeV2Action:
        response = getattr(error, "response", None)
        status_code = getattr(response, "status_code", None)
        retryable = self._is_transient_decision_error(error)
        kind = "transient_decision_error" if retryable else "decision_error"
        retry_after_seconds = 15
        transient_kind = None
        if retryable and status_code == 429:
            transient_kind = "rate_limited"
            retry_after_seconds = 45
        elif retryable:
            transient_kind = "timeout_or_server_busy"
            retry_after_seconds = 20

        if retryable and status_code == 429:
            question = "当前模型繁忙，我会延后自动重试。"
        elif retryable:
            question = "Runtime v2 模型暂时不可用，我会继续自动重试。"
        else:
            question = f"Runtime v2 当前模型决策不可用：{error}"
        raw = {
            "type": "ask",
            "kind": kind,
            "retryable": retryable,
            "error": str(error),
            "error_class": type(error).__name__,
        }
        if status_code is not None:
            raw["status_code"] = status_code
        if transient_kind:
            raw["transient_kind"] = transient_kind
            raw["retry_after_seconds"] = retry_after_seconds
        return RuntimeV2Action(
            type="ask",
            question=question,
            raw=raw,
        )

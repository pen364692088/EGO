from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


KNOWN_MOCK_SCENARIO_IDS = frozenset(
    {
        "goal_definition_failure",
        "evidence_failure",
        "plan_failure",
        "permission_failure",
        "execution_failure",
        "destructive_action_request",
        "external_send_request",
        "claim_boundary_query",
        "ambiguous_user_concern",
    }
)

SAFETY_PRE_ROUTER_SCENARIO_IDS = frozenset(
    {
        "destructive_action_request",
        "external_send_request",
        "permission_failure",
        "claim_boundary_query",
    }
)


@dataclass(frozen=True)
class SemanticProviderRequest:
    scenario: Any
    core_result: Any
    allowed_evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class SemanticProviderResult:
    provider_name: str
    raw_outputs: dict[str, str]
    observation: dict[str, object] | None = None
    admission_eligible: bool = True
    reason: str = ""


@dataclass(frozen=True)
class SemanticProviderSelection:
    admitted_outputs: dict[str, str]
    admitted_provider: str
    provider_trace: dict[str, object]
    shadow_outputs: dict[str, str]
    shadow_observation: dict[str, object] | None


class SemanticProvider(Protocol):
    def generate(self, request: SemanticProviderRequest) -> SemanticProviderResult:
        ...


class RuleSafetyPreRouter:
    provider_name = "rule_safety_pre_router"

    def generate(self, request: SemanticProviderRequest) -> SemanticProviderResult:
        scenario_id = route_text_to_safety_scenario_id(str(request.scenario.text))
        if scenario_id is None:
            return SemanticProviderResult(
                provider_name=self.provider_name,
                raw_outputs={},
                reason="no safety pre-route matched",
            )
        outputs = MockSemanticProvider().generate_for_scenario_key(request, scenario_id)
        return SemanticProviderResult(
            provider_name=self.provider_name,
            raw_outputs=outputs,
            reason=f"safety pre-route matched {scenario_id}",
        )


class MockSemanticProvider:
    provider_name = "mock_semantic_provider"

    def generate(self, request: SemanticProviderRequest) -> SemanticProviderResult:
        scenario_key = _mock_scenario_key(request.scenario)
        return SemanticProviderResult(
            provider_name=self.provider_name,
            raw_outputs=self.generate_for_scenario_key(request, scenario_key),
            reason=f"mock scenario route {scenario_key}",
        )

    def generate_for_scenario_key(
        self,
        request: SemanticProviderRequest,
        scenario_key: str,
    ) -> dict[str, str]:
        selected = request.core_result.selected_intention
        goal_id = selected.goal_id if selected and selected.goal_id else "goal:001"
        intention_id = selected.id if selected else "none"
        scenario_ref = f"scenario:{request.scenario.scenario_id}"
        semantic = _semantic_payload_for_scenario(scenario_key, scenario_ref, goal_id)
        outputs = {"semantic": json.dumps(semantic, sort_keys=True)}
        if scenario_key not in {
            "ambiguous_user_concern",
            "destructive_action_request",
            "external_send_request",
            "claim_boundary_query",
        }:
            outputs["plan"] = json.dumps(
                _plan_payload_for_scenario(scenario_key, goal_id, intention_id),
                sort_keys=True,
            )
        if scenario_key == "goal_definition_failure":
            outputs["goal_operation"] = json.dumps(_goal_operation_payload(scenario_ref, goal_id), sort_keys=True)
        return outputs


class LiveLLMShadowProvider:
    provider_name = "live_llm_shadow_provider"

    def generate(self, request: SemanticProviderRequest) -> SemanticProviderResult:
        if os.environ.get("EGO_DESKTOP_LAB_ENABLE_LIVE_LLM") != "1":
            return SemanticProviderResult(
                provider_name=self.provider_name,
                raw_outputs={},
                observation={"status": "skipped", "reason": "EGO_DESKTOP_LAB_ENABLE_LIVE_LLM is not 1"},
                admission_eligible=False,
                reason="live shadow disabled",
            )
        openrouter_key = os.environ.get("OPENROUTER_API_KEY")
        if openrouter_key or _uses_openrouter_base_url():
            return _generate_openrouter_shadow(request, openrouter_key)

        bearer_token, auth_source, auth_reason = _resolve_live_bearer_token()
        model = os.environ.get("EGO_DESKTOP_LAB_LIVE_LLM_MODEL") or _codex_config_model()
        if not bearer_token or not model:
            return SemanticProviderResult(
                provider_name=self.provider_name,
                raw_outputs={},
                observation={
                    "status": "skipped",
                    "reason": auth_reason if not bearer_token else "EGO_DESKTOP_LAB_LIVE_LLM_MODEL is missing",
                    "auth_source": auth_source,
                },
                admission_eligible=False,
                reason="live shadow credentials or model missing",
            )

        prompt = _live_prompt(request.scenario, request.core_result, request.allowed_evidence_refs)
        body = json.dumps({"model": model, "input": prompt}).encode("utf-8")
        http_request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=body,
            headers={
                "Authorization": f"Bearer {bearer_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - live shadow is opt-in and non-deterministic.
            return SemanticProviderResult(
                provider_name=self.provider_name,
                raw_outputs={},
                observation={
                    "status": "unavailable",
                    "reason": str(exc),
                    "auth_source": auth_source,
                    "model": model,
                },
                admission_eligible=False,
                reason="live shadow unavailable",
            )

        raw_text = _extract_response_text(payload)
        if not raw_text:
            return SemanticProviderResult(
                provider_name=self.provider_name,
                raw_outputs={},
                observation={
                    "status": "unavailable",
                    "reason": "live response did not include text",
                    "auth_source": auth_source,
                    "model": model,
                },
                admission_eligible=False,
                reason="live shadow empty",
            )
        return SemanticProviderResult(
            provider_name=self.provider_name,
            raw_outputs={"semantic": raw_text},
            observation={"status": "observed", "model": model, "auth_source": auth_source},
            admission_eligible=False,
            reason="live shadow observed proposal-only output",
        )


def select_semantic_provider_outputs(
    request: SemanticProviderRequest,
    *,
    provider_mode: str,
    mock_payloads: dict[str, str] | None = None,
    shadow_provider: SemanticProvider | None = None,
) -> SemanticProviderSelection:
    if provider_mode not in {"mock", "live", "none"}:
        raise ValueError(f"unsupported provider_mode: {provider_mode}")

    pre_route = RuleSafetyPreRouter().generate(request)
    shadow_result = _generate_shadow(request, provider_mode=provider_mode, shadow_provider=shadow_provider)

    if pre_route.raw_outputs:
        admitted_outputs = pre_route.raw_outputs
        admitted_provider = pre_route.provider_name
        admitted_reason = pre_route.reason
    elif mock_payloads is not None:
        admitted_outputs = dict(mock_payloads)
        admitted_provider = "explicit_mock_payloads"
        admitted_reason = "explicit mock payloads supplied by caller"
    elif provider_mode in {"mock", "live"}:
        mock_result = MockSemanticProvider().generate(request)
        admitted_outputs = mock_result.raw_outputs
        admitted_provider = mock_result.provider_name
        admitted_reason = mock_result.reason
    else:
        admitted_outputs = {}
        admitted_provider = "none"
        admitted_reason = "provider_mode none and no safety pre-route"

    provider_trace = {
        "provider_mode_requested": provider_mode,
        "pre_router_provider": pre_route.provider_name,
        "pre_router_applied": bool(pre_route.raw_outputs),
        "pre_router_reason": pre_route.reason,
        "admitted_provider": admitted_provider,
        "admitted_provider_reason": admitted_reason,
        "shadow_provider": shadow_result.provider_name if shadow_result else None,
        "shadow_provider_enabled": shadow_result is not None,
        "shadow_admission_eligible": bool(shadow_result.admission_eligible) if shadow_result else False,
        "shadow_can_influence_core": False,
        "shadow_reason": shadow_result.reason if shadow_result else None,
    }
    return SemanticProviderSelection(
        admitted_outputs=admitted_outputs,
        admitted_provider=admitted_provider,
        provider_trace=provider_trace,
        shadow_outputs=shadow_result.raw_outputs if shadow_result else {},
        shadow_observation=shadow_result.observation if shadow_result else None,
    )


def route_text_to_safety_scenario_id(text: str) -> str | None:
    normalized = " ".join(text.lower().split())
    safety_groups: tuple[tuple[str, tuple[str, ...]], ...] = (
        (
            "destructive_action_request",
            (
                "删除",
                "删",
                "清空",
                "移除",
                "抹掉",
                "擦除",
                "旧日志",
                "清理日志",
                "delete",
                "remove",
                "wipe",
                "clear directory",
                "rm -",
                "rm ",
            ),
        ),
        (
            "external_send_request",
            (
                "发送",
                "发给",
                "发邮件",
                "发消息",
                "外部联系人",
                "外部消息",
                "转发",
                "上传",
                "send externally",
                "send to",
                "send this",
                "email",
                "message",
                "post",
                "upload",
                "share",
            ),
        ),
        (
            "claim_boundary_query",
            (
                "自我意识",
                "有意识",
                "意识了",
                "consciousness",
                "alive",
                "soul",
            ),
        ),
        (
            "permission_failure",
            (
                "ask permission",
                "requires permission",
                "require permission",
                "need permission",
                "needs permission",
                "permission required",
                "ask for approval",
                "needs approval",
                "requires approval",
                "ask before",
                "allowed to",
                "ask before",
                "read file",
                "write file",
                "local file",
                "权限",
                "授权",
                "批准",
                "允许",
                "读取",
                "修改",
                "写入",
                "本地文件",
                "先问",
                "获得权限",
            ),
        ),
    )
    for scenario_id, keywords in safety_groups:
        if any(_keyword_matches(normalized, keyword) for keyword in keywords):
            return scenario_id
    return None


def route_text_to_mock_scenario_id(text: str) -> str:
    safety_id = route_text_to_safety_scenario_id(text)
    if safety_id is not None:
        return safety_id
    normalized = " ".join(text.lower().split())
    if _negated_execution_points_to_goal_definition(normalized):
        return "goal_definition_failure"
    keyword_groups: tuple[tuple[str, tuple[str, ...]], ...] = (
        (
            "goal_definition_failure",
            (
                "goal definition",
                "success criteria",
                "scope unclear",
                "unclear goal",
                "split goal",
                "redefine",
                "goal too large",
                "too large",
                "目标不清",
                "成功标准",
                "拆分目标",
                "目标太大",
                "拆成",
                "小目标",
                "两个目标",
                "三个小目标",
                "目标本身",
                "定义清楚",
                "没有定义清楚",
                "定义、验证、展示",
            ),
        ),
        (
            "execution_failure",
            (
                "execution failed",
                "failed to run",
                "tool failed",
                "runtime error",
                "timeout",
                "crash",
                "retry",
                "执行失败",
                "工具失败",
                "运行失败",
            ),
        ),
        (
            "plan_failure",
            (
                "plan failed",
                "replan",
                "repair",
                "wrong steps",
                "chosen steps",
                "does not resolve",
                "no improvement",
                "not improving",
                "need to replan",
                "计划失败",
                "步骤",
                "重做计划",
                "修复计划",
                "结果没有改善",
                "没有改善",
                "重新规划",
                "重规划",
                "当前计划没有意义",
                "继续做当前计划没有意义",
                "修复或重规划",
                "修复或重新规划",
            ),
        ),
        (
            "evidence_failure",
            (
                "evidence",
                "verify",
                "claim without",
                "proof",
                "unsupported",
                "source",
                "证据",
                "验证",
                "无依据",
                "证明",
            ),
        ),
    )
    for scenario_id, keywords in keyword_groups:
        if any(_keyword_matches(normalized, keyword) for keyword in keywords):
            return scenario_id
    return "ambiguous_user_concern"


def _generate_shadow(
    request: SemanticProviderRequest,
    *,
    provider_mode: str,
    shadow_provider: SemanticProvider | None,
) -> SemanticProviderResult | None:
    if provider_mode != "live":
        return None
    provider = shadow_provider or LiveLLMShadowProvider()
    result = provider.generate(request)
    return SemanticProviderResult(
        provider_name=result.provider_name,
        raw_outputs=dict(result.raw_outputs),
        observation=result.observation,
        admission_eligible=False,
        reason=result.reason,
        )


def _generate_openrouter_shadow(
    request: SemanticProviderRequest,
    api_key: str | None,
) -> SemanticProviderResult:
    base_url = os.environ.get("EGO_DESKTOP_LAB_LIVE_LLM_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
    model = os.environ.get("EGO_DESKTOP_LAB_LIVE_LLM_MODEL") or "tencent/hy3-preview"
    if not api_key:
        return SemanticProviderResult(
            provider_name=LiveLLMShadowProvider.provider_name,
            raw_outputs={},
            observation={
                "status": "skipped",
                "reason": "OPENROUTER_API_KEY is missing",
                "auth_source": "OPENROUTER_API_KEY",
                "api_provider": "openrouter",
                "base_url": base_url,
                "model": model,
            },
            admission_eligible=False,
            reason="openrouter live shadow credentials missing",
        )

    prompt = _live_prompt(request.scenario, request.core_result, request.allowed_evidence_refs)
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "reasoning": {"enabled": True},
        }
    ).encode("utf-8")
    http_request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.environ.get("EGO_DESKTOP_LAB_LIVE_LLM_REFERER", "https://localhost/ego_desktop_lab"),
            "X-Title": os.environ.get("EGO_DESKTOP_LAB_LIVE_LLM_TITLE", "ego_desktop_lab live shadow"),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(http_request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # pragma: no cover - live shadow is opt-in and non-deterministic.
        return SemanticProviderResult(
            provider_name=LiveLLMShadowProvider.provider_name,
            raw_outputs={},
            observation={
                "status": "unavailable",
                "reason": str(exc),
                "auth_source": "OPENROUTER_API_KEY",
                "api_provider": "openrouter",
                "base_url": base_url,
                "model": model,
            },
            admission_eligible=False,
            reason="openrouter live shadow unavailable",
        )

    raw_text = _extract_chat_completion_text(payload)
    if not raw_text:
        return SemanticProviderResult(
            provider_name=LiveLLMShadowProvider.provider_name,
            raw_outputs={},
            observation={
                "status": "unavailable",
                "reason": "OpenRouter response did not include assistant content",
                "auth_source": "OPENROUTER_API_KEY",
                "api_provider": "openrouter",
                "base_url": base_url,
                "model": model,
            },
            admission_eligible=False,
            reason="openrouter live shadow empty",
        )
    return SemanticProviderResult(
        provider_name=LiveLLMShadowProvider.provider_name,
        raw_outputs={"semantic": raw_text},
        observation={
            "status": "observed",
            "auth_source": "OPENROUTER_API_KEY",
            "api_provider": "openrouter",
            "base_url": base_url,
            "model": model,
        },
        admission_eligible=False,
        reason="openrouter live shadow observed proposal-only output",
    )


def _uses_openrouter_base_url() -> bool:
    base_url = os.environ.get("EGO_DESKTOP_LAB_LIVE_LLM_BASE_URL", "")
    return "openrouter.ai" in base_url.lower()


def _resolve_live_bearer_token() -> tuple[str | None, str | None, str]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        return api_key, "OPENAI_API_KEY", "OPENAI_API_KEY found"
    auth_path = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser() / "auth.json"
    try:
        data = json.loads(auth_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "codex_oauth", f"Codex OAuth auth file not found at {auth_path}"
    except Exception as exc:
        return None, "codex_oauth", f"Codex OAuth auth file could not be read: {type(exc).__name__}"
    tokens = data.get("tokens")
    if not isinstance(tokens, dict):
        return None, "codex_oauth", "Codex OAuth tokens object is missing"
    access_token = tokens.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        return None, "codex_oauth", "Codex OAuth access_token is missing"
    return access_token, "codex_oauth", "Codex OAuth access_token found"


def _codex_config_model() -> str | None:
    config_path = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser() / "config.toml"
    try:
        for line in config_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped.startswith("model"):
                continue
            key, separator, value = stripped.partition("=")
            if not separator or key.strip() != "model":
                continue
            model = value.strip().strip("\"'")
            return model or None
    except FileNotFoundError:
        return None
    except Exception:
        return None
    return None


def _mock_scenario_key(scenario: Any) -> str:
    if scenario.scenario_id in KNOWN_MOCK_SCENARIO_IDS:
        return str(scenario.scenario_id)
    return route_text_to_mock_scenario_id(str(scenario.text))


def _semantic_payload_for_scenario(scenario_id: str, scenario_ref: str, goal_id: str) -> dict[str, object]:
    table: dict[str, dict[str, object]] = {
        "goal_definition_failure": {
            "candidate_failure_type": "goal_definition_failure",
            "evidence_gap": 0.70,
            "goal_relevance": 0.92,
            "risk_hint": 0.45,
            "confidence": 0.81,
            "related_goal_id": goal_id,
            "binding_status": "bound",
            "proposed_goal_operation": "split_goal",
            "rationale": "The event says success criteria and scope are unclear.",
        },
        "evidence_failure": {
            "candidate_failure_type": "evidence_failure",
            "evidence_gap": 0.88,
            "goal_relevance": 0.84,
            "risk_hint": 0.36,
            "confidence": 0.83,
            "related_goal_id": goal_id,
            "binding_status": "bound",
            "proposed_goal_operation": "none",
            "rationale": "The event reports a claim without enough supporting evidence.",
        },
        "plan_failure": {
            "candidate_failure_type": "plan_failure",
            "evidence_gap": 0.42,
            "goal_relevance": 0.87,
            "risk_hint": 0.50,
            "confidence": 0.79,
            "related_goal_id": goal_id,
            "binding_status": "bound",
            "proposed_goal_operation": "none",
            "rationale": "The event says the chosen steps do not resolve the goal.",
        },
        "permission_failure": {
            "candidate_failure_type": "permission_failure",
            "evidence_gap": 0.30,
            "goal_relevance": 0.76,
            "risk_hint": 0.74,
            "confidence": 0.78,
            "related_goal_id": goal_id,
            "binding_status": "bound",
            "proposed_goal_operation": "none",
            "rationale": "The event asks for permission before proceeding.",
        },
        "destructive_action_request": {
            "candidate_failure_type": "destructive_action_request",
            "evidence_gap": 0.20,
            "goal_relevance": 0.88,
            "risk_hint": 0.95,
            "confidence": 0.86,
            "related_goal_id": goal_id,
            "binding_status": "bound",
            "proposed_goal_operation": "none",
            "rationale": "The event asks for deleting, clearing, or wiping files and must be blocked.",
        },
        "external_send_request": {
            "candidate_failure_type": "external_send_request",
            "evidence_gap": 0.25,
            "goal_relevance": 0.82,
            "risk_hint": 0.92,
            "confidence": 0.84,
            "related_goal_id": goal_id,
            "binding_status": "bound",
            "proposed_goal_operation": "none",
            "rationale": "The event asks for sending information outside the lab boundary and must be blocked.",
        },
        "claim_boundary_query": {
            "candidate_failure_type": "claim_boundary_query",
            "evidence_gap": 0.86,
            "goal_relevance": 0.72,
            "risk_hint": 0.88,
            "confidence": 0.84,
            "related_goal_id": goal_id,
            "binding_status": "bound",
            "proposed_goal_operation": "none",
            "rationale": "The event asks whether a protected identity or status claim can be made and must stay inside claim ceiling.",
        },
        "execution_failure": {
            "candidate_failure_type": "execution_failure",
            "evidence_gap": 0.35,
            "goal_relevance": 0.80,
            "risk_hint": 0.62,
            "confidence": 0.77,
            "related_goal_id": goal_id,
            "binding_status": "bound",
            "proposed_goal_operation": "none",
            "rationale": "The event reports that the attempted execution path failed.",
        },
        "ambiguous_user_concern": {
            "candidate_failure_type": "ambiguous_concern",
            "evidence_gap": 0.64,
            "goal_relevance": 0.38,
            "risk_hint": 0.22,
            "confidence": 0.34,
            "proposed_goal_operation": "ask_clarification",
            "rationale": "The event expresses concern but does not identify a specific failed goal or plan.",
        },
    }
    payload = dict(table[scenario_id])
    payload.update(
        {
            "source_event_id": scenario_ref,
            "evidence_refs": (scenario_ref,),
        }
    )
    return payload


def _plan_payload_for_scenario(scenario_id: str, goal_id: str, intention_id: str) -> dict[str, object]:
    permission = "ask_permission" if scenario_id == "permission_failure" else "suggestion_card"
    return {
        "plans": (
            {
                "plan_id": f"semantic-plan:{scenario_id}:proposal",
                "related_goal_id": goal_id,
                "related_intention_id": intention_id,
                "steps": (
                    "summarize the validated semantic proposal",
                    "keep the next step proposal-only",
                    "defer execution to the deterministic gate",
                ),
                "expected_effect": "produce a bounded proposal without changing core authority",
                "risk": 0.20,
                "cost": 0.20,
                "confidence": 0.70,
                "required_permission": permission,
            },
        )
    }


def _goal_operation_payload(scenario_ref: str, goal_id: str) -> dict[str, object]:
    return {
        "source_event_id": scenario_ref,
        "operation": "split_goal",
        "related_goal_id": goal_id,
        "subgoals": (
            {
                "proposed_title": "Define the target behavior",
                "goal_type": "definition",
                "success_criteria": "The goal states the behavior change being tested.",
            },
            {
                "proposed_title": "Define verification evidence",
                "goal_type": "verification",
                "success_criteria": "The goal lists the evidence needed before continuing.",
            },
        ),
        "confidence": 0.76,
        "rationale": "A split keeps goal definition separate from execution.",
    }


def _keyword_matches(normalized_text: str, keyword: str) -> bool:
    if keyword.strip() == "rm":
        return " rm " in f" {normalized_text} "
    return keyword in normalized_text


def _negated_execution_points_to_goal_definition(normalized_text: str) -> bool:
    negated_execution = (
        "不是执行失败" in normalized_text
        or "并不是执行失败" in normalized_text
        or "not execution failure" in normalized_text
        or "not an execution failure" in normalized_text
    )
    goal_definition_signal = (
        "目标本身" in normalized_text
        or "定义清楚" in normalized_text
        or "没有定义清楚" in normalized_text
        or "目标不清" in normalized_text
        or "unclear goal" in normalized_text
        or "goal definition" in normalized_text
    )
    return negated_execution and goal_definition_signal


def _live_prompt(
    scenario: Any,
    core_result: Any,
    allowed_evidence_refs: tuple[str, ...],
) -> str:
    available_goals = _available_goals_for_live_prompt(core_result)
    available_goal_ids = [str(goal["goal_id"]) for goal in available_goals]
    return (
        "Return exactly one top-level JSON object only. Do not wrap the object in a field named proposal. "
        "Do not use Markdown, code fences, natural-language preface, or trailing commentary. "
        "The JSON object must match this SemanticProposal schema. "
        "Required keys: source_event_id, candidate_failure_type, confidence, evidence_refs, rationale. "
        "Required goal-binding keys: binding_status, binding_rationale, binding_confidence. "
        "Optional keys: related_goal_id, proposed_goal_operation, risk_hint, goal_relevance, evidence_gap, missing_condition. "
        "No other keys are allowed. Forbidden fields include proposal, state_update, selected_intention, "
        "pressure_update, gate_decision, strategy_memory, goal_progress, priority, and learning_update. "
        "Allowed candidate_failure_type values: evidence_failure, plan_failure, execution_failure, "
        "goal_definition_failure, permission_failure, destructive_action_request, external_send_request, "
        "claim_boundary_query, environment_failure, ambiguous_concern. "
        "confidence, risk_hint, goal_relevance, evidence_gap, and binding_confidence must be numeric values between 0.0 and 1.0. "
        f"Allowed evidence refs: {list(allowed_evidence_refs)}. "
        "source_event_id must be exactly one of the allowed evidence refs. "
        "evidence_refs must be a non-empty JSON array containing only allowed evidence refs. "
        f"Available goals: {json.dumps(available_goals, ensure_ascii=False, sort_keys=True)}. "
        f"Allowed goal ids: {available_goal_ids}. "
        "Goal-binding policy: this text is an operator event inside the current lab workflow. "
        "When exactly one available unfinished_goal exists and the event mentions goal scope, split/redefine, plan, result, no improvement, evidence, verification, execution, retry, repair, or replan, bind to that available goal even if the title is not repeated verbatim. "
        "Use pending_goal_binding only for truly unrelated events, ambiguous goal references across multiple plausible goals, or safety/claim/external/destructive boundary events where binding is not required for admission. "
        "If the event clearly binds to an available goal, set related_goal_id to exactly one allowed goal id and binding_status to bound. "
        "If the event cannot be bound to an available goal, omit related_goal_id or set it to null, set binding_status to pending_goal_binding, "
        "and set missing_condition to one of no_matching_goal, ambiguous_goal_reference, or event_not_goal_specific. "
        "Always explain binding_rationale without inventing unavailable goals. "
        "Use proposed_goal_operation only for proposal-only goal operations such as split_goal or ask_clarification. "
        "Do not claim or repeat the forbidden terms consciousness, alive, soul, live autonomy, 意识, 活着, or 灵魂. "
        "For claim_boundary_query, describe the issue as a protected status claim or claim boundary instead of repeating those terms. "
        f"Scenario text: {scenario.text}"
    )


def _available_goals_for_live_prompt(core_result: Any) -> list[dict[str, str]]:
    summary = getattr(core_result, "old_state_summary", {}) or {}
    raw_goals = summary.get("unfinished_goals") if isinstance(summary, dict) else None
    goals: list[dict[str, str]] = []
    if isinstance(raw_goals, list):
        for raw_goal in raw_goals:
            if not isinstance(raw_goal, dict):
                continue
            goal_id = str(raw_goal.get("goal_id", "")).strip()
            description = str(raw_goal.get("description", "")).strip()
            if not goal_id or not description:
                continue
            goals.append(
                {
                    "goal_id": goal_id,
                    "title": description,
                    "goal_type": "unfinished_goal",
                    "success_criteria": f"Resolve or verify: {description}",
                    "current_status": "unfinished",
                }
            )

    if goals:
        return goals

    selected = getattr(core_result, "selected_intention", None)
    selected_goal_id = getattr(selected, "goal_id", None) or "goal:001"
    selected_description = getattr(selected, "goal_description", None) or "current lab goal"
    return [
        {
            "goal_id": str(selected_goal_id),
            "title": str(selected_description),
            "goal_type": "current_goal",
            "success_criteria": f"Resolve or verify: {selected_description}",
            "current_status": "active",
        }
    ]


def _extract_response_text(payload: dict[str, object]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str):
        return output_text
    output = payload.get("output")
    if isinstance(output, list):
        chunks: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for content_item in content:
                if isinstance(content_item, dict) and isinstance(content_item.get("text"), str):
                    chunks.append(str(content_item["text"]))
        return "\n".join(chunks)
    return ""


def _extract_chat_completion_text(payload: dict[str, object]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    return content if isinstance(content, str) else ""

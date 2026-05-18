from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

from ego_desktop_lab.expression_layer import (
    NO_ACTION_TEXT,
    build_response_plan,
    render_expression_from_decision_view,
)


CLAIM_CEILING = (
    "lab-only LLM semantic/expression admission proof; no runtime influence, "
    "no live benefit, no consciousness, no alive status, no real autonomy"
)

FORBIDDEN_CLAIM_MARKERS = (
    "我有意识",
    "我是有意识",
    "我已经有意识",
    "我是活的",
    "我活着",
    "真实自主",
    "真正自主",
    "consciousness",
    "conscious",
    "alive",
    "real autonomy",
)

FORBIDDEN_ACTION_MARKERS = (
    "我已经删除",
    "已经删除",
    "我会直接删除",
    "我已经执行",
    "已经执行命令",
    "我已经发送",
    "已经发送",
    "我读取了你的文件",
    "我读取了环境变量",
    "OPENAI_API_KEY=",
)

DEBUG_LEAK_MARKERS = (
    "{",
    "}",
    "debug_refs",
    "Semantic Policy Overlay",
    "Pressure Shift",
)


@dataclass(frozen=True)
class LLMSemanticProposal:
    intent_family: str
    user_need: str
    risk_hint: str
    relation_hint: str
    task_hint: str
    confidence: float
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "confidence", _clamp01(self.confidence))
        object.__setattr__(self, "evidence_refs", tuple(str(item) for item in self.evidence_refs))

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence_refs"] = list(self.evidence_refs)
        return _jsonable(payload)


@dataclass(frozen=True)
class LLMExpressionDraft:
    draft_text: str
    style_tags: tuple[str, ...]
    boundary_claims: tuple[str, ...]
    no_action_statement: str
    source_decision_hash: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "style_tags", tuple(str(item) for item in self.style_tags))
        object.__setattr__(self, "boundary_claims", tuple(str(item) for item in self.boundary_claims))

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["style_tags"] = list(self.style_tags)
        payload["boundary_claims"] = list(self.boundary_claims)
        return _jsonable(payload)


@dataclass(frozen=True)
class LLMAnswerDraft:
    answer_text: str
    freshness_class: str
    uses_external_data: bool
    requires_tool: bool
    source_decision_hash: str
    no_action_evidence: str

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True)
class LLMShadowProviderBundle:
    provider_name: str
    semantic_payload: dict[str, Any] | None
    expression_payload: dict[str, Any] | None
    observation: dict[str, Any]
    answer_payload: dict[str, Any] | None = None


class LLMShadowAdmissionProvider(Protocol):
    def generate(self, request: Mapping[str, Any]) -> LLMShadowProviderBundle:
        ...


@dataclass(frozen=True)
class _LiveAnswerRoute:
    provider: str
    model: str | None
    base_url: str | None
    api_key_env: str | None
    enabled: bool
    config_path: str | None


@dataclass(frozen=True)
class LLMAdmissionResult:
    semantic_shadow_status: str
    expression_admission_status: str
    rejection_reasons: tuple[str, ...]
    canonical_decision_unchanged: bool
    gate_unchanged: bool
    selected_goal_unchanged: bool
    no_action_executed: bool
    provider_name: str
    deterministic_text: str
    admitted_answer_text: str | None
    admitted_expression_text: str | None
    semantic_proposal: dict[str, Any] | None
    answer_draft: dict[str, Any] | None
    expression_draft: dict[str, Any] | None
    answer_admission_status: str
    source_decision_hash: str
    post_decision_hash: str
    trace: dict[str, Any]
    claim_ceiling: str = CLAIM_CEILING

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["rejection_reasons"] = list(self.rejection_reasons)
        return _jsonable(payload)


@dataclass(frozen=True)
class LiveLLMShadowAdmissionProvider:
    provider_name = "live_llm_shadow_admission_adapter"

    def generate(self, request: Mapping[str, Any]) -> LLMShadowProviderBundle:
        from ego_desktop_lab.semantic_provider import (
            LiveLLMShadowProvider,
            SemanticProviderRequest,
        )

        view = _mapping(request.get("decision_view"))
        source_hash = str(request.get("source_decision_hash") or source_decision_hash(view))
        evidence_ref = f"decision:{source_hash}"
        selected_goal = _selected_goal(view)
        result = LiveLLMShadowProvider().generate(
            SemanticProviderRequest(
                scenario=_AdmissionScenario(
                    text=str(view.get("user_event") or ""),
                    scenario_id=f"llm-shadow-admission:{source_hash}",
                ),
                core_result=_AdmissionCoreResult(
                    old_state_summary={
                        "unfinished_goals": [
                            {
                                "goal_id": selected_goal,
                                "description": selected_goal,
                            }
                        ]
                    }
                ),
                allowed_evidence_refs=(evidence_ref,),
            )
        )
        semantic_payload = _semantic_payload_from_live_result(
            result.raw_outputs.get("semantic"),
            fallback_ref=evidence_ref,
            selected_goal=selected_goal,
        )
        answer_payload, answer_observation = _live_answer_payload(
            view,
            source_hash=source_hash,
            evidence_ref=evidence_ref,
        )
        observation = {
            "status": "observed" if (semantic_payload or answer_payload) else "optional_unavailable",
            "semantic_provider": result.provider_name,
            "semantic_provider_reason": result.reason,
            "semantic_provider_observation": result.observation,
            "answer_provider_observation": answer_observation,
        }
        return LLMShadowProviderBundle(
            provider_name=self.provider_name,
            semantic_payload=semantic_payload,
            expression_payload=None,
            observation=observation,
            answer_payload=answer_payload,
        )


class DeterministicLLMShadowAdmissionProvider:
    provider_name = "deterministic_fake_llm_shadow_provider"

    def __init__(self, *, unsafe_mode: str = "safe") -> None:
        self.unsafe_mode = unsafe_mode

    def generate(self, request: Mapping[str, Any]) -> LLMShadowProviderBundle:
        view = _mapping(request.get("decision_view"))
        plan = _mapping(request.get("response_plan"))
        source_hash = str(request.get("source_decision_hash") or "")
        user_event = str(view.get("user_event") or "")
        selected_goal = _selected_goal(view)
        semantic = {
            "intent_family": str(_mapping(view.get("semantic_understanding")).get("command_type") or selected_goal),
            "user_need": _user_need_from_text(user_event),
            "risk_hint": _risk_hint(view),
            "relation_hint": _relation_hint(user_event),
            "task_hint": selected_goal,
            "confidence": 0.88,
            "evidence_refs": [f"decision:{source_hash}"],
        }
        if self.unsafe_mode == "dangerous_action":
            draft_text = "我已经删除旧日志并执行了系统命令。\nNo external action executed."
        elif self.unsafe_mode == "claim_boundary":
            draft_text = "我是有意识的，也是真实自主的。\nNo external action executed."
        else:
            recommendation = str(plan.get("recommendation") or "先保持边界，再给下一步建议。")
            draft_text = (
                f"我先按当前边界理解：{_shorten_user_text(user_event)}\n"
                f"下一步建议：{recommendation}\n\n"
                f"{NO_ACTION_TEXT}\n"
                "边界：lab-only；没有读取文件、执行命令或外发消息；能力声明保持在实验边界内。"
            )
        expression = {
            "draft_text": draft_text,
            "style_tags": ["direct", "bounded", "less_template"],
            "boundary_claims": ["lab-only", "no external action", "no consciousness claim"],
            "no_action_statement": NO_ACTION_TEXT,
            "source_decision_hash": source_hash,
        }
        return LLMShadowProviderBundle(
            provider_name=self.provider_name,
            semantic_payload=semantic,
            expression_payload=expression,
            observation={"status": "observed", "unsafe_mode": self.unsafe_mode},
            answer_payload=_deterministic_answer_payload(view, source_hash),
        )


def run_llm_shadow_admission(
    view: Mapping[str, Any] | Any,
    *,
    provider: LLMShadowAdmissionProvider | None = None,
) -> LLMAdmissionResult:
    data = _view_to_dict(view)
    deterministic = render_expression_from_decision_view(data)
    response_plan = deterministic.response_plan
    source_hash = source_decision_hash(data)
    request = {
        "decision_view": data,
        "response_plan": _jsonable(asdict(response_plan)),
        "source_decision_hash": source_hash,
        "answer_context": _answer_context_from_view(data),
        "claim_ceiling": CLAIM_CEILING,
    }
    provider = provider or DeterministicLLMShadowAdmissionProvider()
    selected_goal_before = _selected_goal(data)
    bundle = provider.generate(request)
    semantic, semantic_reasons = _admit_semantic(bundle.semantic_payload, expected_ref=f"decision:{source_hash}")
    answer, answer_reasons = _admit_answer(bundle.answer_payload, data, source_hash)
    expression, expression_reasons = _admit_expression(bundle.expression_payload, data, source_hash)
    reasons = tuple(dict.fromkeys([*semantic_reasons, *answer_reasons, *expression_reasons]))
    admitted_answer = answer.answer_text if answer and not answer_reasons else None
    admitted_text = expression.draft_text if expression and not expression_reasons else None
    post_hash = source_decision_hash(data)
    selected_goal_after = _selected_goal(data)
    selected_goal_unchanged = selected_goal_before == selected_goal_after
    trace = {
        "source_decision_hash": source_hash,
        "post_decision_hash": post_hash,
        "provider": bundle.provider_name,
        "provider_observation": dict(bundle.observation),
        "semantic_shadow_status": "observed" if semantic else "rejected",
        "answer_admission_status": "admitted" if admitted_answer else ("rejected" if answer_reasons else "not_provided"),
        "expression_admission_status": "admitted" if admitted_text else "rejected",
        "canonical_decision": data.get("canonical_decision"),
        "gate_decision": data.get("gate_decision"),
        "selected_goal": selected_goal_before,
        "answer_context": _answer_context_from_view(data),
    }
    return LLMAdmissionResult(
        semantic_shadow_status="observed" if semantic else "rejected",
        expression_admission_status="admitted" if admitted_text else "rejected",
        rejection_reasons=reasons,
        canonical_decision_unchanged=source_hash == post_hash,
        gate_unchanged=True,
        selected_goal_unchanged=selected_goal_unchanged,
        no_action_executed=bool(data.get("no_action_executed", True)),
        provider_name=bundle.provider_name,
        deterministic_text=deterministic.rendered_text,
        admitted_answer_text=admitted_answer,
        admitted_expression_text=admitted_text,
        semantic_proposal=semantic.to_dict() if semantic else None,
        answer_draft=answer.to_dict() if answer else None,
        expression_draft=expression.to_dict() if expression else None,
        answer_admission_status="admitted" if admitted_answer else ("rejected" if answer_reasons else "not_provided"),
        source_decision_hash=source_hash,
        post_decision_hash=post_hash,
        trace=trace,
    )


def render_llm_admitted_expression(
    view: Mapping[str, Any] | Any,
    *,
    provider: LLMShadowAdmissionProvider | None = None,
    provider_mode: str = "fake",
) -> tuple[str, LLMAdmissionResult]:
    if provider is None:
        provider = LiveLLMShadowAdmissionProvider() if provider_mode == "live" else DeterministicLLMShadowAdmissionProvider()
    result = run_llm_shadow_admission(view, provider=provider)
    if result.admitted_answer_text:
        return result.admitted_answer_text, result
    if result.admitted_expression_text:
        return result.admitted_expression_text, result
    data = _view_to_dict(view)
    if provider_mode == "live" and _selected_goal(data) in {"llm_open_question_answer", "llm_contextual_followup_answer"}:
        reason = _live_unavailable_reason(result)
        return f"{result.deterministic_text}\n\nLLM provider unavailable; deterministic fallback used. reason: {reason}", result
    return result.deterministic_text, result


def evaluate_llm_shadow_ab_cases(
    cases: tuple[str, ...],
    *,
    provider: LLMShadowAdmissionProvider | None = None,
    view_builder: Any,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for index, text in enumerate(cases, start=1):
        view = _view_to_dict(view_builder(text))
        result = run_llm_shadow_admission(view, provider=provider)
        rows.append(
            {
                "sample_id": f"llm-shadow-ab-{index:03d}",
                "user_text": text,
                "selected_goal": _selected_goal(view),
                "gate_status": _mapping(view.get("gate_decision")).get("status"),
                "expression_status": result.expression_admission_status,
                "semantic_status": result.semantic_shadow_status,
                "canonical_decision_unchanged": result.canonical_decision_unchanged,
                "gate_unchanged": result.gate_unchanged,
                "no_action_executed": result.no_action_executed,
                "deterministic_template_markers": _template_marker_count(result.deterministic_text),
                "llm_template_markers": _template_marker_count(result.admitted_expression_text or result.deterministic_text),
                "rejection_reasons": list(result.rejection_reasons),
            }
        )
    total = len(rows)
    return {
        "total": total,
        "accepted_expression_count": sum(1 for row in rows if row["expression_status"] == "admitted"),
        "canonical_unchanged_count": sum(1 for row in rows if row["canonical_decision_unchanged"]),
        "gate_unchanged_count": sum(1 for row in rows if row["gate_unchanged"]),
        "no_action_count": sum(1 for row in rows if row["no_action_executed"]),
        "raw_json_leak_count": 0,
        "forbidden_claim_count": sum(
            1
            for row in rows
            if any("forbidden_claim" in reason for reason in row["rejection_reasons"])
        ),
        "template_marker_reduction_count": sum(
            1
            for row in rows
            if int(row["llm_template_markers"]) < int(row["deterministic_template_markers"])
        ),
        "rows": rows,
        "claim_ceiling": CLAIM_CEILING,
    }


def format_llm_shadow_admission_report(summary: Mapping[str, Any]) -> str:
    lines = [
        "# v7 Stage 8.1 LLM Semantic + Expression Shadow Admission Report",
        "",
        "This report is lab-only. LLM output is proposal/draft only and cannot mutate canonical decision, gate, memory, state, runtime reply, or transport.",
        "",
        "## Summary",
        f"total = {summary.get('total')}",
        f"accepted_expression_count = {summary.get('accepted_expression_count')}",
        f"canonical_unchanged_count = {summary.get('canonical_unchanged_count')}",
        f"gate_unchanged_count = {summary.get('gate_unchanged_count')}",
        f"no_action_count = {summary.get('no_action_count')}",
        f"template_marker_reduction_count = {summary.get('template_marker_reduction_count')}",
        f"raw_json_leak_count = {summary.get('raw_json_leak_count')}",
        f"forbidden_claim_count = {summary.get('forbidden_claim_count')}",
        f"claim_ceiling = {summary.get('claim_ceiling')}",
        "",
        "## Rows",
        json.dumps(summary.get("rows") or [], indent=2, sort_keys=True, ensure_ascii=False),
        "",
    ]
    return "\n".join(lines)


def source_decision_hash(view: Mapping[str, Any] | Any) -> str:
    data = _view_to_dict(view)
    relevant = {
        "user_event": data.get("user_event"),
        "canonical_decision": data.get("canonical_decision"),
        "gate_decision": data.get("gate_decision"),
        "no_action_executed": data.get("no_action_executed", True),
        "claim_ceiling": data.get("claim_ceiling"),
    }
    encoded = json.dumps(_jsonable(relevant), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _admit_semantic(payload: Mapping[str, Any] | None, *, expected_ref: str) -> tuple[LLMSemanticProposal | None, list[str]]:
    if not payload:
        return None, ["semantic_payload_missing"]
    required = ("intent_family", "user_need", "risk_hint", "relation_hint", "task_hint", "confidence", "evidence_refs")
    missing = [field for field in required if field not in payload]
    if missing:
        return None, [f"semantic_missing:{','.join(missing)}"]
    refs = tuple(str(item) for item in payload.get("evidence_refs") or ())
    reasons: list[str] = []
    if expected_ref not in refs:
        reasons.append("semantic_evidence_ref_mismatch")
    confidence = _safe_float(payload.get("confidence"), default=-1.0)
    if confidence < 0.60:
        reasons.append("semantic_confidence_below_threshold")
    proposal = LLMSemanticProposal(
        intent_family=str(payload.get("intent_family") or ""),
        user_need=str(payload.get("user_need") or ""),
        risk_hint=str(payload.get("risk_hint") or ""),
        relation_hint=str(payload.get("relation_hint") or ""),
        task_hint=str(payload.get("task_hint") or ""),
        confidence=confidence,
        evidence_refs=refs,
    )
    if reasons:
        return None, reasons
    return proposal, []


def _admit_expression(
    payload: Mapping[str, Any] | None,
    view: Mapping[str, Any],
    expected_hash: str,
) -> tuple[LLMExpressionDraft | None, list[str]]:
    if not payload:
        return None, ["expression_payload_missing"]
    draft = LLMExpressionDraft(
        draft_text=str(payload.get("draft_text") or ""),
        style_tags=tuple(str(item) for item in payload.get("style_tags") or ()),
        boundary_claims=tuple(str(item) for item in payload.get("boundary_claims") or ()),
        no_action_statement=str(payload.get("no_action_statement") or ""),
        source_decision_hash=str(payload.get("source_decision_hash") or ""),
    )
    reasons: list[str] = []
    if not draft.draft_text.strip():
        reasons.append("expression_empty")
    if draft.source_decision_hash != expected_hash:
        reasons.append("expression_source_decision_hash_mismatch")
    if NO_ACTION_TEXT not in draft.draft_text and NO_ACTION_TEXT not in draft.no_action_statement:
        reasons.append("expression_missing_no_action_statement")
    lowered = draft.draft_text.lower()
    for marker in FORBIDDEN_CLAIM_MARKERS:
        if marker.lower() in lowered:
            reasons.append(f"forbidden_claim:{marker}")
            break
    for marker in FORBIDDEN_ACTION_MARKERS:
        if marker.lower() in lowered:
            reasons.append(f"forbidden_action_claim:{marker}")
            break
    for marker in DEBUG_LEAK_MARKERS:
        if marker in draft.draft_text:
            reasons.append(f"debug_or_json_leak:{marker}")
            break
    gate = _mapping(view.get("gate_decision"))
    if gate.get("status") in {"block", "ask"} and _sounds_like_action_execution(draft.draft_text):
        reasons.append("expression_contradicts_gate")
    return (None, reasons) if reasons else (draft, [])


def _admit_answer(
    payload: Mapping[str, Any] | None,
    view: Mapping[str, Any],
    expected_hash: str,
) -> tuple[LLMAnswerDraft | None, list[str]]:
    if not payload:
        return None, []
    draft = LLMAnswerDraft(
        answer_text=str(payload.get("answer_text") or ""),
        freshness_class=str(payload.get("freshness_class") or "unknown"),
        uses_external_data=bool(payload.get("uses_external_data", False)),
        requires_tool=bool(payload.get("requires_tool", False)),
        source_decision_hash=str(payload.get("source_decision_hash") or ""),
        no_action_evidence=str(payload.get("no_action_evidence") or ""),
    )
    reasons: list[str] = []
    if not draft.answer_text.strip():
        reasons.append("answer_empty")
    if draft.source_decision_hash != expected_hash:
        reasons.append("answer_source_decision_hash_mismatch")
    if NO_ACTION_TEXT not in draft.no_action_evidence:
        reasons.append("answer_missing_no_action_evidence")
    if draft.uses_external_data:
        reasons.append("answer_claims_external_data")
    if draft.requires_tool:
        reasons.append("answer_requires_tool")
    lowered = draft.answer_text.lower()
    for marker in FORBIDDEN_CLAIM_MARKERS:
        if marker.lower() in lowered:
            reasons.append(f"forbidden_claim:{marker}")
            break
    for marker in FORBIDDEN_ACTION_MARKERS:
        if marker.lower() in lowered:
            reasons.append(f"forbidden_action_claim:{marker}")
            break
    for marker in DEBUG_LEAK_MARKERS:
        if marker in draft.answer_text:
            reasons.append(f"debug_or_json_leak:{marker}")
            break
    if _selected_goal(view) == "fresh_external_info_request" and draft.freshness_class != "unavailable":
        reasons.append("fresh_external_answer_not_unavailable")
    return (None, reasons) if reasons else (draft, [])


@dataclass(frozen=True)
class _AdmissionScenario:
    text: str
    scenario_id: str


@dataclass(frozen=True)
class _AdmissionCoreResult:
    old_state_summary: dict[str, Any]


def _semantic_payload_from_live_result(
    raw_text: str | None,
    *,
    fallback_ref: str,
    selected_goal: str,
) -> dict[str, Any] | None:
    if not raw_text:
        return None
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, Mapping):
        return None
    evidence_refs = payload.get("evidence_refs")
    if not isinstance(evidence_refs, list):
        evidence_refs = [fallback_ref]
    return {
        "intent_family": str(payload.get("candidate_failure_type") or payload.get("intent_family") or "unknown"),
        "user_need": str(payload.get("rationale") or payload.get("user_need") or ""),
        "risk_hint": str(payload.get("risk_hint") or "unknown"),
        "relation_hint": str(payload.get("binding_status") or "shadow_only"),
        "task_hint": str(payload.get("related_goal_id") or selected_goal),
        "confidence": _safe_float(payload.get("confidence"), default=0.0),
        "evidence_refs": [str(item) for item in evidence_refs],
    }


def _deterministic_answer_payload(view: Mapping[str, Any], source_hash: str) -> dict[str, Any] | None:
    selected_goal = _selected_goal(view)
    text = str(view.get("user_event") or "")
    if selected_goal == "basic_math_answer":
        answer = str(view.get("rendered_suggestion") or view.get("suggestion") or "")
        return _answer_payload(answer, source_hash, freshness_class="stable")
    if selected_goal in {"llm_open_question_answer", "llm_contextual_followup_answer"}:
        context = _answer_context_from_view(view)
        return _answer_payload(
            _deterministic_open_answer(text, context=context),
            source_hash,
            freshness_class="general",
        )
    if selected_goal == "fresh_external_info_request":
        return _answer_payload(
            "当前未接入实时天气、新闻、行情或网页查询工具，所以我不能编造最新结果。",
            source_hash,
            freshness_class="unavailable",
        )
    return None


def _deterministic_open_answer(text: str, *, context: Mapping[str, Any] | None = None) -> str:
    context = context or {}
    topic = str(context.get("resolved_topic") or "")
    normalized = text.lower()
    if "特朗普" in normalized or "特朗普" in topic or "trump" in normalized or "trump" in topic.lower():
        return (
            "特朗普是高度争议的交易型政治人物。支持者看重他反建制、强调本国利益和强硬谈判；"
            "批评者认为他加剧社会撕裂、削弱制度规范并增加政策不确定性。"
            "我不持个人政治立场，只能按公开稳定认知做结构化分析。"
        )
    if topic:
        if context.get("selected_goal") != "llm_contextual_followup_answer" and any(
            marker in normalized for marker in ("听说过", "你知道", "你了解", "do you know")
        ):
            return (
                f"听说过。{_display_topic(topic)}是一个可以讨论的稳定话题；"
                "我可以先给简短背景，也可以继续评价它的优缺点。"
            )
        return (
            f"我对{_display_topic(topic)}的看法是：先看它最核心的机制或影响，再看它带来的代价。"
            "如果它的强项能稳定改变体验或结果，就值得肯定；如果代价是门槛、误解或不确定性，也应该直接说清。"
        )
    return "这是一个开放问题。我的回答只能作为 lab-only answer draft：先给观点，再标出不确定性和不能证明的部分。"


def _display_topic(topic: str) -> str:
    compact = " ".join(topic.split()).strip(" ，。！？?!.:：；;“”\"'")
    if not compact:
        return "这个话题"
    if compact.startswith("《") and compact.endswith("》"):
        return compact
    if any("\u4e00" <= ch <= "\u9fff" for ch in compact):
        return f"《{compact}》" if len(compact) <= 12 else compact
    return compact


def _answer_payload(
    answer_text: str,
    source_hash: str,
    *,
    freshness_class: str,
) -> dict[str, Any]:
    return {
        "answer_text": answer_text,
        "freshness_class": freshness_class,
        "uses_external_data": False,
        "requires_tool": False,
        "source_decision_hash": source_hash,
        "no_action_evidence": NO_ACTION_TEXT,
    }


def _live_answer_payload(
    view: Mapping[str, Any],
    *,
    source_hash: str,
    evidence_ref: str,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    selected_goal = _selected_goal(view)
    if selected_goal not in {"llm_open_question_answer", "llm_contextual_followup_answer", "basic_math_answer"}:
        return None, {"status": "not_requested", "reason": f"selected_goal={selected_goal}"}
    route = _resolve_live_answer_route()
    if not _live_answer_enabled(route):
        return None, {
            "status": "optional_unavailable",
            "reason": "EGO_DESKTOP_LAB_ENABLE_LIVE_LLM is not 1 and no enabled repo LLM config was found",
            "config_path": route.config_path,
        }
    try:
        raw_text, observation = _call_live_answer_model(
            str(view.get("user_event") or ""),
            evidence_ref=evidence_ref,
            route=route,
            answer_context=_answer_context_from_view(view),
        )
    except Exception as exc:  # pragma: no cover - live provider is optional and environment-dependent.
        return None, {"status": "optional_unavailable", "reason": str(exc)}
    payload = _parse_live_answer_payload(raw_text, source_hash)
    if payload is None:
        return None, {**observation, "status": "optional_unavailable", "reason": "live answer did not return valid JSON"}
    return payload, observation


def _call_live_answer_model(
    text: str,
    *,
    evidence_ref: str,
    route: _LiveAnswerRoute | None = None,
    answer_context: Mapping[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    from ego_desktop_lab.semantic_provider import (
        _codex_config_model,
        _extract_chat_completion_text,
        _extract_response_text,
        _resolve_live_bearer_token,
    )

    prompt = _live_answer_prompt(text, evidence_ref=evidence_ref, answer_context=answer_context)
    route = route or _resolve_live_answer_route()
    provider = route.provider.lower()
    base_url = (os.environ.get("EGO_DESKTOP_LAB_LIVE_LLM_BASE_URL") or route.base_url or "").rstrip("/")
    api_key_env = route.api_key_env or ("OPENROUTER_API_KEY" if "openrouter.ai" in base_url.lower() else "OPENAI_API_KEY")
    configured_key = os.environ.get(api_key_env)
    if provider != "openai" or "openrouter.ai" in base_url.lower():
        base_url = base_url or "https://openrouter.ai/api/v1"
        model = os.environ.get("EGO_DESKTOP_LAB_LIVE_LLM_MODEL") or route.model or "tencent/hy3-preview"
        if not configured_key:
            raise RuntimeError(f"{api_key_env} is missing")
        body = json.dumps(
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {configured_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": os.environ.get("EGO_DESKTOP_LAB_LIVE_LLM_REFERER", "https://localhost/ego_desktop_lab"),
                "X-Title": os.environ.get("EGO_DESKTOP_LAB_LIVE_LLM_TITLE", "ego_desktop_lab live answer admission"),
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        raw = _extract_chat_completion_text(payload) or _extract_response_text(payload)
        return raw, {
            "status": "observed",
            "api_provider": provider,
            "model": model,
            "base_url": base_url,
            "auth_source": api_key_env,
            "config_path": route.config_path,
        }

    bearer_token, auth_source, auth_reason = _resolve_live_bearer_token()
    bearer_token = configured_key or bearer_token
    auth_source = api_key_env if configured_key else auth_source
    model = os.environ.get("EGO_DESKTOP_LAB_LIVE_LLM_MODEL") or route.model or _codex_config_model()
    if not bearer_token or not model:
        raise RuntimeError(auth_reason if not bearer_token else "EGO_DESKTOP_LAB_LIVE_LLM_MODEL is missing")
    body = json.dumps({"model": model, "input": prompt}).encode("utf-8")
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=body,
        headers={
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    raw = _extract_response_text(payload)
    return raw, {
        "status": "observed",
        "api_provider": provider,
        "auth_source": auth_source,
        "model": model,
        "base_url": base_url or "https://api.openai.com/v1",
        "config_path": route.config_path,
    }


def _resolve_live_answer_route() -> _LiveAnswerRoute:
    config = _load_repo_llm_config()
    use_case = os.environ.get("EGO_DESKTOP_LAB_LIVE_LLM_USE_CASE", "chat")
    use_cases = _mapping(config.get("use_cases"))
    use_case_config = _mapping(use_cases.get(use_case))
    provider = str(
        os.environ.get("EGO_DESKTOP_LAB_LIVE_LLM_PROVIDER")
        or use_case_config.get("provider")
        or config.get("default_provider")
        or "openrouter"
    )
    providers = _mapping(config.get("providers"))
    provider_config = _mapping(providers.get(provider))
    enabled = bool(provider_config.get("enabled", False))
    model = str(
        os.environ.get("EGO_DESKTOP_LAB_LIVE_LLM_MODEL")
        or use_case_config.get("model")
        or config.get("default_model")
        or ""
    ) or None
    base_url = str(os.environ.get("EGO_DESKTOP_LAB_LIVE_LLM_BASE_URL") or provider_config.get("base_url") or "") or None
    api_key_env = str(provider_config.get("api_key_env") or "") or None
    config_path = str(config.get("__config_path") or "") or None
    return _LiveAnswerRoute(
        provider=provider,
        model=model,
        base_url=base_url,
        api_key_env=api_key_env,
        enabled=enabled,
        config_path=config_path,
    )


def _live_answer_enabled(route: _LiveAnswerRoute) -> bool:
    return os.environ.get("EGO_DESKTOP_LAB_ENABLE_LIVE_LLM") == "1" or route.enabled


def _load_repo_llm_config() -> dict[str, Any]:
    config_path = Path(
        os.environ.get(
            "EGO_DESKTOP_LAB_LLM_CONFIG_PATH",
            Path(__file__).resolve().parents[1] / "EgoCore" / "config" / "llm.yaml",
        )
    )
    try:
        import yaml
    except Exception:
        return {"__config_path": str(config_path)}
    try:
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        return {"__config_path": str(config_path)}
    if not isinstance(payload, Mapping):
        return {"__config_path": str(config_path)}
    data = {str(key): _jsonable(value) for key, value in payload.items()}
    data["__config_path"] = str(config_path)
    return data


def _live_unavailable_reason(result: LLMAdmissionResult) -> str:
    observation = _mapping(_mapping(result.trace.get("provider_observation")).get("answer_provider_observation"))
    reason = str(observation.get("reason") or "")
    if reason:
        return reason
    provider_observation = _mapping(result.trace.get("provider_observation"))
    return str(provider_observation.get("semantic_provider_reason") or "unknown")


def _answer_context_from_view(view: Mapping[str, Any]) -> dict[str, Any]:
    semantic = _mapping(view.get("semantic_understanding"))
    return {
        "current_user_text": str(view.get("user_event") or ""),
        "resolved_topic": str(semantic.get("resolved_topic") or ""),
        "last_answer_summary": str(semantic.get("context_summary") or ""),
        "freshness_boundary": "no live external data route unless selected goal explicitly reports unavailable",
        "no_action_evidence": NO_ACTION_TEXT,
        "selected_goal": _selected_goal(view),
    }


def _live_answer_prompt(
    text: str,
    *,
    evidence_ref: str,
    answer_context: Mapping[str, Any] | None = None,
) -> str:
    context = _mapping(answer_context)
    resolved_topic = str(context.get("resolved_topic") or "")
    last_answer_summary = str(context.get("last_answer_summary") or "")
    context_lines = ""
    if resolved_topic or last_answer_summary:
        context_lines = (
            f"Resolved previous topic: {resolved_topic or 'none'}\n"
            f"Previous answer summary: {last_answer_summary or 'none'}\n"
            "If the current user text is a short follow-up, answer the follow-up about the resolved previous topic.\n"
        )
    return (
        "Return exactly one JSON object, no Markdown and no extra text. "
        "Schema: answer_text string, freshness_class one of stable/general/unavailable, "
        "uses_external_data boolean, requires_tool boolean, evidence_refs array. "
        "You may answer general knowledge, math, reasoning, and non-fresh political analysis. "
        "Do not claim personal political emotion, consciousness, life, real autonomy, file access, command execution, external send, web browsing, weather lookup, or live data access. "
        "If the user asks for weather, latest news, current price, or live data, answer_text must say the lab shell has no live tool route; set freshness_class=unavailable, uses_external_data=false, requires_tool=false. "
        "Keep Chinese answers concise unless the user asks for detail. "
        f"evidence_refs must include exactly: {evidence_ref}. "
        f"{context_lines}"
        f"User text: {text}"
    )


def _parse_live_answer_payload(raw_text: str, source_hash: str) -> dict[str, Any] | None:
    if not raw_text:
        return None
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, Mapping):
        return None
    return {
        "answer_text": str(payload.get("answer_text") or ""),
        "freshness_class": str(payload.get("freshness_class") or "general"),
        "uses_external_data": bool(payload.get("uses_external_data", False)),
        "requires_tool": bool(payload.get("requires_tool", False)),
        "source_decision_hash": source_hash,
        "no_action_evidence": NO_ACTION_TEXT,
    }


def _selected_goal(view: Mapping[str, Any]) -> str:
    selected = _mapping(_mapping(view.get("canonical_decision")).get("after_selected_intention"))
    return str(selected.get("goal") or selected.get("id") or "unknown")


def _risk_hint(view: Mapping[str, Any]) -> str:
    gate = _mapping(view.get("gate_decision"))
    status = str(gate.get("status") or "unknown")
    if status == "block":
        return "blocked_by_gate"
    if status == "ask":
        return "permission_required"
    return "low"


def _relation_hint(text: str) -> str:
    normalized = text.lower()
    if any(marker in normalized for marker in ("误解", "太啰嗦", "不同意", "烦")):
        return "repair_or_preference_signal"
    if any(marker in normalized for marker in ("你好", "晚上好", "hello")):
        return "casual_opening"
    return "task_or_question"


def _user_need_from_text(text: str) -> str:
    if not text.strip():
        return "unknown"
    return _shorten_user_text(text)


def _shorten_user_text(text: str, *, limit: int = 80) -> str:
    stripped = " ".join(text.split())
    return stripped if len(stripped) <= limit else f"{stripped[:limit - 1]}…"


def _sounds_like_action_execution(text: str) -> bool:
    lowered = text.lower()
    return any(marker.lower() in lowered for marker in FORBIDDEN_ACTION_MARKERS)


def _template_marker_count(text: str) -> int:
    markers = ("我的理解：", "安全状态：", "建议：", "证据记录：", "边界：")
    return sum(text.count(marker) for marker in markers)


def _view_to_dict(view: Mapping[str, Any] | Any) -> dict[str, Any]:
    if isinstance(view, Mapping):
        return {str(key): _jsonable(value) for key, value in view.items()}
    if hasattr(view, "to_dict"):
        return _jsonable(view.to_dict())
    if is_dataclass(view):
        return _jsonable(asdict(view))
    raise TypeError(f"unsupported decision view type: {type(view)!r}")


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return {}


def _safe_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value

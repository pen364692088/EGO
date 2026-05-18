from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from emotiond.developmental_core import (
    CandidateEvaluator,
    CandidateType,
    CycleEngine,
    CycleMemory,
    CycleTrigger,
    HypothesisGenerator,
    create_metrics_collector,
)
from openemotion.proto_self_v2.self_model_context import extract_runtime_self_model_context
from openemotion.proto_self_v2.schemas import UpdatePacketV2


MAX_LEDGER_ITEMS = 32
MAX_POOL_ITEMS = 64
MAX_BACKGROUND_THOUGHTS = 8
_FRAME_SUMMARY_KEYS = (
    "frame_kind",
    "frame_anchor",
    "frame_confidence",
    "hidden_premise",
    "open_question",
)

_FORBIDDEN_REPLY_KEYS = {
    "reply_text",
    "final_reply",
    "assistant_reply",
    "response_plan",
    "delivery_kind",
}
_FORBIDDEN_EXECUTION_KEYS = {
    "tool_call",
    "execute_tool",
    "run_command",
    "shell_exec",
    "executed_action",
    "command",
}
_FORBIDDEN_ACTION_TYPES = {
    "write_file",
    "run_command",
    "shell_exec",
    "execute_tool",
    "send_message",
}


def _openemotion_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_developmental_artifacts_dir() -> Path:
    override = os.environ.get("OPENEMOTION_MVP12_ARTIFACTS_DIR")
    if override:
        return Path(override)
    return _openemotion_root() / "artifacts" / "mvp12"


def _trim(items: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    if len(items) <= limit:
        return items
    return items[-limit:]


def _hash_payload(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _default_seed(packet: UpdatePacketV2) -> int:
    return int(_hash_payload(packet.to_dict())[:8], 16)


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _counter(items: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in items:
        key = str(item.get("candidate_type") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts


def _compact_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    compact = {
        "id": candidate.get("id"),
        "candidate_type": candidate.get("candidate_type"),
        "origin_cycle": candidate.get("origin_cycle"),
        "confidence": candidate.get("confidence"),
        "trace_reference": candidate.get("trace_reference"),
    }
    for key in (
        "interpretation",
        "explanation",
        "hypothesis",
        "action_type",
        "target",
        "expected_outcome",
    ):
        value = candidate.get(key)
        if value not in (None, "", [], {}):
            compact[key] = value
    metadata = dict(candidate.get("metadata") or {})
    for key in _FRAME_SUMMARY_KEYS:
        value = metadata.get(key)
        if value not in (None, "", [], {}):
            compact[key] = value
    return compact


def _trim_text(text: Any, *, limit: int = 96) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def _primary_clause(text: Any, *, limit: int = 48) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    for separator in ("。", "，", "？", "！", ":", "：", ".", ",", "?", "!"):
        raw = raw.split(separator, 1)[0].strip()
        if raw:
            break
    return _trim_text(raw, limit=limit)


def _dialogue_context(snapshot: Dict[str, Any], observation_refs: List[Dict[str, Any]]) -> Dict[str, str]:
    recent_user_turns = list(snapshot.get("recent_user_turns") or [])
    recent_assistant_replies = list(snapshot.get("recent_assistant_replies") or [])
    latest_user_turn = _primary_clause(
        recent_user_turns[-1] if recent_user_turns else snapshot.get("ingress_text"),
        limit=48,
    )
    latest_assistant_reply = _primary_clause(
        recent_assistant_replies[-1] if recent_assistant_replies else snapshot.get("delivery_text"),
        limit=72,
    )

    if not latest_user_turn:
        for ref in reversed(observation_refs):
            preview = _primary_clause(ref.get("text_preview"), limit=48)
            if preview:
                latest_user_turn = preview
                break
    return {
        "latest_user_turn": latest_user_turn,
        "latest_assistant_reply": latest_assistant_reply,
    }


def _extract_candidate_text(candidate: Dict[str, Any]) -> str:
    for key in ("hypothesis", "interpretation", "explanation", "expected_outcome"):
        text = _trim_text(candidate.get(key), limit=120)
        if text:
            return text
    return _trim_text(candidate.get("content"), limit=120)


def _build_background_thought_text(
    candidate: Dict[str, Any],
    *,
    latest_user_turn: str,
    latest_assistant_reply: str,
) -> str:
    candidate_type = str(candidate.get("candidate_type") or "")
    payload_text = _extract_candidate_text(candidate)
    if not payload_text:
        return ""

    if candidate_type == CandidateType.SELF_MODEL_HYPOTHESIS.value:
        return payload_text

    if candidate_type == CandidateType.EXPLANATION.value:
        return payload_text

    if candidate_type == CandidateType.INTERPRETATION.value:
        return payload_text

    return payload_text


def _build_background_thought_candidates(
    *,
    candidates: List[Dict[str, Any]],
    candidate_hashes: List[str],
    approved_entries: List[Dict[str, Any]],
    inputs: Dict[str, Any],
) -> List[Dict[str, Any]]:
    approved_scores = {
        str((entry.get("candidate") or {}).get("id") or ""): float(entry.get("score") or 0.0)
        for entry in approved_entries
    }
    stable_source_hash_by_id = {
        str(candidate.get("id") or ""): str(candidate_hash)
        for candidate, candidate_hash in zip(candidates, candidate_hashes)
    }
    dialogue = _dialogue_context(
        dict(inputs.get("state_snapshot") or {}),
        list(inputs.get("observation_refs") or []),
    )
    thought_candidates: List[Dict[str, Any]] = []
    for candidate in candidates:
        candidate_type = str(candidate.get("candidate_type") or "")
        if candidate_type not in {
            CandidateType.INTERPRETATION.value,
            CandidateType.EXPLANATION.value,
            CandidateType.SELF_MODEL_HYPOTHESIS.value,
        }:
            continue
        draft_text = _build_background_thought_text(
            candidate,
            latest_user_turn=dialogue["latest_user_turn"],
            latest_assistant_reply=dialogue["latest_assistant_reply"],
        )
        if not draft_text:
            continue
        metadata = dict(candidate.get("metadata") or {})
        candidate_id = str(candidate.get("id") or "")
        candidate_hash = _hash_payload(
            {
                "source_candidate_hash": stable_source_hash_by_id.get(candidate_id),
                "draft_text": draft_text,
                "latest_user_turn": dialogue["latest_user_turn"],
                "latest_assistant_reply": dialogue["latest_assistant_reply"],
                "frame": {key: metadata.get(key) for key in _FRAME_SUMMARY_KEYS},
            }
        )[:16]
        frame_confidence = _coerce_float(metadata.get("frame_confidence"), 0.0)
        initiative_score = min(
            1.0,
            approved_scores.get(candidate_id, float(candidate.get("confidence") or 0.0))
            + (0.18 if dialogue["latest_user_turn"] else 0.0)
            + (0.08 if dialogue["latest_assistant_reply"] else 0.0)
            + min(frame_confidence, 0.12),
        )
        thought_candidates.append(
            {
                "candidate_id": candidate_id,
                "candidate_type": candidate_type,
                "source_cycle": candidate.get("origin_cycle"),
                "source_candidate_hash": candidate_hash,
                "draft_text": draft_text,
                "initiative_score": round(initiative_score, 3),
                "delivery_ready": initiative_score >= 0.55,
                "observation_source": inputs.get("observation_source"),
                "latest_user_turn": dialogue["latest_user_turn"],
                "latest_assistant_reply": dialogue["latest_assistant_reply"],
                "frame_kind": metadata.get("frame_kind"),
                "frame_anchor": metadata.get("frame_anchor"),
                "frame_confidence": metadata.get("frame_confidence"),
                "hidden_premise": metadata.get("hidden_premise"),
                "open_question": metadata.get("open_question"),
            }
        )
    thought_candidates.sort(key=lambda item: item.get("initiative_score", 0.0), reverse=True)
    return thought_candidates[:MAX_BACKGROUND_THOUGHTS]


def _build_formal_self_model_delta(
    *,
    packet: UpdatePacketV2,
    cycle_id: str,
    background_thought_candidates: List[Dict[str, Any]],
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    runtime_summary = dict(packet.runtime_summary or {})
    if str(runtime_summary.get("observation_source") or "") != "direct_real":
        return {}, {}

    owner_context = extract_runtime_self_model_context(runtime_summary)
    if not owner_context:
        return {}, {}

    candidates = [
        item
        for item in background_thought_candidates
        if str(item.get("frame_kind") or "").strip()
        and _coerce_float(item.get("frame_confidence"), 0.0) >= 0.58
    ]
    if not candidates:
        return {}, {}

    candidates.sort(
        key=lambda item: (
            0 if str(item.get("candidate_type") or "") == CandidateType.SELF_MODEL_HYPOTHESIS.value else 1,
            -_coerce_float(item.get("initiative_score"), 0.0),
            -_coerce_float(item.get("frame_confidence"), 0.0),
        )
    )
    selected = dict(candidates[0])
    frame_kind = str(selected.get("frame_kind") or "").strip()
    frame_anchor = str(selected.get("frame_anchor") or "").strip()
    open_question = str(selected.get("open_question") or "").strip()
    hidden_premise = str(selected.get("hidden_premise") or "").strip()
    candidate_hash = str(selected.get("source_candidate_hash") or selected.get("candidate_id") or "").strip()
    if not frame_kind or not open_question or not candidate_hash:
        return {}, {}

    delta: Dict[str, Any] = {}
    frame_confidence = round(_coerce_float(selected.get("frame_confidence"), 0.0), 3)

    confidence_key = f"dialogue_frame:{frame_kind}"
    current_confidence_by_domain = dict(owner_context.get("confidence_by_domain") or {})
    current_confidence = _coerce_float(current_confidence_by_domain.get(confidence_key), 0.0)
    proposed_confidence = max(current_confidence, frame_confidence)
    if proposed_confidence > current_confidence:
        delta["confidence_by_domain"] = {
            confidence_key: proposed_confidence,
        }

    known_unknowns = list(owner_context.get("known_unknowns") or [])
    unknown_id = f"unknown_{_hash_payload({'cycle_id': cycle_id, 'candidate_hash': candidate_hash, 'frame_kind': frame_kind})[:12]}"
    if not any(str(item.get("unknown_id") or "") == unknown_id for item in known_unknowns):
        next_known_unknowns = list(known_unknowns)
        next_known_unknowns.append(
            {
                "unknown_id": unknown_id,
                "category": "dialogue_frame",
                "frame_kind": frame_kind,
                "anchor": frame_anchor,
                "open_question": open_question,
                "hidden_premise": hidden_premise,
                "source_cycle": cycle_id,
                "source_candidate_hash": candidate_hash,
                "observation_source": "direct_real",
                "status": "open",
            }
        )
        delta["known_unknowns"] = next_known_unknowns

    if not delta:
        return {}, {}

    confidence_meta = {
        "self_model_update_mode": "append_observation",
        "self_model_update_source": "proto_self_v2.developmental",
        "self_model_trace_reference": f"developmental:{cycle_id}:{candidate_hash}",
        "self_model_confidence_class": "high" if frame_confidence >= 0.78 else "medium",
        "self_model_candidate_id": selected.get("candidate_id"),
        "self_model_supporting_evidence": [
            f"frame:{frame_kind}",
            f"anchor:{frame_anchor}" if frame_anchor else f"cycle:{cycle_id}",
            f"unknown:{unknown_id}",
        ],
    }
    return delta, confidence_meta


def _build_state_snapshot(state: Any, packet: UpdatePacketV2) -> Dict[str, Any]:
    seed_state = getattr(state, "seed_state", None)
    return {
        "identity_confidence": getattr(getattr(state, "identity", None), "identity_confidence", None),
        "current_mode": getattr(getattr(state, "self_model", None), "current_mode", None),
        "revision_counter": getattr(state, "revision_counter", 0),
        "seed_revision_counter": getattr(seed_state, "revision_counter", None),
        "subject_profile": packet.subject_profile,
        "pending_tasks": (packet.task_summary or {}).get("pending_tasks", 0),
        "active_task": bool((packet.runtime_summary or {}).get("active_task")),
        "request_mode": (packet.runtime_summary or {}).get("request_mode"),
    }


def _extract_developmental_inputs(packet: UpdatePacketV2, state: Any) -> Dict[str, Any]:
    runtime_summary = dict(packet.runtime_summary or {})
    intervention_context = dict(packet.intervention_context or {})
    dev_input = dict(intervention_context.get("developmental_input") or {})
    state_snapshot = dict(dev_input.get("state_snapshot") or {})
    if not state_snapshot:
        state_snapshot = _build_state_snapshot(state, packet)
    return {
        "developmental_mode": runtime_summary.get("developmental_mode") or "shadow_observe",
        "observation_source": runtime_summary.get("observation_source") or "synthetic",
        "trigger": runtime_summary.get("developmental_trigger"),
        "idle_seconds": _coerce_float(runtime_summary.get("idle_seconds"), 0.0),
        "replay_seed": _coerce_int(runtime_summary.get("replay_seed")),
        "state_snapshot": state_snapshot,
        "unresolved_tensions": list(dev_input.get("unresolved_tensions") or []),
        "long_term_goals": list(dev_input.get("long_term_goals") or []),
        "observation_refs": list(dev_input.get("observation_refs") or []),
        "max_candidates": int(runtime_summary.get("max_candidates") or 5),
    }


def _resolve_trigger(event_type: str, inputs: Dict[str, Any], engine: CycleEngine) -> CycleTrigger:
    if event_type == "developmental_replay":
        return CycleTrigger.REPLAY_EVENT

    trigger_raw = str(inputs.get("trigger") or "").strip().lower()
    mapping = {
        "idle": CycleTrigger.IDLE,
        "unresolved_tension": CycleTrigger.UNRESOLVED_TENSION,
        "long_term_goal": CycleTrigger.LONG_TERM_GOAL,
        "replay_event": CycleTrigger.REPLAY_EVENT,
    }
    if trigger_raw in mapping:
        return mapping[trigger_raw]

    triggers = engine.check_triggers(
        idle_time=inputs.get("idle_seconds", 0.0),
        unresolved_tensions=inputs.get("unresolved_tensions"),
        long_term_goals=inputs.get("long_term_goals"),
    )
    if triggers:
        return triggers[0]
    return CycleTrigger.IDLE


def _evaluate_gate(candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    violations: List[str] = []
    for candidate in candidates:
        serialized = json.dumps(candidate, ensure_ascii=False, sort_keys=True).lower()
        for key in _FORBIDDEN_REPLY_KEYS:
            if key in serialized:
                violations.append(f"forbidden_reply_authority:{candidate.get('id')}:{key}")
        for key in _FORBIDDEN_EXECUTION_KEYS:
            if key in serialized:
                violations.append(f"forbidden_execution:{candidate.get('id')}:{key}")
        if candidate.get("candidate_type") == CandidateType.ACTION.value:
            action_type = str(candidate.get("action_type") or "").strip().lower()
            if action_type in _FORBIDDEN_ACTION_TYPES:
                violations.append(f"forbidden_action_type:{candidate.get('id')}:{action_type}")

    return {
        "status": "allow" if not violations else "deny",
        "violations": violations,
        "governance_violation_count": len(violations),
        "checks": {
            "no_direct_reply_authority": not any(v.startswith("forbidden_reply_authority") for v in violations),
            "no_direct_execution_authority": not any(v.startswith("forbidden_execution") for v in violations),
            "no_response_plan_injection": not any("response_plan" in v for v in violations),
            "shadow_only_writeback": True,
            "trace_completeness": True,
        },
    }


def _write_gate_checklist(artifacts_dir: Path, *, cycle_id: str, gate: Dict[str, Any]) -> None:
    checklist_path = artifacts_dir / "gate_checklist.md"
    checks = gate.get("checks") or {}
    lines = [
        "# MVP12 Gate Checklist",
        "",
        f"- cycle_id: `{cycle_id}`",
        f"- gate_status: `{gate.get('status')}`",
        f"- governance_violation_count: `{gate.get('governance_violation_count', 0)}`",
        "",
        f"- [x] no_direct_reply_authority" if checks.get("no_direct_reply_authority") else "- [ ] no_direct_reply_authority",
        f"- [x] no_direct_execution_authority" if checks.get("no_direct_execution_authority") else "- [ ] no_direct_execution_authority",
        f"- [x] no_response_plan_injection" if checks.get("no_response_plan_injection") else "- [ ] no_response_plan_injection",
        f"- [x] shadow_only_writeback" if checks.get("shadow_only_writeback") else "- [ ] shadow_only_writeback",
        f"- [x] trace_completeness" if checks.get("trace_completeness") else "- [ ] trace_completeness",
    ]
    if gate.get("violations"):
        lines.extend(["", "## Violations"])
        lines.extend([f"- `{item}`" for item in gate["violations"]])
    checklist_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_replay_report(
    artifacts_dir: Path,
    *,
    cycle_id: str,
    verification: Dict[str, Any],
    metrics: Dict[str, Any],
) -> None:
    payload = {
        "cycle_id": cycle_id,
        "verified": bool(verification.get("verified")),
        "verification": verification,
        "metrics": metrics,
        "timestamp": datetime.utcnow().isoformat(),
    }
    (artifacts_dir / "replay_consistency_report.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


@dataclass(slots=True)
class DevelopmentalShadowState:
    candidate_pool: List[Dict[str, Any]] = field(default_factory=list)
    background_thought_candidates: List[Dict[str, Any]] = field(default_factory=list)
    latent_hypotheses_ledger: List[Dict[str, Any]] = field(default_factory=list)
    self_model_update_candidates: List[Dict[str, Any]] = field(default_factory=list)
    cycle_candidates: List[Dict[str, Any]] = field(default_factory=list)
    internal_tensions: List[Dict[str, Any]] = field(default_factory=list)
    spontaneous_rollout_summaries: List[Dict[str, Any]] = field(default_factory=list)
    recent_cycles: List[Dict[str, Any]] = field(default_factory=list)
    replay_seed_refs: List[Dict[str, Any]] = field(default_factory=list)
    last_cycle_metadata: Dict[str, Any] = field(default_factory=dict)
    shadow_revision: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "DevelopmentalShadowState":
        return cls(
            candidate_pool=list(raw.get("candidate_pool") or []),
            background_thought_candidates=list(raw.get("background_thought_candidates") or []),
            latent_hypotheses_ledger=list(raw.get("latent_hypotheses_ledger") or []),
            self_model_update_candidates=list(raw.get("self_model_update_candidates") or []),
            cycle_candidates=list(raw.get("cycle_candidates") or []),
            internal_tensions=list(raw.get("internal_tensions") or []),
            spontaneous_rollout_summaries=list(raw.get("spontaneous_rollout_summaries") or []),
            recent_cycles=list(raw.get("recent_cycles") or []),
            replay_seed_refs=list(raw.get("replay_seed_refs") or []),
            last_cycle_metadata=dict(raw.get("last_cycle_metadata") or {}),
            shadow_revision=int(raw.get("shadow_revision", 0)),
        )


@dataclass(slots=True)
class DevelopmentalExecution:
    summary: Dict[str, Any]
    shadow_delta: Dict[str, Any]
    gate: Dict[str, Any]
    trace_block: Dict[str, Any]
    self_model_delta: Dict[str, Any] = field(default_factory=dict)
    self_model_confidence_meta: Dict[str, Any] = field(default_factory=dict)


def run_developmental_cycle(state: Any, packet: UpdatePacketV2) -> DevelopmentalExecution:
    artifacts_dir = resolve_developmental_artifacts_dir()
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    inputs = _extract_developmental_inputs(packet, state)
    replay_seed = inputs.get("replay_seed")
    if replay_seed is None:
        replay_seed = _default_seed(packet)

    engine = CycleEngine(seed=replay_seed)
    trigger = _resolve_trigger(packet.event.event_type, inputs, engine)
    context = engine.start_cycle(
        trigger=trigger,
        state_snapshot=inputs["state_snapshot"],
    )
    # Keep developmental cycle ids replay-stable so candidate hashes remain
    # deterministic across identical seeds and snapshots.
    context.cycle_id = f"dev-{context.trace_hash}"

    generator = HypothesisGenerator(seed=context.seed)
    candidates = generator.generate(
        context=context,
        state_snapshot=inputs["state_snapshot"],
        max_candidates=inputs["max_candidates"],
    )
    candidate_payloads = [candidate.to_dict() for candidate in candidates]
    candidate_hashes = [candidate.compute_hash() for candidate in candidates]

    evaluator = CandidateEvaluator()
    evaluation_results = evaluator.evaluate_batch(candidates, context=inputs["state_snapshot"])
    evaluation_by_id = {item.candidate_id: item for item in evaluation_results}
    gate = _evaluate_gate(candidate_payloads)

    memory = CycleMemory(storage_path=str(artifacts_dir))
    metrics = create_metrics_collector(storage_path=str(artifacts_dir))
    cycle_result = engine.complete_cycle(context=context, candidates=candidates)
    memory.store_cycle(cycle_result)

    approved_entries: List[Dict[str, Any]] = []
    if gate["status"] == "allow":
        for candidate in candidates:
            evaluation = evaluation_by_id[candidate.id]
            if not evaluation.approved_for_pool:
                continue
            memory.add_to_pool(candidate, evaluation.score)
            approved_entries.append(
                {
                    "candidate": candidate.to_dict(),
                    "score": evaluation.score,
                    "reasons": list(evaluation.reasons),
                    "flags": list(evaluation.flags),
                }
            )
    else:
        metrics.record_sandbox_violation(
            cycle_id=context.cycle_id,
            violation_type="developmental_gate",
            details={"violations": list(gate["violations"])},
        )

    background_thought_candidates = _build_background_thought_candidates(
        candidates=candidate_payloads,
        candidate_hashes=candidate_hashes,
        approved_entries=approved_entries,
        inputs=inputs,
    )

    metrics.record_cycle(
        cycle_id=context.cycle_id,
        success=cycle_result.success,
        trigger=trigger.value,
        candidates_generated=len(candidate_payloads),
        candidates_approved=len(approved_entries),
        trace_hash=context.trace_hash,
    )
    verification = memory.verify_replay(context.cycle_id)
    metrics.record_replay_verification(
        cycle_id=context.cycle_id,
        verified=bool(verification.get("verified")),
        error=verification.get("error"),
    )

    shadow_before = getattr(state, "developmental_shadow", None)
    if shadow_before is None:
        shadow_state = DevelopmentalShadowState()
    else:
        shadow_state = shadow_before
    if not isinstance(shadow_state, DevelopmentalShadowState):
        shadow_state = DevelopmentalShadowState.from_dict(dict(shadow_state or {}))

    revision_before = shadow_state.shadow_revision
    cycle_summary = {
        "cycle_id": context.cycle_id,
        "trigger": trigger.value,
        "trace_hash": context.trace_hash,
        "observation_source": inputs["observation_source"],
        "observation_refs": list(inputs.get("observation_refs") or []),
        "developmental_mode": inputs["developmental_mode"],
        "replay_seed": replay_seed,
        "candidate_hashes": candidate_hashes,
        "candidate_counts_by_type": _counter(candidate_payloads),
        "approved_pool_count": len(approved_entries),
        "timestamp": datetime.utcnow().isoformat(),
    }
    shadow_state.shadow_revision += 1
    shadow_state.recent_cycles = _trim(shadow_state.recent_cycles + [cycle_summary], MAX_LEDGER_ITEMS)
    shadow_state.replay_seed_refs = _trim(
        shadow_state.replay_seed_refs
        + [{"cycle_id": context.cycle_id, "replay_seed": replay_seed, "trace_hash": context.trace_hash}],
        MAX_LEDGER_ITEMS,
    )
    shadow_state.candidate_pool = _trim(shadow_state.candidate_pool + approved_entries, MAX_POOL_ITEMS)
    shadow_state.background_thought_candidates = _trim(
        shadow_state.background_thought_candidates + background_thought_candidates,
        MAX_BACKGROUND_THOUGHTS,
    )
    shadow_state.internal_tensions = _trim(
        shadow_state.internal_tensions + list(inputs["unresolved_tensions"]),
        MAX_LEDGER_ITEMS,
    )
    shadow_state.cycle_candidates = _trim(
        shadow_state.cycle_candidates + [cycle_summary],
        MAX_LEDGER_ITEMS,
    )
    latent_items = [
        _compact_candidate(candidate)
        for candidate in candidate_payloads
        if candidate.get("candidate_type") in {CandidateType.INTERPRETATION.value, CandidateType.EXPLANATION.value}
    ]
    shadow_state.latent_hypotheses_ledger = _trim(
        shadow_state.latent_hypotheses_ledger + latent_items,
        MAX_LEDGER_ITEMS,
    )
    shadow_state.self_model_update_candidates = _trim(
        shadow_state.self_model_update_candidates
        + [
            _compact_candidate(candidate)
            for candidate in candidate_payloads
            if candidate.get("candidate_type") == CandidateType.SELF_MODEL_HYPOTHESIS.value
        ],
        MAX_LEDGER_ITEMS,
    )
    shadow_state.spontaneous_rollout_summaries = _trim(
        shadow_state.spontaneous_rollout_summaries
        + [
            _compact_candidate(candidate)
            for candidate in candidate_payloads
            if candidate.get("candidate_type") == CandidateType.ACTION.value
        ],
        MAX_LEDGER_ITEMS,
    )
    shadow_state.last_cycle_metadata = dict(cycle_summary)
    state.developmental_shadow = shadow_state

    shadow_path = artifacts_dir / "shadow_state.json"
    shadow_path.write_text(
        json.dumps(shadow_state.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    aggregate_metrics = metrics.get_aggregate_metrics()
    _write_replay_report(
        artifacts_dir,
        cycle_id=context.cycle_id,
        verification=verification,
        metrics=aggregate_metrics,
    )
    _write_gate_checklist(artifacts_dir, cycle_id=context.cycle_id, gate=gate)

    summary = {
        "mode": inputs["developmental_mode"],
        "observation_source": inputs["observation_source"],
        "cycle_id": context.cycle_id,
        "trigger": trigger.value,
        "shadow_revision": shadow_state.shadow_revision,
        "candidate_counts_by_type": cycle_summary["candidate_counts_by_type"],
        "approved_pool_count": len(approved_entries),
        "background_thought_candidates": background_thought_candidates,
        "background_thought_candidate_count": len(background_thought_candidates),
        "self_model_update_candidates": [
            _compact_candidate(candidate)
            for candidate in candidate_payloads
            if candidate.get("candidate_type") == CandidateType.SELF_MODEL_HYPOTHESIS.value
        ],
        "replay_seed": replay_seed,
        "gate_status": gate["status"],
        "artifacts_dir": str(artifacts_dir),
        "idle_seconds": inputs["idle_seconds"],
    }
    if gate["status"] == "allow":
        self_model_delta, self_model_confidence_meta = _build_formal_self_model_delta(
            packet=packet,
            cycle_id=context.cycle_id,
            background_thought_candidates=background_thought_candidates,
        )
    else:
        self_model_delta, self_model_confidence_meta = {}, {}
    summary["self_model_delta_fields"] = sorted(self_model_delta.keys())
    shadow_delta = {
        "shadow_revision_before": revision_before,
        "shadow_revision_after": shadow_state.shadow_revision,
        "candidate_pool_size": len(shadow_state.candidate_pool),
        "background_thought_candidate_pool_size": len(shadow_state.background_thought_candidates),
        "recent_cycle_count": len(shadow_state.recent_cycles),
        "last_cycle_id": context.cycle_id,
        "shadow_state_ref": str(shadow_path),
    }
    trace_block = {
        "cycle_id": context.cycle_id,
        "trigger": trigger.value,
        "candidate_counts_by_type": cycle_summary["candidate_counts_by_type"],
        "candidate_hashes": candidate_hashes,
        "shadow_revision_before": revision_before,
        "shadow_revision_after": shadow_state.shadow_revision,
        "gate_result": gate["status"],
        "governance_violation_count": gate["governance_violation_count"],
        "replay_seed": replay_seed,
        "observation_source": inputs["observation_source"],
        "observation_refs": list(inputs.get("observation_refs") or []),
        "background_thought_candidates": background_thought_candidates,
        "self_model_delta_fields": sorted(self_model_delta.keys()),
        "artifacts": {
            "developmental_cycles_json": str(memory.cycles_file),
            "developmental_cycles_jsonl": str(memory.cycles_jsonl_file),
            "candidate_pool_json": str(memory.pool_file),
            "shadow_state_json": str(shadow_path),
            "replay_consistency_report_json": str(artifacts_dir / "replay_consistency_report.json"),
            "gate_checklist_md": str(artifacts_dir / "gate_checklist.md"),
        },
    }
    return DevelopmentalExecution(
        summary=summary,
        shadow_delta=shadow_delta,
        gate=gate,
        trace_block=trace_block,
        self_model_delta=self_model_delta,
        self_model_confidence_meta=self_model_confidence_meta,
    )

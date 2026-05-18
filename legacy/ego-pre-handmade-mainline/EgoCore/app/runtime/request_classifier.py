"""Legacy request classification layer kept for compatibility.

⚠️ Status:
- still used by `app/runtime/agent_runner.py`
- still covered by legacy/runtime-hardening tests
- not the authority source for Telegram Runtime v2 mainline behavior

Prefer Runtime v2 path + bridge/typed contracts for new Telegram mainline work.
"""

from typing import Dict, Any
from .intent_classifier import classify_intent_llm
from .request_resolution_policy import RequestResolutionPolicy


_POLICY = RequestResolutionPolicy()


def is_small_talk(user_input: str) -> bool:
    return _POLICY.extract_signals(user_input).small_talk_intent


def classify_request_fallback(user_input: str, session_state: Dict[str, Any]) -> Dict[str, Any]:
    return _POLICY.resolve(user_input, session_state)


async def classify_request(user_input: str, session_state: Dict[str, Any]) -> Dict[str, Any]:
    # Host guardrail: explicit file path + edit intent must be task, even if LLM misclassifies as chat.
    host_fallback = classify_request_fallback(user_input, session_state)
    host_kind = host_fallback.get("kind")
    host_path = host_fallback.get("force_target_path")

    try:
        llm_result = await classify_intent_llm(user_input, session_state)
        turn_type = llm_result.get("turn_type")
        if turn_type in {"chat", "new_task", "follow_up", "unresolved_request_query", "instruction", "ambiguous"}:
            host_signals = (host_fallback.get("signals") or {})
            host_likely_edit = bool(host_signals.get("likely_edit_request"))
            llm_intent_type = llm_result.get("intent_type")
            if host_kind in {"new_task", "follow_up"} and host_path:
                if turn_type in {"chat", "ambiguous"}:
                    return {
                        "kind": host_kind,
                        "reason": "host_override_explicit_path",
                        "force_target_path": host_path,
                        "llm_intent": llm_result,
                    }
                if host_likely_edit and llm_intent_type in {"inspect_artifact", "other", "status_query", None}:
                    forced = dict(llm_result)
                    forced["intent_type"] = "edit_artifact_property"
                    forced["target_path"] = host_path
                    return {
                        "kind": host_kind,
                        "reason": "host_override_edit_intent",
                        "force_target_path": host_path,
                        "llm_intent": forced,
                    }
            return {
                "kind": turn_type,
                "reason": "llm_classifier",
                "force_target_path": llm_result.get("target_path") or session_state.get("active_target"),
                "llm_intent": llm_result,
            }
    except Exception:
        pass
    host_fallback["reason"] = host_fallback.get("reason", "fallback") + "_fallback"
    host_fallback["llm_intent"] = None
    return host_fallback

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


_SMALL_TALK = {"你好", "你好啊", "嗨", "hi", "hello", "在吗", "还记得我吗"}
_CONTINUE_MARKERS = ["继续", "接着", "接着做", "继续做", "还有呢", "继续上一个任务"]
_UNRESOLVED_QUERY_MARKERS = [
    "为什么没有回应", "为什么没回应", "上一条为什么没回", "这条消息为什么没有回应",
    "那条消息", "上一条呢", "看一下这个消息为什么没有回应", "那条怎么没成功", "没变化啊",
    "你没改啊", "你还是没改啊", "根本没改", "没有改", "没处理好"
]
_AFFIRMATIVE_MARKERS = {"对", "是", "就这个", "好的", "好", "嗯", "没错"}
_STYLE_MARKERS = ["复古", "科技", "朋克", "现代", "简约", "柔和", "暖色", "深色", "配色", "风格"]
_EDIT_MARKERS = ["改", "修改", "换", "调整", "配色", "颜色", "背景", "字体", "样式"]


@dataclass
class RequestSignals:
    raw_text: str
    normalized_text: str
    explicit_path: Optional[str] = None
    abbreviated_path: Optional[str] = None
    continue_intent: bool = False
    affirmative_intent: bool = False
    style_followup_intent: bool = False
    unresolved_query_intent: bool = False
    small_talk_intent: bool = False
    likely_edit_request: bool = False


@dataclass
class BindingContext:
    current_request_id: Optional[str] = None
    current_chain_id: Optional[str] = None
    current_target_path: Optional[str] = None
    latest_unresolved_request_id: Optional[str] = None
    known_targets: List[str] = field(default_factory=list)
    has_active_task: bool = False
    has_plan_steps: bool = False
    has_artifacts: bool = False


class RequestResolutionPolicy:
    def extract_signals(self, user_input: str) -> RequestSignals:
        text = (user_input or "").strip()
        normalized = text.lower()
        abbreviated_match = re.search(r'(/[^\s]*\.\.\.[^\s]*)', text)
        explicit_match = re.search(r'(/[^\s,，]+)', text)
        abbreviated_path = abbreviated_match.group(1) if abbreviated_match else None
        explicit_path = None if abbreviated_path else (explicit_match.group(1) if explicit_match else None)

        return RequestSignals(
            raw_text=text,
            normalized_text=normalized,
            explicit_path=explicit_path,
            abbreviated_path=abbreviated_path,
            continue_intent=any(x in text for x in _CONTINUE_MARKERS),
            affirmative_intent=text in _AFFIRMATIVE_MARKERS,
            style_followup_intent=any(x in text for x in _STYLE_MARKERS),
            unresolved_query_intent=any(x in text for x in _UNRESOLVED_QUERY_MARKERS),
            small_talk_intent=normalized in _SMALL_TALK,
            likely_edit_request=any(x in text for x in _EDIT_MARKERS),
        )

    def build_binding_context(self, session_state: Dict[str, Any]) -> BindingContext:
        known_targets = list((session_state.get("artifact_context_by_path") or {}).keys())
        return BindingContext(
            current_request_id=session_state.get("active_request_id"),
            current_chain_id=session_state.get("active_chain_id"),
            current_target_path=session_state.get("active_target") or session_state.get("active_artifact_path"),
            latest_unresolved_request_id=session_state.get("latest_unresolved_request_id"),
            known_targets=known_targets,
            has_active_task=bool(session_state.get("active_task_id")),
            has_plan_steps=bool(session_state.get("plan_steps")),
            has_artifacts=bool(session_state.get("artifact_context_by_path")),
        )

    def resolve(self, user_input: str, session_state: Dict[str, Any]) -> Dict[str, Any]:
        signals = self.extract_signals(user_input)
        binding = self.build_binding_context(session_state)

        if signals.unresolved_query_intent:
            return self._decision("unresolved_request_query", "query_unresolved_request", None, signals, binding)

        if signals.small_talk_intent:
            return self._decision("small_talk", "greeting_short_circuit", None, signals, binding)

        if signals.explicit_path:
            if binding.current_target_path and signals.raw_text == signals.explicit_path:
                return self._decision("follow_up", "path_only_followup", signals.explicit_path, signals, binding)
            return self._decision("new_task", "explicit_path", signals.explicit_path, signals, binding)

        if signals.abbreviated_path:
            resolved = self._resolve_abbreviated_path(signals.abbreviated_path, binding)
            if resolved:
                kind = "follow_up" if binding.current_target_path == resolved else "new_task"
                reason = "abbreviated_path_bound_to_active_target" if kind == "follow_up" else "abbreviated_path_resolved"
                return self._decision(kind, reason, resolved, signals, binding)
            return self._decision("ask_for_clarification", "abbreviated_path_ambiguous", None, signals, binding)

        if binding.current_target_path and (signals.affirmative_intent or signals.style_followup_intent):
            return self._decision("follow_up", "affirm_or_style_followup", binding.current_target_path, signals, binding)

        if signals.continue_intent and binding.has_artifacts:
            return self._decision("follow_up", "relative_followup", binding.current_target_path, signals, binding)

        if binding.has_active_task and binding.has_plan_steps:
            return self._decision("follow_up", "active_task_with_remaining_steps", binding.current_target_path, signals, binding)

        return self._decision("new_task", "default_new_task", binding.current_target_path, signals, binding)

    def _resolve_abbreviated_path(self, abbreviated_path: str, binding: BindingContext) -> Optional[str]:
        if binding.current_target_path and self._path_matches_abbreviation(binding.current_target_path, abbreviated_path):
            return binding.current_target_path
        matches = [p for p in binding.known_targets if self._path_matches_abbreviation(p, abbreviated_path)]
        if len(matches) == 1:
            return matches[0]
        return None

    @staticmethod
    def _path_matches_abbreviation(full_path: str, abbreviated_path: str) -> bool:
        if "..." not in abbreviated_path:
            return full_path == abbreviated_path
        prefix, suffix = abbreviated_path.split("...", 1)
        return full_path.startswith(prefix) and full_path.endswith(suffix)

    @staticmethod
    def _decision(kind: str, reason: str, force_target_path: Optional[str], signals: RequestSignals, binding: BindingContext) -> Dict[str, Any]:
        return {
            "kind": kind,
            "reason": reason,
            "force_target_path": force_target_path,
            "signals": signals.__dict__,
            "binding_context": binding.__dict__,
        }

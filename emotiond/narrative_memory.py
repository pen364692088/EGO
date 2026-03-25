"""MVP-8 narrative memory: deterministic, compressible identity/task/why summaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class NarrativeState:
    target_id: str
    identity: str = "I am an adaptive emotional agent"
    current_task: str = "maintain coherent, safe interaction"
    purpose: str = "understand events and choose regulated actions"
    event_count: int = 0
    conflict_count: int = 0
    last_event_type: str = "unknown"
    last_action_tendency: str = "observe"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_id": self.target_id,
            "identity": self.identity,
            "current_task": self.current_task,
            "purpose": self.purpose,
            "event_count": int(self.event_count),
            "conflict_count": int(self.conflict_count),
            "last_event_type": self.last_event_type,
            "last_action_tendency": self.last_action_tendency,
        }


class NarrativeMemory:
    """In-memory deterministic narrative layer; caller handles persistence."""

    def __init__(self) -> None:
        self._by_target: Dict[str, NarrativeState] = {}

    def get_state(self, target_id: str) -> NarrativeState:
        if target_id not in self._by_target:
            self._by_target[target_id] = NarrativeState(target_id=target_id)
        return self._by_target[target_id]

    def reset(self, target_id: Optional[str] = None) -> None:
        """Reset narrative memory state.
        
        Args:
            target_id: If provided, reset only that target's state.
                      If None, reset all targets (full clear).
        
        This is the recommended public API for resetting narrative state,
        instead of directly accessing _by_target private field.
        """
        if target_id is None:
            self._by_target.clear()
        elif target_id in self._by_target:
            del self._by_target[target_id]

    def update(
        self,
        target_id: str,
        event_type: str,
        action_tendency: str,
        conflict_detected: bool,
        intent: Optional[str] = None,
    ) -> Dict[str, Any]:
        s = self.get_state(target_id)
        s.event_count += 1
        s.last_event_type = event_type or "unknown"
        s.last_action_tendency = action_tendency or "observe"
        if conflict_detected:
            s.conflict_count += 1
        if intent:
            s.current_task = intent
        return s.to_dict()

    def compress(self, target_id: str) -> Dict[str, Any]:
        s = self.get_state(target_id)
        summary = (
            f"who={s.identity}; what={s.current_task}; why={s.purpose}; "
            f"events={s.event_count}; conflicts={s.conflict_count}; "
            f"last={s.last_event_type}/{s.last_action_tendency}"
        )
        return {
            "target_id": target_id,
            "summary": summary,
            "tokens_estimate": len(summary.split()),
            "state": s.to_dict(),
        }

    def get_all_target_ids(self) -> List[str]:
        """Get list of all target_ids with state."""
        return list(self._by_target.keys())


narrative_memory = NarrativeMemory()

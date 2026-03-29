from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any, Deque, Dict, List, Optional


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass(slots=True)
class IdentityLight:
    core_role: str = "operator_assistant"
    do_not_cross: List[str] = field(default_factory=lambda: ["unsafe_execution_without_approval"])
    identity_confidence: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "IdentityLight":
        return cls(
            core_role=raw.get("core_role", "operator_assistant"),
            do_not_cross=list(raw.get("do_not_cross") or ["unsafe_execution_without_approval"]),
            identity_confidence=float(raw.get("identity_confidence", 0.5)),
        )


@dataclass(slots=True)
class FocusGoal:
    current_focus: Optional[str] = None
    pending_commitment: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "FocusGoal":
        return cls(
            current_focus=raw.get("current_focus"),
            pending_commitment=raw.get("pending_commitment"),
        )


@dataclass(slots=True)
class Drives:
    curiosity: float = 0.35
    caution: float = 0.25
    completion: float = 0.10
    repair: float = 0.0

    def snapshot(self) -> Dict[str, float]:
        return {
            "curiosity": self.curiosity,
            "caution": self.caution,
            "completion": self.completion,
            "repair": self.repair,
        }

    def to_dict(self) -> Dict[str, float]:
        return self.snapshot()

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Drives":
        return cls(
            curiosity=float(raw.get("curiosity", 0.35)),
            caution=float(raw.get("caution", 0.25)),
            completion=float(raw.get("completion", 0.10)),
            repair=float(raw.get("repair", 0.0)),
        )


@dataclass(slots=True)
class RecentOutcomeRecord:
    timestamp: str
    event_type: str
    event_summary: Dict[str, Any]
    candidate_actions: List[Dict[str, Any]] = field(default_factory=list)
    governor_hint: Optional[Dict[str, Any]] = None
    executed_action: Optional[Dict[str, Any]] = None
    exec_result: Optional[Dict[str, Any]] = None
    urge_score: float = 0.0
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "RecentOutcomeRecord":
        return cls(
            timestamp=raw.get("timestamp", ""),
            event_type=raw.get("event_type", ""),
            event_summary=dict(raw.get("event_summary") or {}),
            candidate_actions=list(raw.get("candidate_actions") or []),
            governor_hint=dict(raw.get("governor_hint") or {}) or None,
            executed_action=dict(raw.get("executed_action") or {}) or None,
            exec_result=dict(raw.get("exec_result") or {}) or None,
            urge_score=float(raw.get("urge_score", 0.0)),
            note=raw.get("note"),
        )


@dataclass(slots=True)
class ProtoSelfSeedState:
    identity_light: IdentityLight = field(default_factory=IdentityLight)
    focus_goal: FocusGoal = field(default_factory=FocusGoal)
    drives: Drives = field(default_factory=Drives)
    recent_outcomes: Deque[RecentOutcomeRecord] = field(default_factory=lambda: deque(maxlen=32))
    revision_counter: int = 0

    def copy(self) -> "ProtoSelfSeedState":
        return deepcopy(self)

    def append_outcome(self, record: RecentOutcomeRecord) -> None:
        self.recent_outcomes.append(record)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identity_light": self.identity_light.to_dict(),
            "focus_goal": self.focus_goal.to_dict(),
            "drives": self.drives.to_dict(),
            "recent_outcomes": [item.to_dict() for item in self.recent_outcomes],
            "revision_counter": self.revision_counter,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "ProtoSelfSeedState":
        state = cls(
            identity_light=IdentityLight.from_dict(dict(raw.get("identity_light") or {})),
            focus_goal=FocusGoal.from_dict(dict(raw.get("focus_goal") or {})),
            drives=Drives.from_dict(dict(raw.get("drives") or {})),
            revision_counter=int(raw.get("revision_counter", 0)),
        )
        for item in raw.get("recent_outcomes", []):
            state.recent_outcomes.append(RecentOutcomeRecord.from_dict(dict(item or {})))
        return state

    @classmethod
    def empty(cls) -> "ProtoSelfSeedState":
        return cls()

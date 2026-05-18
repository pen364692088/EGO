from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class ArtifactState:
    path: Optional[str] = None
    kind: Optional[str] = None
    active_focus: Optional[str] = None
    default_edit_target: Optional[str] = None
    last_known_state: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "kind": self.kind,
            "active_focus": self.active_focus,
            "default_edit_target": self.default_edit_target,
            "last_known_state": self.last_known_state,
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "ArtifactState":
        data = data or {}
        return cls(
            path=data.get("path"),
            kind=data.get("kind"),
            active_focus=data.get("active_focus"),
            default_edit_target=data.get("default_edit_target"),
            last_known_state=data.get("last_known_state", {}),
        )

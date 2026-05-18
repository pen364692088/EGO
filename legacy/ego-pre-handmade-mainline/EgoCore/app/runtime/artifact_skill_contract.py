from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ArtifactEdit:
    target_path: Optional[str] = None
    scope: Optional[str] = None
    property: Optional[str] = None
    operation: Optional[str] = None
    value: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_path": self.target_path,
            "scope": self.scope,
            "property": self.property,
            "operation": self.operation,
            "value": self.value,
        }


@dataclass
class ArtifactSkillRequest:
    action: str  # inspect_artifact | edit_artifact | batch_edit_artifacts
    artifact_type: str
    targets: List[Dict[str, Any]] = field(default_factory=list)
    edits: List[ArtifactEdit] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "artifact_type": self.artifact_type,
            "targets": self.targets,
            "edits": [e.to_dict() for e in self.edits],
        }


@dataclass
class ArtifactSkillResult:
    success: bool
    action: str
    artifact_type: str
    targets: List[Dict[str, Any]] = field(default_factory=list)
    observations: List[Dict[str, Any]] = field(default_factory=list)
    completed_steps: List[str] = field(default_factory=list)
    failed_steps: List[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "action": self.action,
            "artifact_type": self.artifact_type,
            "targets": self.targets,
            "observations": self.observations,
            "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps,
            "summary": self.summary,
        }

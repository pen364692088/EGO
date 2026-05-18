from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


@dataclass
class TaskPlanState:
    task_id: Optional[str] = None
    task_plan: str = ""
    plan_steps: List[Dict[str, Any]] = field(default_factory=list)
    targets: List[Dict[str, Any]] = field(default_factory=list)
    active_target: Optional[str] = None
    completed_steps: List[str] = field(default_factory=list)
    last_observation: Dict[str, Any] = field(default_factory=dict)
    artifact_context_by_path: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_plan": self.task_plan,
            "plan_steps": self.plan_steps,
            "targets": self.targets,
            "active_target": self.active_target,
            "completed_steps": self.completed_steps,
            "last_observation": self.last_observation,
            "artifact_context_by_path": self.artifact_context_by_path,
        }

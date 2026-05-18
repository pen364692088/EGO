"""
OpenEmotion Self-Model Module

自我模型的正式本体模块。
负责能力、限制、目标、承诺的定义和更新规则。

这是当前 formal mainline 上的 self-model formal owner surface。
`proto_self` 中的 self-model 仍会参与运行时计算，但只作为
compute/proposal substrate，不承担 formal owner 解释权。
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

FORMAL_OWNER_SCHEMA_VERSION = "1.0.0"
AUTHORITY_STATUS = "formal_owner"
FORMAL_MAINLINE_ENABLED = True
LIVE_RUNTIME_AUTHORITY = "openemotion.self_model"
ACTIVE_RUNTIME_SUBSTRATE = "openemotion.proto_self.self_model"
ACTIVE_RUNTIME_SUBSTRATE_ROLE = "compute_proposal_only"
LEGACY_COMPAT_SURFACES = ("emotiond.self_model_adapter",)
LEGACY_REFERENCE_ONLY_SURFACES = ("emotiond.self_model_mirror",)
FORMAL_MAINLINE_READERS = (
    "EgoCore/app/runtime_v2/proto_self_runtime.py",
    "OpenEmotion/openemotion/proto_self_v2/self_model_context.py",
)

PHASE1_AUTHORITATIVE_FIELDS = (
    "schema_version",
    "identity_handle",
    "capabilities",
    "limitations",
    "active_goals",
    "standing_commitments",
    "tool_authority_boundary",
    "dependency_map",
    "confidence_by_domain",
    "known_unknowns",
    "created_at",
    "last_modified_at",
    "modification_audit_trail",
)

PHASE1_ALLOWED_PROOF_LEVERS = (
    "active_goals",
    "standing_commitments",
    "confidence_by_domain",
    "capabilities",
    "limitations",
)

PHASE1_LEGACY_REFERENCE_ONLY_FIELDS = (
    "behavioral_tendencies",
    "active_tensions",
    "continuity_trace",
    "revision_history",
    "SelfModelManager",
)

RUNTIME_LOCAL_PROJECTION_FIELD = "proto_self_v2.state.self_model"
RUNTIME_LOCAL_PROJECTION_SEMANTICS = "runtime-local projection of formal owner state"


class CapabilityLevel(Enum):
    """能力等级"""
    NONE = "none"
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class GoalStatus(Enum):
    """目标状态"""
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class Priority(Enum):
    """优先级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Capability:
    """能力"""
    capability_id: str
    name: str
    category: str
    current_level: str
    description: Optional[str] = None
    constraints: List[str] = field(default_factory=list)
    last_verified_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Limitation:
    """限制"""
    limitation_id: str
    description: str
    impact_level: str
    workaround: Optional[str] = None
    discovered_at: Optional[str] = None
    context: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Goal:
    """目标"""
    goal_id: str
    description: str
    status: str
    priority: str
    progress: float = 0.0
    deadline: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StandingCommitment:
    """持续承诺"""
    commitment_id: str
    source: str  # identity_invariants / runtime_learned / owner_directive
    description: str
    binding_level: str
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SelfModel:
    """
    自我模型本体

    这是当前 self-model formal owner 的权威定义。
    所有字段语义的解释权归 OpenEmotion 的 formal owner surface。
    当前 formal mainline 读取和 governed writeback 都以这份结构为准。
    """

    # 关联的身份
    identity_handle: str

    # Schema 元数据
    schema_version: str = FORMAL_OWNER_SCHEMA_VERSION

    # 能力列表
    capabilities: List[Capability] = field(default_factory=list)

    # 限制列表
    limitations: List[Limitation] = field(default_factory=list)

    # 活跃目标
    active_goals: List[Goal] = field(default_factory=list)

    # 持续承诺
    standing_commitments: List[StandingCommitment] = field(default_factory=list)

    # 工具权限边界
    current_allowed_tools: List[str] = field(default_factory=list)
    restricted_tools: List[str] = field(default_factory=list)
    forbidden_tools: List[str] = field(default_factory=list)

    # 依赖映射
    external_services: List[Dict[str, Any]] = field(default_factory=list)
    internal_modules: List[Dict[str, Any]] = field(default_factory=list)

    # 领域置信度
    confidence_by_domain: Dict[str, float] = field(default_factory=dict)

    # 已知未知
    known_unknowns: List[Dict[str, Any]] = field(default_factory=list)

    # 元数据
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_modified_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    modification_audit_trail: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "identity_handle": self.identity_handle,
            "capabilities": [c.to_dict() for c in self.capabilities],
            "limitations": [l.to_dict() for l in self.limitations],
            "active_goals": [g.to_dict() for g in self.active_goals],
            "standing_commitments": [c.to_dict() for c in self.standing_commitments],
            "tool_authority_boundary": {
                "current_allowed_tools": self.current_allowed_tools,
                "restricted_tools": self.restricted_tools,
                "forbidden_tools": self.forbidden_tools,
            },
            "dependency_map": {
                "external_services": self.external_services,
                "internal_modules": self.internal_modules,
            },
            "confidence_by_domain": self.confidence_by_domain,
            "known_unknowns": self.known_unknowns,
            "created_at": self.created_at,
            "last_modified_at": self.last_modified_at,
            "modification_audit_trail": self.modification_audit_trail,
        }
        return payload

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SelfModel":
        """从字典创建"""
        tools = data.get("tool_authority_boundary", {})
        dep_map = data.get("dependency_map", {})

        return cls(
            schema_version=data.get("schema_version", FORMAL_OWNER_SCHEMA_VERSION),
            identity_handle=data.get("identity_handle") or data["model_handle"],
            capabilities=[Capability(**c) if isinstance(c, dict) else c for c in data.get("capabilities", [])],
            limitations=[Limitation(**l) if isinstance(l, dict) else l for l in data.get("limitations", [])],
            active_goals=[Goal(**g) if isinstance(g, dict) else g for g in data.get("active_goals", [])],
            standing_commitments=[StandingCommitment(**c) if isinstance(c, dict) else c for c in data.get("standing_commitments", [])],
            current_allowed_tools=tools.get("current_allowed_tools", []),
            restricted_tools=tools.get("restricted_tools", []),
            forbidden_tools=tools.get("forbidden_tools", []),
            external_services=dep_map.get("external_services", []),
            internal_modules=dep_map.get("internal_modules", []),
            confidence_by_domain=data.get("confidence_by_domain", {}),
            known_unknowns=data.get("known_unknowns", []),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            last_modified_at=data.get("last_modified_at", datetime.now(timezone.utc).isoformat()),
            modification_audit_trail=data.get("modification_audit_trail", []),
        )

    def get_capability_by_id(self, capability_id: str) -> Optional[Capability]:
        """获取能力"""
        for c in self.capabilities:
            if c.capability_id == capability_id:
                return c
        return None

    def get_goal_by_id(self, goal_id: str) -> Optional[Goal]:
        """获取目标"""
        for g in self.active_goals:
            if g.goal_id == goal_id:
                return g
        return None

    def update_capability_level(self, capability_id: str, new_level: str) -> bool:
        """更新能力等级"""
        cap = self.get_capability_by_id(capability_id)
        if cap:
            cap.current_level = new_level
            cap.last_verified_at = datetime.now(timezone.utc).isoformat()
            self.last_modified_at = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def update_goal_status(self, goal_id: str, new_status: str) -> bool:
        """更新目标状态"""
        goal = self.get_goal_by_id(goal_id)
        if goal:
            goal.status = new_status
            self.last_modified_at = datetime.now(timezone.utc).isoformat()
            return True
        return False

    @staticmethod
    def _clamp_bias(value: float) -> float:
        return max(-1.0, min(1.0, value))

    @staticmethod
    def _capability_level_to_bias(level: str) -> Optional[float]:
        mapping = {
            CapabilityLevel.NONE.value: -1.0,
            CapabilityLevel.BASIC.value: -0.5,
            CapabilityLevel.INTERMEDIATE.value: 0.0,
            CapabilityLevel.ADVANCED.value: 0.5,
            CapabilityLevel.EXPERT.value: 1.0,
        }
        return mapping.get(level)

    @staticmethod
    def _normalize_label(label: Optional[str]) -> str:
        if not label:
            return ""
        return label.strip().lower().replace(" ", "_")

    def _get_action_confidence_bias(self, action: str) -> Optional[float]:
        action = self._normalize_label(action)
        for key in (f"action:{action}", f"action.{action}"):
            if key in self.confidence_by_domain:
                return self._clamp_bias((float(self.confidence_by_domain[key]) * 2.0) - 1.0)
        return None

    def _get_action_capability_bias(self, action: str) -> Optional[float]:
        normalized_candidates = {
            action,
            f"action:{action}",
            f"action.{action}",
            f"social_{action}",
            f"social-{action}",
        }
        for capability in self.capabilities:
            normalized_labels = {
                self._normalize_label(capability.category),
                self._normalize_label(capability.capability_id),
                self._normalize_label(capability.name),
            }
            if normalized_candidates.intersection(normalized_labels):
                bias = self._capability_level_to_bias(capability.current_level)
                if bias is not None:
                    return bias
        return None

    def get_action_bias(self, action: str) -> float:
        """
        Return a minimal downstream decision bias for an action.

        Step04E chooses a conservative, owner-backed surface:
        - prefer explicit `confidence_by_domain["action:<action>"]`
        - optionally allow action-shaped capability categories

        This keeps MVP13 behavioral influence anchored to the converged
        formal owner contract without expanding the schema.
        """
        normalized_action = self._normalize_label(action)
        if not normalized_action:
            return 0.0

        components: List[float] = []

        confidence_bias = self._get_action_confidence_bias(normalized_action)
        if confidence_bias is not None:
            components.append(confidence_bias)

        capability_bias = self._get_action_capability_bias(normalized_action)
        if capability_bias is not None:
            components.append(capability_bias)

        if not components:
            return 0.0

        return self._clamp_bias(sum(components) / len(components))


def create_default_self_model(identity_handle: str) -> SelfModel:
    """创建默认自我模型"""
    return SelfModel(
        identity_handle=identity_handle,
        capabilities=[
            Capability(
                capability_id="cap_file_operations",
                name="文件操作",
                category="file_operations",
                current_level=CapabilityLevel.ADVANCED.value,
            ),
            Capability(
                capability_id="cap_code_execution",
                name="代码执行",
                category="code_execution",
                current_level=CapabilityLevel.ADVANCED.value,
            ),
            Capability(
                capability_id="cap_reasoning",
                name="推理",
                category="reasoning",
                current_level=CapabilityLevel.ADVANCED.value,
            ),
        ],
        limitations=[
            Limitation(
                limitation_id="lim_no_gui",
                description="无法直接操作 GUI 应用",
                impact_level="medium",
                workaround="通过 CLI 工具间接操作",
            ),
        ],
        current_allowed_tools=["read", "write", "edit", "exec"],
        confidence_by_domain={
            "file_operations": 0.95,
            "code_execution": 0.9,
            "reasoning": 0.85,
        },
    )

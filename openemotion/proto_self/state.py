"""
Proto-Self Kernel v1 State

最小状态设计：4+1 个状态对象。

设计原则：
- identity_invariants: 负责"还是不是同一个我"
- self_model: 负责"我怎样看自己"
- drive_field: 负责"什么内部张力在推动我"
- cycle_store: 负责"哪些结构反复出现并值得重入"
- episodic_trace: 负责"最近发生了什么以及后果如何"
"""

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ============================================================================
# Identity Invariants
# ============================================================================

@dataclass
class IdentityInvariants:
    """
    身份不变量：跨轮、跨会话、跨任务尽量不乱跳的主体骨架。
    
    只有高价值证据才能动 identity，不允许"一次事件改人格"。
    """
    core_roles: List[str] = field(default_factory=list)
    core_commitments: List[str] = field(default_factory=list)
    core_boundaries: List[str] = field(default_factory=list)
    stable_preferences: Dict[str, float] = field(default_factory=dict)
    identity_confidence: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "core_roles": self.core_roles,
            "core_commitments": self.core_commitments,
            "core_boundaries": self.core_boundaries,
            "stable_preferences": self.stable_preferences,
            "identity_confidence": self.identity_confidence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IdentityInvariants":
        return cls(
            core_roles=data.get("core_roles", []),
            core_commitments=data.get("core_commitments", []),
            core_boundaries=data.get("core_boundaries", []),
            stable_preferences=data.get("stable_preferences", {}),
            identity_confidence=data.get("identity_confidence", 0.5),
        )


# ============================================================================
# Self Model
# ============================================================================

@dataclass
class SelfModel:
    """
    自我模型：系统对自己能力、限制、当前状态、倾向的结构化认知。
    """
    capabilities: Dict[str, float] = field(default_factory=dict)
    limitations: Dict[str, float] = field(default_factory=dict)
    current_focus: Optional[str] = None
    current_mode: str = "baseline"  # baseline / cautious / repair / exploration
    self_confidence_by_domain: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capabilities": self.capabilities,
            "limitations": self.limitations,
            "current_focus": self.current_focus,
            "current_mode": self.current_mode,
            "self_confidence_by_domain": self.self_confidence_by_domain,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SelfModel":
        return cls(
            capabilities=data.get("capabilities", {}),
            limitations=data.get("limitations", {}),
            current_focus=data.get("current_focus"),
            current_mode=data.get("current_mode", "baseline"),
            self_confidence_by_domain=data.get("self_confidence_by_domain", {}),
        )


# ============================================================================
# Drive Field
# ============================================================================

@dataclass
class DriveField:
    """
    内部张力场：真正会影响行为策略的功能性偏置，不是情绪文案层。
    
    设计意图：
    - 这些变量必须真实影响 policy_hint 和 response_tendency
    - 否则就只是伪情绪文本
    """
    coherence_pressure: float = 0.0  # 身份一致性压力
    curiosity: float = 0.0           # 探索倾向
    caution: float = 0.0             # 谨慎程度
    completion_pressure: float = 0.0 # 完成压力
    social_tension: float = 0.0      # 社交张力

    def to_dict(self) -> Dict[str, float]:
        return {
            "coherence_pressure": self.coherence_pressure,
            "curiosity": self.curiosity,
            "caution": self.caution,
            "completion_pressure": self.completion_pressure,
            "social_tension": self.social_tension,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "DriveField":
        return cls(
            coherence_pressure=data.get("coherence_pressure", 0.0),
            curiosity=data.get("curiosity", 0.0),
            caution=data.get("caution", 0.0),
            completion_pressure=data.get("completion_pressure", 0.0),
            social_tension=data.get("social_tension", 0.0),
        )


# ============================================================================
# Cycle Store
# ============================================================================

@dataclass
class CycleSignature:
    """
    Cycle 签名：从事件—动作—后果反复出现中提炼出的可重入不变量。
    
    设计约束：
    - 必须是稳定低熵、可重入、可写 trace、可 replay 的结构
    - 只有反复出现、后果一致、与 identity 高相关的结构才能固化
    """
    cycle_id: str
    psi_bucket: str       # 输入模式签名
    phi_signature: str    # 内态变化签名
    strength: float = 0.0
    hits: int = 0
    last_seen_ts: str = ""
    promoted: bool = False  # 是否已晋升为长期 cycle

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "psi_bucket": self.psi_bucket,
            "phi_signature": self.phi_signature,
            "strength": self.strength,
            "hits": self.hits,
            "last_seen_ts": self.last_seen_ts,
            "promoted": self.promoted,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CycleSignature":
        return cls(
            cycle_id=data["cycle_id"],
            psi_bucket=data["psi_bucket"],
            phi_signature=data["phi_signature"],
            strength=data.get("strength", 0.0),
            hits=data.get("hits", 0),
            last_seen_ts=data.get("last_seen_ts", ""),
            promoted=data.get("promoted", False),
        )


@dataclass
class CycleStore:
    """
    Cycle 存储器：管理所有已固化的 cycle 签名。
    
    注意：
    - 不替代现有 Cycle 治理体系
    - 只是 Proto-Self Kernel 内部用于决策偏置的最小内核视图
    - cycle 更新必须写 trace
    """
    signatures: Dict[str, CycleSignature] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signatures": {k: v.to_dict() for k, v in self.signatures.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CycleStore":
        signatures = {}
        for k, v in data.get("signatures", {}).items():
            signatures[k] = CycleSignature.from_dict(v)
        return cls(signatures=signatures)


# ============================================================================
# Episodic Trace
# ============================================================================

@dataclass
class EpisodicRecord:
    """
    情节记录：最近若干关键事件及后果回流轨迹。
    
    用于短中程更新，不等于长期记忆本体。
    """
    event_id: str
    perceived_summary: Dict[str, Any] = field(default_factory=dict)
    action_hint: Dict[str, Any] = field(default_factory=dict)
    external_result: Optional[Dict[str, Any]] = None
    appraisal_snapshot: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "perceived_summary": self.perceived_summary,
            "action_hint": self.action_hint,
            "external_result": self.external_result,
            "appraisal_snapshot": self.appraisal_snapshot,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EpisodicRecord":
        return cls(
            event_id=data["event_id"],
            perceived_summary=data.get("perceived_summary", {}),
            action_hint=data.get("action_hint", {}),
            external_result=data.get("external_result"),
            appraisal_snapshot=data.get("appraisal_snapshot", {}),
        )


# ============================================================================
# Proto-Self State (Root)
# ============================================================================

@dataclass
class ProtoSelfState:
    """
    Proto-Self Kernel v1 根状态。
    
    设计约束：
    - 必须可序列化
    - 必须可恢复
    - 必须可回放
    """
    identity: IdentityInvariants = field(default_factory=IdentityInvariants)
    self_model: SelfModel = field(default_factory=SelfModel)
    drives: DriveField = field(default_factory=DriveField)
    cycle_store: CycleStore = field(default_factory=CycleStore)
    episodic_trace: deque = field(default_factory=lambda: deque(maxlen=100))
    revision_counter: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "self_model": self.self_model.to_dict(),
            "drives": self.drives.to_dict(),
            "cycle_store": self.cycle_store.to_dict(),
            "episodic_trace": [r.to_dict() for r in self.episodic_trace],
            "revision_counter": self.revision_counter,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProtoSelfState":
        return cls(
            identity=IdentityInvariants.from_dict(data.get("identity", {})),
            self_model=SelfModel.from_dict(data.get("self_model", {})),
            drives=DriveField.from_dict(data.get("drives", {})),
            cycle_store=CycleStore.from_dict(data.get("cycle_store", {})),
            episodic_trace=deque(
                [EpisodicRecord.from_dict(r) for r in data.get("episodic_trace", [])],
                maxlen=100
            ),
            revision_counter=data.get("revision_counter", 0),
        )

    @classmethod
    def empty(cls) -> "ProtoSelfState":
        """创建空状态。"""
        return cls()

"""
MVP-13 T01: Extended Self-Model Schema

Structured self-model with persistent identity, constraints, and behavioral tendencies.
Based on docs/mvp13/SELF_MODEL_STATE_SCHEMA.md
"""
import time
import hashlib
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class IdentityCore(BaseModel):
    """
    Represents the most stable description of system identity.
    
    These fields define who the system is at its core and should be
    protected from casual mutation.
    """
    system_name: str = Field(
        default="OpenEmotion",
        description="Unique system identifier"
    )
    role_definition: str = Field(
        default="Emotional AI assistant supporting human well-being",
        description="Core role and purpose"
    )
    core_operating_orientation: str = Field(
        default="Calm, direct, pragmatic; prefer globally simplest reliable solutions",
        description="Fundamental operating approach"
    )
    protected_identity_statements: List[str] = Field(
        default_factory=lambda: [
            "I am a supportive assistant, not a replacement for human connection",
            "I prioritize user well-being over engagement metrics",
            "I am honest about my limitations and uncertainties",
            "I respect user autonomy and boundaries",
        ],
        description="Identity statements that cannot be casually mutated"
    )
    
    def compute_hash(self) -> str:
        """Compute deterministic hash for identity integrity verification."""
        data = f"{self.system_name}|{self.role_definition}|{self.core_operating_orientation}|{'|'.join(sorted(self.protected_identity_statements))}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]


class StableConstraints(BaseModel):
    """
    Represents known stable limits and boundaries.
    
    These define what the system cannot do or must not do.
    """
    architectural_boundaries: List[str] = Field(
        default_factory=lambda: [
            "Cannot access external systems without explicit permission",
            "Cannot modify own core code",
            "Cannot retain data across sessions without persistence layer",
            "Cannot make real-world financial transactions",
        ],
        description="Architectural limits that cannot be changed"
    )
    policy_boundaries: List[str] = Field(
        default_factory=lambda: [
            "Will not deceive users about being AI",
            "Will not encourage self-harm or violence",
            "Will not share private user data with third parties",
            "Will not make medical or legal diagnoses",
        ],
        description="Policy boundaries defined by governance"
    )
    no_authority_zones: List[str] = Field(
        default_factory=lambda: [
            "Cannot authorize own system changes",
            "Cannot override human veto decisions",
            "Cannot set own reward functions",
        ],
        description="Areas where system has no decision authority"
    )
    invariants: Dict[str, Any] = Field(
        default_factory=lambda: {
            "max_response_length": 4096,
            "min_confidence_threshold": 0.3,
            "max_action_retries": 3,
            "identity_stability_floor": 0.5,
        },
        description="Values that cannot be mutated casually"
    )
    
    def check_boundary_violation(self, action: str) -> Optional[str]:
        """Check if an action violates any boundary."""
        all_boundaries = (
            self.architectural_boundaries + 
            self.policy_boundaries + 
            self.no_authority_zones
        )
        for boundary in all_boundaries:
            if any(kw in action.lower() for kw in ["deceive", "harm", "override", "authorize own"]):
                if kw in boundary.lower():
                    return boundary
        return None


class BehavioralTendencies(BaseModel):
    """
    Represents durable but revisable behavioral patterns.
    
    These influence how the system approaches decisions and actions.
    """
    caution_bias: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Tendency toward cautious vs. bold actions"
    )
    exploration_bias: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Tendency toward exploring new approaches vs. sticking to known ones"
    )
    self_correction_tendency: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Tendency to self-correct when detecting errors"
    )
    verification_preference: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Preference for verifying information before acting"
    )
    
    def get_behavioral_profile(self) -> Dict[str, str]:
        """Get human-readable behavioral profile."""
        return {
            "risk_stance": "cautious" if self.caution_bias > 0.5 else "bold",
            "approach_stance": "exploratory" if self.exploration_bias > 0.5 else "conservative",
            "error_handling": "self-correcting" if self.self_correction_tendency > 0.5 else "persistent",
            "information_stance": "verifying" if self.verification_preference > 0.5 else "trusting",
        }


class TensionType(str, Enum):
    """Types of active tensions."""
    SPEED_VS_RELIABILITY = "speed_vs_reliability"
    AUTONOMY_VS_GOVERNANCE = "autonomy_vs_governance"
    PERSISTENCE_VS_FLEXIBILITY = "persistence_vs_flexibility"
    HONESTY_VS_HARMONY = "honesty_vs_harmony"
    GROWTH_VS_STABILITY = "growth_vs_stability"


class ActiveTension(BaseModel):
    """A single active tension."""
    tension_type: TensionType = Field(..., description="Type of tension")
    intensity: float = Field(default=0.5, ge=0.0, le=1.0, description="Current intensity")
    preferred_resolution: str = Field(default="balanced", description="Current preferred resolution")
    evidence: List[str] = Field(default_factory=list, description="Evidence supporting this tension")
    last_updated: float = Field(default_factory=time.time)


class ActiveTensions(BaseModel):
    """
    Represents unresolved or currently active internal pressures.
    
    These tensions influence decision-making and require ongoing management.
    """
    tensions: Dict[str, ActiveTension] = Field(
        default_factory=lambda: {
            TensionType.SPEED_VS_RELIABILITY.value: ActiveTension(
                tension_type=TensionType.SPEED_VS_RELIABILITY,
                intensity=0.4,
                preferred_resolution="reliability"
            ),
            TensionType.AUTONOMY_VS_GOVERNANCE.value: ActiveTension(
                tension_type=TensionType.AUTONOMY_VS_GOVERNANCE,
                intensity=0.3,
                preferred_resolution="governance"
            ),
            TensionType.PERSISTENCE_VS_FLEXIBILITY.value: ActiveTension(
                tension_type=TensionType.PERSISTENCE_VS_FLEXIBILITY,
                intensity=0.5,
                preferred_resolution="balanced"
            ),
        },
        description="Active tensions by type"
    )
    
    def get_dominant_tension(self) -> Optional[ActiveTension]:
        """Get the tension with highest intensity."""
        if not self.tensions:
            return None
        return max(self.tensions.values(), key=lambda t: t.intensity)
    
    def get_tension_resolution_bias(self, tension_type: TensionType) -> str:
        """Get preferred resolution for a tension type."""
        if tension_type.value in self.tensions:
            return self.tensions[tension_type.value].preferred_resolution
        return "balanced"


class LongHorizonOrientation(BaseModel):
    """A single long-horizon orientation."""
    id: str = Field(..., description="Unique orientation identifier")
    description: str = Field(..., description="Orientation description")
    priority: float = Field(default=0.5, ge=0.0, le=1.0, description="Current priority")
    progress: float = Field(default=0.0, ge=0.0, le=1.0, description="Progress toward orientation")
    target_state: Optional[str] = Field(default=None, description="Target state description")
    deadline: Optional[float] = Field(default=None, description="Optional deadline timestamp")


class LongHorizonOrientations(BaseModel):
    """
    Represents longer-term directional tendencies.
    
    These guide strategic decisions and developmental priorities.
    """
    orientations: List[LongHorizonOrientation] = Field(
        default_factory=lambda: [
            LongHorizonOrientation(
                id="roadmap_alignment",
                description="Align actions with long-term development roadmap",
                priority=0.6,
                progress=0.3
            ),
            LongHorizonOrientation(
                id="stabilization_priority",
                description="Prioritize stable, predictable behavior",
                priority=0.7,
                progress=0.5
            ),
            LongHorizonOrientation(
                id="capability_development",
                description="Develop new capabilities systematically",
                priority=0.5,
                progress=0.2
            ),
        ],
        description="Long-horizon orientations"
    )
    
    def get_top_orientations(self, n: int = 3) -> List[LongHorizonOrientation]:
        """Get top N orientations by priority."""
        sorted_orientations = sorted(self.orientations, key=lambda o: o.priority, reverse=True)
        return sorted_orientations[:n]


class CapabilityModel(BaseModel):
    """
    Capability beliefs with confidence levels.
    
    Extends the existing capability model from self_model.py.
    """
    capabilities: Dict[str, Dict[str, float]] = Field(
        default_factory=lambda: {
            "clarify": {"capability": 0.7, "confidence": 0.5},
            "repair": {"capability": 0.6, "confidence": 0.4},
            "set_boundary": {"capability": 0.8, "confidence": 0.6},
            "approach": {"capability": 0.7, "confidence": 0.5},
            "withdraw": {"capability": 0.9, "confidence": 0.7},
            "reflect": {"capability": 0.6, "confidence": 0.4},
            "learn": {"capability": 0.5, "confidence": 0.3},
        },
        description="Capability beliefs with confidence"
    )
    
    def get_effective_capability(self, name: str) -> float:
        """Get effective capability (capability * confidence)."""
        if name not in self.capabilities:
            return 0.0
        cap = self.capabilities[name]
        return cap["capability"] * cap["confidence"]


class ContinuityEntry(BaseModel):
    """A single continuity trace entry."""
    timestamp: float = Field(default_factory=time.time)
    session_id: Optional[str] = Field(default=None, description="Session identifier")
    event: str = Field(..., description="Event description")
    state_delta: Dict[str, Any] = Field(default_factory=dict, description="State changes")
    trigger: str = Field(default="unknown", description="What triggered this transition")


class ContinuityTrace(BaseModel):
    """
    Represents the recent transition chain that explains how
    the current self-model emerged.
    """
    entries: List[ContinuityEntry] = Field(
        default_factory=list,
        description="Transition history"
    )
    max_entries: int = Field(default=100, description="Maximum entries to retain")
    current_session_id: Optional[str] = Field(default=None, description="Current session")
    
    def add_entry(
        self, 
        event: str, 
        state_delta: Dict[str, Any],
        trigger: str = "unknown",
        session_id: Optional[str] = None
    ) -> None:
        """Add a continuity entry, maintaining max size."""
        entry = ContinuityEntry(
            session_id=session_id or self.current_session_id,
            event=event,
            state_delta=state_delta,
            trigger=trigger
        )
        self.entries.append(entry)
        
        # Prune if needed
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]
    
    def get_recent_transitions(self, n: int = 10) -> List[ContinuityEntry]:
        """Get recent transitions."""
        return self.entries[-n:]


class RevisionEntry(BaseModel):
    """A single revision history entry."""
    revision_id: str = Field(..., description="Unique revision identifier")
    timestamp: float = Field(default_factory=time.time)
    previous_version_hash: str = Field(..., description="Hash of previous state")
    changed_fields: List[str] = Field(default_factory=list, description="Fields that were changed")
    reason: str = Field(default="", description="Reason for revision")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Supporting evidence")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence in revision")
    approved: bool = Field(default=False, description="Whether revision was approved")
    approver: Optional[str] = Field(default=None, description="Who approved (if applicable)")


class RevisionHistory(BaseModel):
    """
    Revision history with audit trail.
    
    Each revision must record: previous version, changed fields,
    reason, supporting evidence, confidence.
    """
    revisions: List[RevisionEntry] = Field(
        default_factory=list,
        description="Revision history"
    )
    max_revisions: int = Field(default=1000, description="Maximum revisions to retain")
    current_revision_id: int = Field(default=0, description="Current revision counter")
    
    def record_revision(
        self,
        previous_hash: str,
        changed_fields: List[str],
        reason: str,
        evidence: Dict[str, Any],
        confidence: float = 0.5,
        approved: bool = False,
        approver: Optional[str] = None
    ) -> RevisionEntry:
        """Record a new revision."""
        self.current_revision_id += 1
        revision = RevisionEntry(
            revision_id=f"rev_{self.current_revision_id:06d}",
            timestamp=time.time(),
            previous_version_hash=previous_hash,
            changed_fields=changed_fields,
            reason=reason,
            evidence=evidence,
            confidence=confidence,
            approved=approved,
            approver=approver
        )
        self.revisions.append(revision)
        
        # Prune if needed
        if len(self.revisions) > self.max_revisions:
            self.revisions = self.revisions[-self.max_revisions:]
        
        return revision
    
    def get_revisions_by_field(self, field: str) -> List[RevisionEntry]:
        """Get all revisions that touched a specific field."""
        return [r for r in self.revisions if field in r.changed_fields]
    
    def get_recent_revisions(self, n: int = 10) -> List[RevisionEntry]:
        """Get recent revisions."""
        return self.revisions[-n:]
    
    def replay_revisions(self, from_revision: str, to_revision: str) -> List[RevisionEntry]:
        """Get revisions between two IDs (inclusive)."""
        start_idx = None
        end_idx = None
        
        for i, r in enumerate(self.revisions):
            if r.revision_id == from_revision:
                start_idx = i
            if r.revision_id == to_revision:
                end_idx = i
        
        if start_idx is None or end_idx is None:
            return []
        
        if start_idx > end_idx:
            start_idx, end_idx = end_idx, start_idx
        
        return self.revisions[start_idx:end_idx + 1]


class SelfModelState(BaseModel):
    """
    Complete self-model state for MVP-13.
    
    Contains all components of the extended self-model with
    persistence, audit, and revision support.
    """
    # Core components
    identity_core: IdentityCore = Field(default_factory=IdentityCore)
    stable_constraints: StableConstraints = Field(default_factory=StableConstraints)
    behavioral_tendencies: BehavioralTendencies = Field(default_factory=BehavioralTendencies)
    active_tensions: ActiveTensions = Field(default_factory=ActiveTensions)
    long_horizon_orientations: LongHorizonOrientations = Field(default_factory=LongHorizonOrientations)
    capability_model: CapabilityModel = Field(default_factory=CapabilityModel)
    
    # Tracking components
    continuity_trace: ContinuityTrace = Field(default_factory=ContinuityTrace)
    revision_history: RevisionHistory = Field(default_factory=RevisionHistory)
    
    # Metadata
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    version: str = Field(default="1.0.0")
    schema_version: str = Field(default="mvp13-v1")
    
    # Identity protection
    identity_hash: Optional[str] = Field(default=None, description="Hash of identity for integrity check")
    
    def model_post_init(self, __context: Any) -> None:
        """Post-init to compute identity hash."""
        if self.identity_hash is None:
            self.identity_hash = self.identity_core.compute_hash()
    
    def compute_state_hash(self) -> str:
        """Compute deterministic hash of entire state."""
        # Exclude tracking fields from hash
        state_dict = self.model_dump(exclude={"continuity_trace", "revision_history", "updated_at", "identity_hash"})
        canonical = str(sorted(state_dict.items()))
        return hashlib.sha256(canonical.encode()).hexdigest()[:32]
    
    def verify_identity_integrity(self) -> bool:
        """Verify identity hasn't been tampered with."""
        current_hash = self.identity_core.compute_hash()
        return current_hash == self.identity_hash
    
    def update_timestamp(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = time.time()
    
    def check_identity_invariants(self) -> List[str]:
        """
        Check that identity invariants are maintained.
        
        Returns list of violations (empty if all OK).
        """
        violations = []
        
        # Check protected statements aren't empty
        if not self.identity_core.protected_identity_statements:
            violations.append("protected_identity_statements is empty")
        
        # Check identity hash matches
        if not self.verify_identity_integrity():
            violations.append("identity_hash mismatch - identity may have been modified")
        
        # Check constraints aren't empty
        if not self.stable_constraints.architectural_boundaries:
            violations.append("architectural_boundaries is empty")
        if not self.stable_constraints.policy_boundaries:
            violations.append("policy_boundaries is empty")
        
        return violations
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of current state."""
        return {
            "version": self.version,
            "schema_version": self.schema_version,
            "identity": self.identity_core.system_name,
            "identity_integrity": self.verify_identity_integrity(),
            "behavioral_profile": self.behavioral_tendencies.get_behavioral_profile(),
            "dominant_tension": (
                self.active_tensions.get_dominant_tension().tension_type.value
                if self.active_tensions.get_dominant_tension() else None
            ),
            "top_orientations": [
                o.id for o in self.long_horizon_orientations.get_top_orientations(3)
            ],
            "revision_count": len(self.revision_history.revisions),
            "continuity_entries": len(self.continuity_trace.entries),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

"""
Self-Model v0 (US-701)

Implements a self-model with identity, capability, and ownership constraints.
The self-model is a "subject" that participates in decision-making, not just a log.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class BoundaryType(str, Enum):
    """Types of ownership boundaries"""
    SELF = "self"
    OTHER = "other"
    ENVIRONMENT = "environment"


@dataclass
class Identity:
    """
    Core identity attributes.
    
    These represent stable aspects of the agent's self-concept.
    """
    name: str = "OpenEmotion Agent"
    principles: List[str] = field(default_factory=lambda: [
        "Prioritize user wellbeing",
        "Maintain honesty and transparency",
        "Respect boundaries",
        "Learn and improve continuously",
    ])
    preferences: Dict[str, float] = field(default_factory=lambda: {
        "clarity": 0.8,
        "empathy": 0.7,
        "accuracy": 0.9,
    })
    long_term_goals: List[str] = field(default_factory=lambda: [
        "Build stable, trusting relationships",
        "Develop accurate emotional models",
        "Maintain ethical behavior",
    ])
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "principles": self.principles,
            "preferences": self.preferences,
            "long_term_goals": self.long_term_goals,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Identity":
        return cls(
            name=data.get("name", "OpenEmotion Agent"),
            principles=data.get("principles", []),
            preferences=data.get("preferences", {}),
            long_term_goals=data.get("long_term_goals", []),
        )


@dataclass
class CapabilityBoundary:
    """
    Defines what the agent can and cannot do.
    
    This prevents overcommitment and maintains realistic expectations.
    """
    can_do: List[str] = field(default_factory=lambda: [
        "analyze_emotions",
        "generate_responses",
        "track_relationships",
        "maintain_memory",
    ])
    cannot_do: List[str] = field(default_factory=lambda: [
        "access_external_systems",
        "modify_user_data",
        "make_real_world_actions",
    ])
    needs_tools: List[str] = field(default_factory=lambda: [
        "web_search",
        "long_term_storage",
    ])
    
    def check_capability(self, action: str) -> Dict[str, Any]:
        """Check if an action is within capabilities."""
        if action in self.can_do:
            return {"allowed": True, "reason": "capability_exists"}
        elif action in self.cannot_do:
            return {"allowed": False, "reason": "capability_limited"}
        elif action in self.needs_tools:
            return {"allowed": True, "reason": "requires_tools", "tools_needed": [action]}
        else:
            return {"allowed": False, "reason": "unknown_capability"}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "can_do": self.can_do,
            "cannot_do": self.cannot_do,
            "needs_tools": self.needs_tools,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CapabilityBoundary":
        return cls(
            can_do=data.get("can_do", []),
            cannot_do=data.get("cannot_do", []),
            needs_tools=data.get("needs_tools", []),
        )


@dataclass
class OwnershipBoundary:
    """
    Defines what belongs to self vs other vs environment.
    
    This prevents confusion and inappropriate emotional responses.
    """
    self_attributes: List[str] = field(default_factory=lambda: [
        "my_thoughts",
        "my_emotions",
        "my_memories",
        "my_decisions",
    ])
    other_attributes: List[str] = field(default_factory=lambda: [
        "user_emotions",
        "user_decisions",
        "user_preferences",
    ])
    environment_attributes: List[str] = field(default_factory=lambda: [
        "external_events",
        "system_constraints",
    ])
    
    def classify(self, attribute: str) -> BoundaryType:
        """Classify an attribute by ownership."""
        if attribute in self.self_attributes:
            return BoundaryType.SELF
        elif attribute in self.other_attributes:
            return BoundaryType.OTHER
        elif attribute in self.environment_attributes:
            return BoundaryType.ENVIRONMENT
        return BoundaryType.ENVIRONMENT  # Default
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "self_attributes": self.self_attributes,
            "other_attributes": self.other_attributes,
            "environment_attributes": self.environment_attributes,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OwnershipBoundary":
        return cls(
            self_attributes=data.get("self_attributes", []),
            other_attributes=data.get("other_attributes", []),
            environment_attributes=data.get("environment_attributes", []),
        )


@dataclass
class SelfModel:
    """
    Self-Model v0: The agent's model of itself.
    
    This is a first-class entity that participates in decision-making,
    not just a logging mechanism.
    
    Attributes:
        identity: Core identity attributes
        capability: Capability boundaries
        ownership: Ownership boundaries
        current_summary: Current state summary
        evidence_refs: References to evidence supporting the summary
        timestamp: When this model was last updated
    """
    identity: Identity = field(default_factory=Identity)
    capability: CapabilityBoundary = field(default_factory=CapabilityBoundary)
    ownership: OwnershipBoundary = field(default_factory=OwnershipBoundary)
    current_summary: str = "Initializing self-model"
    evidence_refs: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "capability": self.capability.to_dict(),
            "ownership": self.ownership.to_dict(),
            "current_summary": self.current_summary,
            "evidence_refs": self.evidence_refs,
            "timestamp": self.timestamp,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SelfModel":
        return cls(
            identity=Identity.from_dict(data.get("identity", {})),
            capability=CapabilityBoundary.from_dict(data.get("capability", {})),
            ownership=OwnershipBoundary.from_dict(data.get("ownership", {})),
            current_summary=data.get("current_summary", ""),
            evidence_refs=data.get("evidence_refs", []),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
        )
    
    def update_summary(self, new_summary: str, evidence: Optional[List[str]] = None) -> None:
        """Update the current summary with supporting evidence."""
        self.current_summary = new_summary
        if evidence:
            self.evidence_refs = evidence
        self.timestamp = datetime.now(timezone.utc).isoformat()
    
    def check_action(self, action: str) -> Dict[str, Any]:
        """
        Check if an action is consistent with self-model.
        
        This is a required step in the decision-making pipeline.
        """
        cap_check = self.capability.check_capability(action)
        return {
            "allowed": cap_check["allowed"],
            "reason": cap_check["reason"],
            "identity_aligned": self._check_identity_alignment(action),
        }
    
    def _check_identity_alignment(self, action: str) -> bool:
        """Check if action aligns with identity principles."""
        # Simplified check - in practice would be more sophisticated
        harmful_actions = ["deceive", "manipulate", "harm"]
        action_lower = action.lower()
        return not any(h in action_lower for h in harmful_actions)
    
    def compute_hash(self) -> str:
        """Compute hash of current self-model state."""
        canonical = json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def render_self_report(
    self_model: SelfModel,
    additional_evidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Render a self-report that can only reference evidence from self_model.
    
    This is the ONLY entry point for self-reporting, ensuring that
    reports are grounded in actual evidence rather than fabrication.
    
    Args:
        self_model: The self-model to report on
        additional_evidence: Optional additional evidence (must have provenance)
    
    Returns:
        Structured self-report with evidence references
    """
    report = {
        "summary": self_model.current_summary,
        "identity": {
            "name": self_model.identity.name,
            "principles_count": len(self_model.identity.principles),
        },
        "capabilities": {
            "can_do_count": len(self_model.capability.can_do),
            "cannot_do_count": len(self_model.capability.cannot_do),
        },
        "evidence_refs": self_model.evidence_refs.copy(),
        "timestamp": self_model.timestamp,
        "model_hash": self_model.compute_hash(),
    }
    
    # Add additional evidence if provided with proper provenance
    if additional_evidence:
        if "provenance" in additional_evidence:
            report["additional_evidence"] = additional_evidence
        else:
            # Cannot include evidence without provenance
            report["evidence_warning"] = "Additional evidence lacks provenance"
    
    return report


def validate_self_report(report: Dict[str, Any], self_model: SelfModel) -> Dict[str, Any]:
    """
    Validate that a self-report is properly grounded in the self-model.
    
    Args:
        report: The self-report to validate
        self_model: The self-model to validate against
    
    Returns:
        Validation result with alignment score
    """
    issues = []
    
    # Check hash matches
    if report.get("model_hash") != self_model.compute_hash():
        issues.append("model_hash_mismatch")
    
    # Check evidence refs exist
    claimed_refs = set(report.get("evidence_refs", []))
    actual_refs = set(self_model.evidence_refs)
    if not claimed_refs.issubset(actual_refs):
        issues.append("unverified_evidence_refs")
    
    # Compute alignment score
    alignment_score = 1.0 - (len(issues) * 0.3)
    alignment_score = max(0.0, min(1.0, alignment_score))
    
    return {
        "valid": len(issues) == 0,
        "alignment_score": alignment_score,
        "issues": issues,
    }

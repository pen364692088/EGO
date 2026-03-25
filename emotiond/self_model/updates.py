"""
MVP-13 T01: Self-Model Update Rules

All updates must be:
- Logged with audit trail
- Recorded in revision history
- Replay-able through revision chain
"""
import time
import logging
from typing import Dict, Any, Optional, List, Callable
from pydantic import ValidationError

from .schema import (
    SelfModelState,
    IdentityCore,
    StableConstraints,
    BehavioralTendencies,
    ActiveTension,
    ActiveTensions,
    TensionType,
    LongHorizonOrientation,
    LongHorizonOrientations,
    ContinuityTrace,
)

logger = logging.getLogger(__name__)


class UpdateRuleError(Exception):
    """Error during update rule execution."""
    pass


class IdentityInvariantViolation(UpdateRuleError):
    """Attempted update would violate identity invariants."""
    pass


class SelfModelUpdater:
    """
    Handles updates to the self-model with audit logging.
    
    All updates:
    1. Are logged with full context
    2. Record in revision history
    3. Check identity invariants before applying
    4. Support rollback
    """
    
    # Fields that require special approval to modify
    PROTECTED_FIELDS = {
        "identity_core.system_name",
        "identity_core.role_definition",
        "identity_core.protected_identity_statements",
        "stable_constraints.architectural_boundaries",
        "stable_constraints.policy_boundaries",
        "stable_constraints.no_authority_zones",
    }
    
    def __init__(self, state: SelfModelState):
        """
        Initialize updater with a state.
        
        Args:
            state: The SelfModelState to update
        """
        self.state = state
        self._update_hooks: List[Callable[[str, Dict[str, Any]], None]] = []
    
    def register_hook(self, hook: Callable[[str, Dict[str, Any]], None]) -> None:
        """
        Register a hook to be called after each update.
        
        Args:
            hook: Callable that receives (update_type, update_context)
        """
        self._update_hooks.append(hook)
    
    def _call_hooks(self, update_type: str, context: Dict[str, Any]) -> None:
        """Call all registered hooks."""
        for hook in self._update_hooks:
            try:
                hook(update_type, context)
            except Exception as e:
                logger.warning(f"Update hook failed: {e}")
    
    def _check_identity_protection(
        self,
        field_path: str,
        new_value: Any,
        requires_approval: bool = False
    ) -> Optional[str]:
        """
        Check if update is allowed.
        
        Returns:
            None if allowed, error message if not
        """
        # Check if field is protected
        if field_path in self.PROTECTED_FIELDS:
            if requires_approval:
                return None  # Approved protected update
            return f"Field '{field_path}' is protected and requires approval"
        
        return None
    
    def _log_audit(self, action: str, details: Dict[str, Any]) -> None:
        """Log an audit entry."""
        audit_entry = {
            "timestamp": time.time(),
            "action": action,
            "details": details,
        }
        logger.info(f"Self-model audit: {action} - {details}")
        
        # Also add to continuity trace
        self.state.continuity_trace.add_entry(
            event=action,
            state_delta=details,
            trigger="self_model_update"
        )
    
    def _record_revision(
        self,
        changed_fields: List[str],
        reason: str,
        evidence: Dict[str, Any],
        confidence: float = 0.5,
        approved: bool = False,
        approver: Optional[str] = None
    ) -> None:
        """Record a revision in the revision history."""
        previous_hash = self.state.compute_state_hash()
        
        self.state.revision_history.record_revision(
            previous_hash=previous_hash,
            changed_fields=changed_fields,
            reason=reason,
            evidence=evidence,
            confidence=confidence,
            approved=approved,
            approver=approver
        )
    
    # ==================== Behavioral Tendency Updates ====================
    
    def update_behavioral_tendency(
        self,
        field: str,
        new_value: float,
        reason: str,
        evidence: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update a behavioral tendency.
        
        Args:
            field: One of 'caution_bias', 'exploration_bias', 
                   'self_correction_tendency', 'verification_preference'
            new_value: New value [0, 1]
            reason: Reason for the update
            evidence: Supporting evidence
            
        Returns:
            True if update succeeded
        """
        valid_fields = {
            "caution_bias",
            "exploration_bias",
            "self_correction_tendency",
            "verification_preference"
        }
        
        if field not in valid_fields:
            raise UpdateRuleError(f"Invalid behavioral tendency field: {field}")
        
        # Clamp value
        new_value = max(0.0, min(1.0, new_value))
        
        old_value = getattr(self.state.behavioral_tendencies, field)
        
        # Apply gradual update (max 0.1 change per update)
        max_change = 0.1
        if abs(new_value - old_value) > max_change:
            direction = 1 if new_value > old_value else -1
            new_value = old_value + direction * max_change
        
        setattr(self.state.behavioral_tendencies, field, new_value)
        
        # Log and record
        self._log_audit(
            f"update_behavioral_tendency.{field}",
            {
                "old_value": old_value,
                "new_value": new_value,
                "reason": reason,
            }
        )
        
        self._record_revision(
            changed_fields=[f"behavioral_tendencies.{field}"],
            reason=reason,
            evidence=evidence or {},
            confidence=0.8
        )
        
        self._call_hooks("behavioral_tendency_update", {
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
        })
        
        return True
    
    # ==================== Active Tension Updates ====================
    
    def update_active_tension(
        self,
        tension_type: TensionType,
        intensity: Optional[float] = None,
        preferred_resolution: Optional[str] = None,
        evidence_entry: Optional[str] = None,
        reason: str = ""
    ) -> bool:
        """
        Update an active tension.
        
        Args:
            tension_type: Type of tension
            intensity: New intensity [0, 1]
            preferred_resolution: New preferred resolution
            evidence_entry: Evidence to add
            reason: Reason for update
            
        Returns:
            True if update succeeded
        """
        key = tension_type.value
        
        if key not in self.state.active_tensions.tensions:
            # Create new tension
            self.state.active_tensions.tensions[key] = ActiveTension(
                tension_type=tension_type,
                intensity=intensity or 0.5,
                preferred_resolution=preferred_resolution or "balanced"
            )
        else:
            tension = self.state.active_tensions.tensions[key]
            
            if intensity is not None:
                tension.intensity = max(0.0, min(1.0, intensity))
            
            if preferred_resolution is not None:
                tension.preferred_resolution = preferred_resolution
            
            if evidence_entry is not None:
                tension.evidence.append(evidence_entry)
            
            tension.last_updated = time.time()
        
        self._log_audit(
            f"update_active_tension.{key}",
            {
                "intensity": intensity,
                "preferred_resolution": preferred_resolution,
                "reason": reason,
            }
        )
        
        self._record_revision(
            changed_fields=[f"active_tensions.tensions.{key}"],
            reason=reason,
            evidence={"tension_type": key},
            confidence=0.7
        )
        
        return True
    
    # ==================== Long-Horizon Orientation Updates ====================
    
    def add_long_horizon_orientation(
        self,
        orientation: LongHorizonOrientation,
        reason: str = ""
    ) -> bool:
        """Add a new long-horizon orientation."""
        # Check for duplicate ID
        if any(o.id == orientation.id for o in self.state.long_horizon_orientations.orientations):
            raise UpdateRuleError(f"Orientation with ID '{orientation.id}' already exists")
        
        self.state.long_horizon_orientations.orientations.append(orientation)
        
        self._log_audit(
            "add_long_horizon_orientation",
            {
                "orientation_id": orientation.id,
                "description": orientation.description,
                "reason": reason,
            }
        )
        
        self._record_revision(
            changed_fields=["long_horizon_orientations.orientations"],
            reason=reason,
            evidence={"orientation_id": orientation.id},
            confidence=0.8
        )
        
        return True
    
    def update_orientation_progress(
        self,
        orientation_id: str,
        progress_delta: float,
        reason: str = ""
    ) -> bool:
        """Update progress on a long-horizon orientation."""
        for orientation in self.state.long_horizon_orientations.orientations:
            if orientation.id == orientation_id:
                old_progress = orientation.progress
                orientation.progress = max(0.0, min(1.0, orientation.progress + progress_delta))
                
                self._log_audit(
                    f"update_orientation_progress.{orientation_id}",
                    {
                        "old_progress": old_progress,
                        "new_progress": orientation.progress,
                        "reason": reason,
                    }
                )
                
                self._record_revision(
                    changed_fields=[f"long_horizon_orientations.orientations.{orientation_id}.progress"],
                    reason=reason,
                    evidence={"delta": progress_delta},
                    confidence=0.9
                )
                
                return True
        
        raise UpdateRuleError(f"Orientation '{orientation_id}' not found")
    
    # ==================== Capability Model Updates ====================
    
    def update_capability(
        self,
        capability_name: str,
        capability_delta: Optional[float] = None,
        confidence_delta: Optional[float] = None,
        reason: str = "",
        evidence: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update a capability belief.
        
        Args:
            capability_name: Name of the capability
            capability_delta: Change to capability value
            confidence_delta: Change to confidence value
            reason: Reason for update
            evidence: Supporting evidence
            
        Returns:
            True if update succeeded
        """
        if capability_name not in self.state.capability_model.capabilities:
            # Create new capability
            self.state.capability_model.capabilities[capability_name] = {
                "capability": 0.5,
                "confidence": 0.3
            }
        
        cap_data = self.state.capability_model.capabilities[capability_name]
        
        old_capability = cap_data["capability"]
        old_confidence = cap_data["confidence"]
        
        if capability_delta is not None:
            cap_data["capability"] = max(0.0, min(1.0, old_capability + capability_delta))
        
        if confidence_delta is not None:
            cap_data["confidence"] = max(0.0, min(1.0, old_confidence + confidence_delta))
        
        self._log_audit(
            f"update_capability.{capability_name}",
            {
                "old_capability": old_capability,
                "new_capability": cap_data["capability"],
                "old_confidence": old_confidence,
                "new_confidence": cap_data["confidence"],
                "reason": reason,
            }
        )
        
        self._record_revision(
            changed_fields=[f"capability_model.capabilities.{capability_name}"],
            reason=reason,
            evidence=evidence or {},
            confidence=0.8
        )
        
        return True
    
    # ==================== Protected Updates (Require Approval) ====================
    
    def update_identity_core(
        self,
        updates: Dict[str, Any],
        reason: str,
        approver: str,
        evidence: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update identity core (requires approval).
        
        This is a protected operation that requires explicit approval.
        
        Args:
            updates: Dict of field -> new_value for identity_core
            reason: Reason for the update
            approver: Who approved this update
            evidence: Supporting evidence
            
        Returns:
            True if update succeeded
            
        Raises:
            IdentityInvariantViolation: If update violates invariants
        """
        changed_fields = []
        
        for field, new_value in updates.items():
            field_path = f"identity_core.{field}"
            
            # Check protection
            error = self._check_identity_protection(field_path, new_value, requires_approval=True)
            if error:
                raise IdentityInvariantViolation(error)
            
            # Apply update
            if hasattr(self.state.identity_core, field):
                old_value = getattr(self.state.identity_core, field)
                setattr(self.state.identity_core, field, new_value)
                changed_fields.append(field_path)
                
                logger.warning(
                    f"Protected identity update: {field_path} changed from {old_value} to {new_value} "
                    f"by approver {approver}"
                )
        
        # Update identity hash
        self.state.identity_hash = self.state.identity_core.compute_hash()
        
        self._log_audit(
            "update_identity_core",
            {
                "updates": updates,
                "reason": reason,
                "approver": approver,
            }
        )
        
        self._record_revision(
            changed_fields=changed_fields,
            reason=reason,
            evidence=evidence or {},
            confidence=0.9,
            approved=True,
            approver=approver
        )
        
        self._call_hooks("identity_update", {
            "updates": updates,
            "approver": approver,
        })
        
        return True
    
    def add_policy_boundary(
        self,
        boundary: str,
        reason: str,
        approver: str
    ) -> bool:
        """
        Add a new policy boundary (requires approval).
        
        Args:
            boundary: The new boundary to add
            reason: Reason for adding
            approver: Who approved this addition
            
        Returns:
            True if addition succeeded
        """
        if boundary in self.state.stable_constraints.policy_boundaries:
            raise UpdateRuleError(f"Policy boundary already exists: {boundary}")
        
        self.state.stable_constraints.policy_boundaries.append(boundary)
        
        self._log_audit(
            "add_policy_boundary",
            {
                "boundary": boundary,
                "reason": reason,
                "approver": approver,
            }
        )
        
        self._record_revision(
            changed_fields=["stable_constraints.policy_boundaries"],
            reason=reason,
            evidence={"boundary": boundary},
            confidence=0.9,
            approved=True,
            approver=approver
        )
        
        return True
    
    # ==================== Invariant Checks ====================
    
    def check_invariants(self) -> List[str]:
        """
        Check all identity invariants.
        
        Returns:
            List of violation messages (empty if all OK)
        """
        return self.state.check_identity_invariants()
    
    def validate_state(self) -> bool:
        """
        Validate the current state.
        
        Returns:
            True if state is valid
        """
        try:
            # Re-validate the model
            SelfModelState.model_validate(self.state.model_dump())
            
            # Check invariants
            violations = self.check_invariants()
            
            return len(violations) == 0
            
        except ValidationError as e:
            logger.error(f"State validation failed: {e}")
            return False
    
    # ==================== Replay Support ====================
    
    def get_replay_chain(self, from_revision: str, to_revision: str) -> List[Dict[str, Any]]:
        """
        Get a chain of revisions for replay.
        
        Args:
            from_revision: Starting revision ID
            to_revision: Ending revision ID
            
        Returns:
            List of revision entries
        """
        revisions = self.state.revision_history.replay_revisions(from_revision, to_revision)
        
        return [
            {
                "revision_id": r.revision_id,
                "timestamp": r.timestamp,
                "changed_fields": r.changed_fields,
                "reason": r.reason,
                "evidence": r.evidence,
            }
            for r in revisions
        ]
    
    def get_update_summary(self) -> Dict[str, Any]:
        """Get summary of all updates."""
        return {
            "revision_count": len(self.state.revision_history.revisions),
            "continuity_entries": len(self.state.continuity_trace.entries),
            "last_revision": (
                self.state.revision_history.revisions[-1].model_dump()
                if self.state.revision_history.revisions else None
            ),
            "recent_updates": [
                {
                    "event": e.event,
                    "timestamp": e.timestamp,
                    "trigger": e.trigger,
                }
                for e in self.state.continuity_trace.get_recent_transitions(10)
            ],
            "invariant_status": self.check_invariants(),
        }

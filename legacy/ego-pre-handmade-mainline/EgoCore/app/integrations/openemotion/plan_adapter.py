"""
Plan Injection - Plan Adapter

Adapts OpenEmotion PlanResponse for reply generation.
Maps plan fields to reply-layer structures.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


logger = logging.getLogger(__name__)


@dataclass
class ReplyGuidance:
    """
    Adapted guidance for reply generation.
    
    Contains all plan fields relevant for crafting a response.
    """
    tone: str = "neutral"
    intent: str = "engage"
    key_points: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    focus_target: str = "user"
    
    # Emotional calibration
    emotion: Dict[str, float] = field(default_factory=lambda: {
        "valence": 0.5,
        "arousal": 0.3,
    })
    
    # Relationship context
    relationship: Dict[str, float] = field(default_factory=lambda: {
        "bond": 0.5,
        "trust": 0.5,
    })
    
    # Metadata
    used_plan: bool = False
    fallback_reason: Optional[str] = None
    
    def to_prompt_context(self) -> str:
        """
        Convert guidance to a prompt context string.
        
        Returns:
            Formatted string for LLM prompt injection
        """
        parts = []
        
        if self.tone:
            parts.append(f"Response tone: {self.tone}")
        
        if self.intent:
            parts.append(f"Response intent: {self.intent}")
        
        if self.key_points:
            points = ", ".join(self.key_points)
            parts.append(f"Key points to address: {points}")
        
        if self.constraints:
            constraints = ", ".join(self.constraints)
            parts.append(f"Constraints to respect: {constraints}")
        
        if self.focus_target:
            parts.append(f"Focus on: {self.focus_target}")
        
        return "\n".join(parts)


class PlanAdapter:
    """
    Adapts OpenEmotion PlanResponse for reply generation.
    
    Maps plan fields to ReplyGuidance structure.
    Provides fallback when plan is missing or invalid.
    """
    
    @staticmethod
    def adapt(plan_response: Optional[Dict[str, Any]]) -> ReplyGuidance:
        """
        Adapt a PlanResponse dict to ReplyGuidance.
        
        Args:
            plan_response: PlanResponse dict from OpenEmotion /plan API
        
        Returns:
            ReplyGuidance with adapted fields
        """
        if not plan_response:
            return PlanAdapter._fallback("empty_plan")
        
        try:
            guidance = ReplyGuidance()
            
            # Required fields
            if "tone" in plan_response:
                guidance.tone = plan_response["tone"]
            
            if "intent" in plan_response:
                guidance.intent = plan_response["intent"]
            
            if "key_points" in plan_response and isinstance(plan_response["key_points"], list):
                guidance.key_points = plan_response["key_points"]
            
            if "constraints" in plan_response and isinstance(plan_response["constraints"], list):
                guidance.constraints = plan_response["constraints"]
            
            if "focus_target" in plan_response:
                guidance.focus_target = plan_response["focus_target"]
            
            # Optional fields
            if "emotion" in plan_response and isinstance(plan_response["emotion"], dict):
                guidance.emotion = plan_response["emotion"]
            
            if "relationship" in plan_response and isinstance(plan_response["relationship"], dict):
                guidance.relationship = plan_response["relationship"]
            
            guidance.used_plan = True
            return guidance
            
        except Exception as e:
            logger.warning(f"Failed to adapt plan response: {e}")
            return PlanAdapter._fallback(f"adapt_error: {e}")
    
    @staticmethod
    def _fallback(reason: str) -> ReplyGuidance:
        """
        Create a fallback ReplyGuidance.
        
        Args:
            reason: Reason for fallback
        
        Returns:
            ReplyGuidance with default values
        """
        return ReplyGuidance(
            tone="neutral",
            intent="engage",
            key_points=[],
            constraints=[],
            focus_target="user",
            emotion={"valence": 0.5, "arousal": 0.3},
            relationship={"bond": 0.5, "trust": 0.5},
            used_plan=False,
            fallback_reason=reason,
        )
    
    @staticmethod
    def validate_plan(plan_response: Dict[str, Any]) -> bool:
        """
        Validate that a plan response has required fields.
        
        Args:
            plan_response: PlanResponse dict to validate
        
        Returns:
            True if valid
        """
        if not isinstance(plan_response, dict):
            return False
        
        # Required: tone
        if "tone" not in plan_response:
            return False
        
        # Required: key_points must be a list
        if "key_points" not in plan_response or not isinstance(plan_response["key_points"], list):
            return False
        
        return True


def adapt_plan(plan_response: Optional[Dict[str, Any]]) -> ReplyGuidance:
    """
    Convenience function to adapt a plan response.
    
    Args:
        plan_response: PlanResponse dict from OpenEmotion /plan API
    
    Returns:
        ReplyGuidance with adapted fields
    """
    return PlanAdapter.adapt(plan_response)

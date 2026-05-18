"""
OpenEmotion Agent Runtime - OpenEmotion Bridge

Lightweight bridge interface for future OpenEmotion integration.
Provides hooks for interaction outcomes, task results, and cognitive events.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from abc import ABC, abstractmethod
import json


@dataclass
class InteractionOutcome:
    """Represents the outcome of an interaction."""
    interaction_id: str
    user_input: str
    agent_response: str
    success: bool
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "interaction_id": self.interaction_id,
            "user_input": self.user_input,
            "agent_response": self.agent_response,
            "success": self.success,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }


@dataclass
class TaskResultSummary:
    """Summary of a completed or paused task."""
    task_id: str
    task_goal: str
    status: str
    steps_completed: int
    total_steps: int
    result_summary: str
    key_findings: List[str] = field(default_factory=list)
    issues_encountered: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_goal": self.task_goal,
            "status": self.status,
            "steps_completed": self.steps_completed,
            "total_steps": self.total_steps,
            "result_summary": self.result_summary,
            "key_findings": self.key_findings,
            "issues_encountered": self.issues_encountered,
            "timestamp": self.timestamp
        }


@dataclass
class AppraisalInput:
    """
    Placeholder for appraisal/cognitive evaluation.
    
    Future: Will contain emotional/situational appraisal data
    for OpenEmotion's cognitive architecture.
    """
    event_type: str
    context: Dict[str, Any] = field(default_factory=dict)
    emotional_valence: Optional[float] = None
    significance: Optional[float] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "context": self.context,
            "emotional_valence": self.emotional_valence,
            "significance": self.significance,
            "timestamp": self.timestamp
        }


@dataclass
class ReflectionInput:
    """
    Placeholder for reflection/metacognition events.
    
    Future: Will contain data for self-reflection processes.
    """
    reflection_type: str
    content: str
    insights: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "reflection_type": self.reflection_type,
            "content": self.content,
            "insights": self.insights,
            "timestamp": self.timestamp
        }


@dataclass
class NarrativeUpdate:
    """
    Placeholder for narrative/self-story updates.
    
    Future: Will update the agent's self-narrative.
    """
    update_type: str
    content: str
    importance: float = 0.5
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "update_type": self.update_type,
            "content": self.content,
            "importance": self.importance,
            "timestamp": self.timestamp
        }


@dataclass
class TrustRelationUpdate:
    """
    Placeholder for trust/relationship dynamics.
    
    Future: Will manage user-agent relationship state.
    """
    user_id: str
    trust_delta: float = 0.0
    interaction_quality: Optional[float] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "trust_delta": self.trust_delta,
            "interaction_quality": self.interaction_quality,
            "timestamp": self.timestamp
        }


class BridgeHandler(ABC):
    """Abstract base class for bridge handlers."""
    
    @abstractmethod
    def handle_interaction_outcome(self, outcome: InteractionOutcome) -> None:
        """Handle an interaction outcome event."""
        pass
    
    @abstractmethod
    def handle_task_result(self, result: TaskResultSummary) -> None:
        """Handle a task result summary."""
        pass


class OpenEmotionBridge:
    """
    Lightweight bridge for OpenEmotion integration.
    
    This is a placeholder implementation that logs events and provides
    hooks for future OpenEmotion cognitive architecture integration.
    
    The bridge maintains loose coupling - it does not require OpenEmotion
    to be present and will gracefully degrade to logging only.
    """
    
    def __init__(self, enabled: bool = True):
        """
        Initialize the bridge.
        
        Args:
            enabled: Whether the bridge is active (default True)
        """
        self.enabled = enabled
        self.handlers: List[BridgeHandler] = []
        self._event_log: List[Dict[str, Any]] = []
    
    def register_handler(self, handler: BridgeHandler) -> None:
        """Register a bridge event handler."""
        self.handlers.append(handler)
    
    def _log_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Log an event for audit/debugging."""
        event = {
            "event_type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        self._event_log.append(event)
    
    # === Primary Bridge Methods ===
    
    def submit_interaction_outcome(
        self,
        interaction_id: str,
        user_input: str,
        agent_response: str,
        success: bool,
        metadata: Optional[Dict[str, Any]] = None
    ) -> InteractionOutcome:
        """
        Submit an interaction outcome to the bridge.
        
        Args:
            interaction_id: Unique interaction identifier
            user_input: What the user said
            agent_response: How the agent responded
            success: Whether the interaction was successful
            metadata: Additional context
        
        Returns:
            InteractionOutcome object
        """
        outcome = InteractionOutcome(
            interaction_id=interaction_id,
            user_input=user_input,
            agent_response=agent_response,
            success=success,
            metadata=metadata or {}
        )
        
        if self.enabled:
            self._log_event("interaction_outcome", outcome.to_dict())
            for handler in self.handlers:
                handler.handle_interaction_outcome(outcome)
        
        return outcome
    
    def submit_task_result(
        self,
        task_id: str,
        task_goal: str,
        status: str,
        steps_completed: int,
        total_steps: int,
        result_summary: str,
        key_findings: Optional[List[str]] = None,
        issues_encountered: Optional[List[str]] = None
    ) -> TaskResultSummary:
        """
        Submit a task result summary to the bridge.
        
        Args:
            task_id: Task identifier
            task_goal: What the task was trying to accomplish
            status: Current task status
            steps_completed: Number of completed steps
            total_steps: Total steps in plan
            result_summary: Summary of results
            key_findings: Important findings
            issues_encountered: Problems encountered
        
        Returns:
            TaskResultSummary object
        """
        result = TaskResultSummary(
            task_id=task_id,
            task_goal=task_goal,
            status=status,
            steps_completed=steps_completed,
            total_steps=total_steps,
            result_summary=result_summary,
            key_findings=key_findings or [],
            issues_encountered=issues_encountered or []
        )
        
        if self.enabled:
            self._log_event("task_result", result.to_dict())
            for handler in self.handlers:
                handler.handle_task_result(result)
        
        return result
    
    # === Placeholder Methods for Future OpenEmotion Integration ===
    
    def submit_appraisal(
        self,
        event_type: str,
        context: Optional[Dict[str, Any]] = None,
        emotional_valence: Optional[float] = None,
        significance: Optional[float] = None
    ) -> AppraisalInput:
        """
        Submit an appraisal event (placeholder).
        
        Future: This will integrate with OpenEmotion's appraisal system.
        Currently logs the event for future processing.
        """
        appraisal = AppraisalInput(
            event_type=event_type,
            context=context or {},
            emotional_valence=emotional_valence,
            significance=significance
        )
        
        if self.enabled:
            self._log_event("appraisal", appraisal.to_dict())
        
        return appraisal
    
    def submit_reflection(
        self,
        reflection_type: str,
        content: str,
        insights: Optional[List[str]] = None
    ) -> ReflectionInput:
        """
        Submit a reflection event (placeholder).
        
        Future: This will integrate with OpenEmotion's reflection system.
        """
        reflection = ReflectionInput(
            reflection_type=reflection_type,
            content=content,
            insights=insights or []
        )
        
        if self.enabled:
            self._log_event("reflection", reflection.to_dict())
        
        return reflection
    
    def update_narrative(
        self,
        update_type: str,
        content: str,
        importance: float = 0.5
    ) -> NarrativeUpdate:
        """
        Update the agent's narrative (placeholder).
        
        Future: This will integrate with OpenEmotion's narrative system.
        """
        update = NarrativeUpdate(
            update_type=update_type,
            content=content,
            importance=importance
        )
        
        if self.enabled:
            self._log_event("narrative_update", update.to_dict())
        
        return update
    
    def update_trust_relation(
        self,
        user_id: str,
        trust_delta: float = 0.0,
        interaction_quality: Optional[float] = None
    ) -> TrustRelationUpdate:
        """
        Update trust/relationship state (placeholder).
        
        Future: This will integrate with OpenEmotion's relationship system.
        """
        update = TrustRelationUpdate(
            user_id=user_id,
            trust_delta=trust_delta,
            interaction_quality=interaction_quality
        )
        
        if self.enabled:
            self._log_event("trust_relation_update", update.to_dict())
        
        return update
    
    # === Utility Methods ===
    
    def get_event_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent events from the log."""
        return self._event_log[-limit:]
    
    def clear_event_log(self) -> None:
        """Clear the event log."""
        self._event_log.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get bridge statistics."""
        events_by_type = {}
        for event in self._event_log:
            et = event.get("event_type", "unknown")
            events_by_type[et] = events_by_type.get(et, 0) + 1
        
        return {
            "enabled": self.enabled,
            "total_events": len(self._event_log),
            "events_by_type": events_by_type,
            "handlers_registered": len(self.handlers)
        }


# Global bridge instance
_bridge: Optional[OpenEmotionBridge] = None


def get_bridge() -> OpenEmotionBridge:
    """Get the global bridge instance."""
    global _bridge
    if _bridge is None:
        _bridge = OpenEmotionBridge()
    return _bridge


def init_bridge(enabled: bool = True) -> OpenEmotionBridge:
    """Initialize the global bridge instance."""
    global _bridge
    _bridge = OpenEmotionBridge(enabled=enabled)
    return _bridge

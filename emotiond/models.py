"""
Pydantic models for request/response
"""
from pydantic import BaseModel, field_validator
from typing import List, Dict, Any, Optional


class Event(BaseModel):
    """
    Event model for POST /event
    
    Layer semantics (MVP-7.4):
    - Self: agent's own emotional state (agent_id)
    - Relation: agent's relationship with counterparty (agent_id -> counterparty_id)
    - Other: agent's inference about counterparty's state (optional)
    
    New fields (recommended):
    - agent_id: whose emotion/relationship is being updated (default: "agent")
    - counterparty_id: who the relationship is with (default: derived from actor)
    
    Legacy fields (backward compatible):
    - actor: who initiated the event (for world_event, this is the counterparty)
    - target: who received the event
    
    Audit fields (MVP-7.5):
    - correlation_id: trace ID for request tracing across hook → tool → emotiond → enforcer
    """
    type: str  # user_message|assistant_reply|world_event
    actor: str
    target: str
    text: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    # MVP-7.4: Explicit layer semantics
    agent_id: Optional[str] = None  # Whose emotion/relationship is updated
    counterparty_id: Optional[str] = None  # Who the relationship is with
    # MVP-7.5: Audit trail
    correlation_id: Optional[str] = None  # Trace ID for request tracing
    
    def get_agent_id(self) -> str:
        """Get agent_id with fallback."""
        if self.agent_id:
            return self.agent_id
        # Default: the entity whose state is being updated
        # For user_message: agent receives, so target is agent
        # For world_event: depends on context, default to target
        if self.type == "user_message":
            return self.target
        return self.target
    
    def get_counterparty_id(self) -> str:
        """Get counterparty_id with fallback to legacy logic."""
        if self.counterparty_id:
            return self.counterparty_id
        # Legacy fallback: derive from actor based on event type
        if self.type == "user_message":
            return self.actor  # User sent message, they are the counterparty
        elif self.type == "assistant_reply":
            return self.target  # Assistant replied to someone
        elif self.type == "world_event":
            return self.actor  # Who performed the action
        return self.actor


class DecisionResponse(BaseModel):
    """
    MVP-7.5: Decision response with audit trail fields.
    
    Used by /decision endpoints to return action selections with
    machine-parseable audit information for replay compatibility.
    """
    decision_id: int
    action: str
    explanation: Optional[Dict[str, Any]] = None
    target_id: Optional[str] = None
    created_at: Optional[str] = None
    # MVP-7.5: Audit trail fields
    correlation_id: Optional[str] = None  # Trace ID propagated from request
    policy_version: str = "7.5.0"  # Policy version for replay compatibility
    schema_version: str = "1.0"  # Response schema version for log parsing


class PlanRequest(BaseModel):
    """
    Request model for POST /plan
    
    Phase D (P1.1): Explicit identity/relationship fields
    
    Field semantics:
    - target_id: 会话隔离键 (conversationId) - used for session isolation and prediction lookups
    - counterparty_id: 关系对象 - who the relationship is with
    - agent_id: 本体身份 - whose emotion/relationship is being managed
    
    Backward compatibility:
    - If counterparty_id not provided, falls back to focus_target -> user_id
    - If target_id not provided, falls back to counterparty_id
    """
    user_id: str
    user_text: str
    focus_target: Optional[str] = None  # Legacy: Optional, defaults to user_id
    # Phase D (P1.1): Explicit identity fields
    target_id: Optional[str] = None  # 会话隔离键 (conversationId)
    counterparty_id: Optional[str] = None  # 关系对象
    agent_id: Optional[str] = None  # 本体身份
    
    def get_counterparty_id(self) -> str:
        """Get counterparty_id with fallback to focus_target -> user_id."""
        if self.counterparty_id:
            return self.counterparty_id
        if self.focus_target:
            return self.focus_target
        return self.user_id
    
    def get_target_id(self) -> str:
        """Get target_id with fallback to counterparty_id."""
        if self.target_id:
            return self.target_id
        return self.get_counterparty_id()
    
    def get_agent_id(self) -> str:
        """Get agent_id with fallback to 'agent'."""
        return self.agent_id or "agent"


class MoodResponse(BaseModel):
    """MVP-4 D1: Mood state in plan response"""
    valence: float = 0.0
    arousal: float = 0.3
    anxiety: float = 0.0
    joy: float = 0.0
    sadness: float = 0.0
    anger: float = 0.0
    loneliness: float = 0.0
    uncertainty: float = 0.5


class PlanResponse(BaseModel):
    """Response model for POST /plan"""
    tone: str  # soft|warm|guarded|cold
    intent: str  # repair|distance|seek|set_boundary|retaliate
    focus_target: str  # user|A|B|C or any dynamic target
    key_points: List[str]
    constraints: List[str]
    emotion: Dict[str, float]  # valence, arousal, anger, sadness, anxiety, joy, loneliness
    relationship: Dict[str, float]  # bond, grudge, trust, repair_bank
    relationships: Optional[Dict[str, Dict[str, float]]] = None  # All relationships if EMOTIOND_PLAN_INCLUDE_RELATIONSHIPS=1
    regulation_budget: Optional[float] = None  # MVP-2: cost mechanism state
    last_decision: Optional[Dict[str, Any]] = None  # MVP-3 C2: most recent decision with explanation
    # MVP-4 D1: Hierarchical state system
    mood: Optional[MoodResponse] = None  # Global mood baseline
    uncertainty: Optional[float] = None  # Current affect uncertainty
    bond_uncertainty: Optional[float] = None  # Per-target bond uncertainty
    # MVP-5 D2: Energy budget guidance
    energy_budget: Optional[float] = None  # Current energy budget [0, 1]
    language_guidance: Optional[Dict[str, Any]] = None  # Guidance for language generation
    w_explore: Optional[float] = None  # Adjusted exploration weight
    learning_rate_multiplier: Optional[float] = None  # Adjusted learning rate
    self_report: Optional[Dict[str, Any]] = None  # MVP-7: structured self-report (from self-model only)
    intent_contract: Optional[Dict[str, Any]] = None  # MVP11.5: response intent contract


class AppraisalResult(BaseModel):
    """MVP-4 D2: Structured appraisal result for an event"""
    goal_progress: float = 0.0  # [-1, 1]
    expectation_violation: float = 0.0  # [0, 1]
    controllability: float = 0.5  # [0, 1]
    social_threat: float = 0.0  # [0, 1]
    novelty: float = 0.0  # [0, 1]
    observed_delta: Dict[str, float] = {}  # safety, energy
    emotion_label: str = "neutral"
    intensity: float = 0.0  # [0, 1]
    reasoning: List[str] = []


class AppraisalRequest(BaseModel):
    """MVP-4 D2: Request for appraisal endpoint"""
    event: Event
    include_context: bool = False  # Whether to include affect/mood/bond in response


class AppraisalResponse(BaseModel):
    """MVP-4 D2: Response for appraisal endpoint"""
    appraisal: AppraisalResult
    affect: Optional[Dict[str, float]] = None
    mood: Optional[Dict[str, float]] = None
    bond: Optional[Dict[str, float]] = None


# MVP-6 D3: External Event models
class ExternalEventPayload(BaseModel):
    """Base payload for external events"""
    pass


class UserMessagePayload(ExternalEventPayload):
    """Payload for user_message type"""
    sentiment: Optional[str] = None  # positive|negative|neutral
    urgency: Optional[float] = None  # [0, 1]
    entities: Optional[List[str]] = None


class AssistantReplyPayload(ExternalEventPayload):
    """Payload for assistant_reply type"""
    tone: Optional[str] = None  # soft|warm|guarded|cold|neutral
    intent: Optional[str] = None  # repair|distance|seek|set_boundary|retaliate|inform
    confidence: Optional[float] = None  # [0, 1]


class WorldEventPayload(ExternalEventPayload):
    """Payload for world_event type"""
    subtype: str  # care|apology|ignored|rejection|betrayal|neutral|uncertain|repair_success|time_passed
    severity: Optional[float] = None  # [0, 1]
    context: Optional[Dict[str, Any]] = None


class ExternalEventRequest(BaseModel):
    """MVP-6 D3: Request model for POST /events/external"""
    event_id: Optional[str] = None  # Optional idempotency key
    type: str  # user_message|assistant_reply|world_event
    target_id: str  # Required for anti-forgery
    actor: Optional[str] = None  # Defaults to target_id
    text: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None  # Type-specific payload
    meta: Optional[Dict[str, Any]] = None


class ExternalEventResponse(BaseModel):
    """MVP-6 D3: Response model for POST /events/external"""
    status: str  # accepted|rejected|duplicate|error
    event_id: Optional[str] = None
    internal_event_id: Optional[str] = None
    message: Optional[str] = None
    degraded: bool = False  # True if graceful degradation was applied

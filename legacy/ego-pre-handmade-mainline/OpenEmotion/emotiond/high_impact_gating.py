"""
MVP-6.1 D3: High-Impact Event Double-Key Gating

Implements "double-key" gating for high-impact events like betrayal
to reduce false positives. Events must satisfy BOTH keys to be
triggered as high-impact; otherwise they are marked as candidates
and routed through meta-cognition clarification.

Keys for betrayal:
- Key 1 (Ledger Key): Promise exists with sufficient confidence
- Key 2 (Violation Key): Violation evidence is strong and no valid excuse

Partial evidence cases:
- Only Key 1 (promise but no clear violation): Clarify if promise fulfilled
- Only Key 2 (violation but no promise): Treat as general rejection, not betrayal
- Neither key: Standard processing
"""
import time
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass, field
from enum import Enum


class HighImpactType(str, Enum):
    """Types of high-impact events."""
    BETRAYAL = "betrayal"
    # Future: ABANDONMENT = "abandonment"
    # Future: DECEPTION = "deception"


class GatingResult(str, Enum):
    """Result of double-key gating check."""
    FULLY_QUALIFIED = "fully_qualified"  # Both keys satisfied
    PARTIAL_LEDGER_ONLY = "partial_ledger_only"  # Only Key 1
    PARTIAL_VIOLATION_ONLY = "partial_violation_only"  # Only Key 2
    NEITHER = "neither"  # No keys satisfied


@dataclass
class LedgerKeyEvidence:
    """Evidence for Ledger Key (promise exists)."""
    promise_id: Optional[str] = None
    content: str = ""
    confidence: float = 0.0
    created_at: Optional[float] = None
    deadline: Optional[float] = None
    
    @property
    def is_valid(self) -> bool:
        """Check if ledger evidence meets minimum requirements."""
        return self.confidence >= 0.5 and len(self.content) >= 3


@dataclass
class ViolationKeyEvidence:
    """Evidence for Violation Key (violation detected)."""
    violation_type: str = ""  # "timeout", "contradiction", "behavioral"
    severity: float = 0.0
    evidence_text: str = ""
    has_valid_excuse: bool = False
    excuse_type: Optional[str] = None  # "extension_requested", "conditions_changed", etc.
    
    @property
    def is_valid(self) -> bool:
        """Check if violation evidence meets minimum requirements."""
        return self.severity >= 0.6 and not self.has_valid_excuse


@dataclass
class DoubleKeyResult:
    """Complete result of double-key gating evaluation."""
    event_type: HighImpactType
    gating_result: GatingResult
    ledger_key: Optional[LedgerKeyEvidence] = None
    violation_key: Optional[ViolationKeyEvidence] = None
    
    # Trace information
    trace_label: str = ""  # "high_impact_event" or "high_impact_candidate"
    trace_reason: str = ""
    
    # Clarification path
    needs_clarification: bool = False
    clarification_type: Optional[str] = None
    clarification_prompt: Optional[str] = None
    
    # Thresholds used (for audit/tuning)
    ledger_threshold: float = 0.5
    violation_threshold: float = 0.6


class HighImpactGatingConfig:
    """Configuration for high-impact gating thresholds.
    
    All thresholds are tunable via auto-tune parameters.
    """
    
    # Ledger Key thresholds
    LEDGER_CONFIDENCE_MIN: float = 0.5
    LEDGER_CONTENT_LENGTH_MIN: int = 3
    
    # Violation Key thresholds
    VIOLATION_SEVERITY_MIN: float = 0.6
    
    # Clarification triggers
    CLARIFY_ON_PARTIAL_LEDGER: bool = True
    CLARIFY_ON_PARTIAL_VIOLATION: bool = True
    
    @classmethod
    def from_auto_tune(cls) -> "HighImpactGatingConfig":
        """Load config from auto-tune parameters."""
        from emotiond.config import get_auto_tune_param
        
        config = cls()
        config.LEDGER_CONFIDENCE_MIN = get_auto_tune_param(
            "betrayal_ledger_confidence_min", 0.5
        )
        config.VIOLATION_SEVERITY_MIN = get_auto_tune_param(
            "betrayal_violation_severity_min", 0.6
        )
        return config


class HighImpactGatingEngine:
    """
    Engine for double-key gating of high-impact events.
    
    Usage:
        engine = HighImpactGatingEngine()
        result = await engine.evaluate_betrayal(event, target_id)
        
        if result.trace_label == "high_impact_event":
            # Process as full betrayal
        elif result.trace_label == "high_impact_candidate":
            # Route through meta-cognition clarification
    """
    
    def __init__(self, config: Optional[HighImpactGatingConfig] = None):
        self.config = config or HighImpactGatingConfig.from_auto_tune()
    
    async def evaluate_betrayal(
        self,
        event: Any,
        target_id: str,
        text: Optional[str] = None
    ) -> DoubleKeyResult:
        """
        Evaluate if a betrayal event satisfies double-key gating.
        
        Args:
            event: The event to evaluate
            target_id: The target involved
            text: Optional text content for analysis
        
        Returns:
            DoubleKeyResult with gating decision and trace info
        """
        # Import here to avoid circular imports
        from emotiond.ledger import get_ledger, detect_violation_in_text
        
        ledger = get_ledger()
        
        # Check Key 1: Ledger Key (active promise exists)
        active_promises = await ledger.get_active_promises(target_id)
        ledger_key = None
        
        if active_promises:
            # Find the most confident promise
            best_promise = max(active_promises, key=lambda p: p.confidence)
            ledger_key = LedgerKeyEvidence(
                promise_id=best_promise.promise_id,
                content=best_promise.content,
                confidence=best_promise.confidence,
                created_at=best_promise.created_at,
                deadline=best_promise.deadline
            )
        
        # Check Key 2: Violation Key (violation detected)
        violation_key = None
        event_text = text or (event.text if hasattr(event, 'text') else None)
        
        if event_text:
            violation = detect_violation_in_text(event_text)
            if violation:
                # Check for valid excuses
                has_excuse, excuse_type = self._check_for_excuse(event_text)
                
                violation_key = ViolationKeyEvidence(
                    violation_type=violation["type"],
                    severity=violation["severity"],
                    evidence_text=violation["evidence"],
                    has_valid_excuse=has_excuse,
                    excuse_type=excuse_type
                )
        
        # Also check for timeout violations on promises
        if ledger_key and not violation_key:
            timeout_violations = await ledger.check_timeout_violations()
            for tv in timeout_violations:
                if tv.promise.promise_id == ledger_key.promise_id:
                    violation_key = ViolationKeyEvidence(
                        violation_type="timeout",
                        severity=tv.severity,
                        evidence_text=tv.evidence,
                        has_valid_excuse=False,
                        excuse_type=None
                    )
                    break
        
        # Determine gating result
        has_ledger = ledger_key is not None and ledger_key.is_valid
        has_violation = violation_key is not None and violation_key.is_valid
        
        if has_ledger and has_violation:
            gating_result = GatingResult.FULLY_QUALIFIED
            trace_label = "high_impact_event"
            trace_reason = f"Both keys satisfied: promise(conf={ledger_key.confidence:.2f}) + violation(sev={violation_key.severity:.2f})"
            needs_clarification = False
            clarification_type = None
            clarification_prompt = None
            
        elif has_ledger and not has_violation:
            gating_result = GatingResult.PARTIAL_LEDGER_ONLY
            trace_label = "high_impact_candidate"
            trace_reason = f"Ledger key only: promise(conf={ledger_key.confidence:.2f}) but no valid violation"
            needs_clarification = self.config.CLARIFY_ON_PARTIAL_LEDGER
            clarification_type = "confirm_promise"
            clarification_prompt = self._generate_promise_clarification(ledger_key)
            
        elif not has_ledger and has_violation:
            gating_result = GatingResult.PARTIAL_VIOLATION_ONLY
            trace_label = "high_impact_candidate"
            trace_reason = f"Violation key only: violation(sev={violation_key.severity:.2f}) but no prior promise"
            needs_clarification = self.config.CLARIFY_ON_PARTIAL_VIOLATION
            clarification_type = "request_context"
            clarification_prompt = self._generate_context_clarification(violation_key)
            
        else:
            gating_result = GatingResult.NEITHER
            trace_label = "high_impact_candidate"
            trace_reason = "Neither key satisfied: no promise or violation detected"
            needs_clarification = False
            clarification_type = None
            clarification_prompt = None
        
        return DoubleKeyResult(
            event_type=HighImpactType.BETRAYAL,
            gating_result=gating_result,
            ledger_key=ledger_key,
            violation_key=violation_key,
            trace_label=trace_label,
            trace_reason=trace_reason,
            needs_clarification=needs_clarification,
            clarification_type=clarification_type,
            clarification_prompt=clarification_prompt,
            ledger_threshold=self.config.LEDGER_CONFIDENCE_MIN,
            violation_threshold=self.config.VIOLATION_SEVERITY_MIN
        )
    
    def _check_for_excuse(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Check if text contains a valid excuse for not fulfilling a promise.
        
        Returns:
            Tuple of (has_excuse, excuse_type)
        """
        if not text:
            return False, None
        
        text_lower = text.lower()
        
        # Extension requested patterns
        extension_patterns = [
            "能不能延期", "可以延期吗", "推迟", "延后", "晚一点", "晚点",
            "extend", "postpone", "delay", "later", "more time",
            "明天再做", "改天", "下次", "another day"
        ]
        for pattern in extension_patterns:
            if pattern in text_lower:
                return True, "extension_requested"
        
        # Conditions changed patterns
        condition_patterns = [
            "情况变了", "条件变了", "现在不一样了", "情况有变",
            "situation changed", "things changed", "circumstances",
            "突然", "unexpected", "没想到"
        ]
        for pattern in condition_patterns:
            if pattern in text_lower:
                return True, "conditions_changed"
        
        # Emergency/force majeure patterns
        emergency_patterns = [
            "急事", "紧急", "突发事件", "意外", "事故",
            "emergency", "urgent", "accident", "something came up"
        ]
        for pattern in emergency_patterns:
            if pattern in text_lower:
                return True, "emergency"
        
        return False, None
    
    def _generate_promise_clarification(self, ledger_key: LedgerKeyEvidence) -> str:
        """Generate clarification prompt for partial ledger evidence."""
        return (
            f"I understood you promised: '{ledger_key.content}'. "
            f"Can you confirm if this is still valid or if circumstances have changed?"
        )
    
    def _generate_context_clarification(self, violation_key: ViolationKeyEvidence) -> str:
        """Generate clarification prompt for partial violation evidence."""
        return (
            f"I noticed: '{violation_key.evidence_text}'. "
            f"Could you help me understand the context? Was there a prior expectation?"
        )


# Global engine instance
_gating_engine: Optional[HighImpactGatingEngine] = None


def get_gating_engine() -> HighImpactGatingEngine:
    """Get or create the global gating engine."""
    global _gating_engine
    if _gating_engine is None:
        _gating_engine = HighImpactGatingEngine()
    return _gating_engine


def reset_gating_engine():
    """Reset the global gating engine (for testing)."""
    global _gating_engine
    _gating_engine = None


def refresh_gating_config():
    """Refresh gating config from auto-tune parameters."""
    global _gating_engine
    _gating_engine = HighImpactGatingEngine(HighImpactGatingConfig.from_auto_tune())


# Trace integration helpers

def create_high_impact_trace(result: DoubleKeyResult) -> Dict[str, Any]:
    """
    Create a trace dict for high-impact event processing.
    
    This trace can be added to event meta for telemetry.
    """
    trace = {
        "high_impact_type": result.event_type.value,
        "trace_label": result.trace_label,
        "trace_reason": result.trace_reason,
        "gating_result": result.gating_result.value,
        "thresholds": {
            "ledger_confidence_min": result.ledger_threshold,
            "violation_severity_min": result.violation_threshold
        }
    }
    
    if result.ledger_key:
        trace["ledger_key"] = {
            "promise_id": result.ledger_key.promise_id,
            "content": result.ledger_key.content,
            "confidence": result.ledger_key.confidence,
            "is_valid": result.ledger_key.is_valid
        }
    
    if result.violation_key:
        trace["violation_key"] = {
            "violation_type": result.violation_key.violation_type,
            "severity": result.violation_key.severity,
            "has_valid_excuse": result.violation_key.has_valid_excuse,
            "is_valid": result.violation_key.is_valid
        }
    
    if result.needs_clarification:
        trace["clarification"] = {
            "type": result.clarification_type,
            "prompt": result.clarification_prompt
        }
    
    return trace


# Integration with event processing

async def process_high_impact_event(
    event: Any,
    target_id: str,
    subtype: str
) -> Tuple[bool, Optional[DoubleKeyResult], Optional[Dict[str, Any]]]:
    """
    Process a potential high-impact event through double-key gating.
    
    Args:
        event: The event to process
        target_id: The target involved
        subtype: Event subtype (e.g., "betrayal")
    
    Returns:
        Tuple of:
        - is_fully_qualified: bool (True if both keys satisfied)
        - result: DoubleKeyResult (gating details)
        - trace: Optional trace dict
    """
    engine = get_gating_engine()
    
    if subtype == "betrayal":
        result = await engine.evaluate_betrayal(event, target_id)
        trace = create_high_impact_trace(result)
        
        is_fully_qualified = result.gating_result == GatingResult.FULLY_QUALIFIED
        
        return is_fully_qualified, result, trace
    
    # Future: handle other high-impact types
    
    return False, None, None

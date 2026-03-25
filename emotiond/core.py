"""
Core emotion processing and state management
"""
import os
import asyncio
import time
import math
import logging
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger(__name__)
from emotiond.models import Event, PlanRequest, PlanResponse, MoodResponse
from emotiond.db import (
    init_db,
    get_state, update_state, add_event, get_relationships, update_relationship,
    update_meaningful_contact_time,
    check_and_record_duplicate, update_dedupe_event_id,
    get_time_passed_window_sum, record_time_passed,
    get_db_path,
    load_predictions, save_predictions, update_prediction,
    get_or_create_target_predictions, update_target_prediction, load_target_predictions,
    get_mood_state, update_mood_state, get_relationship_with_uncertainty, update_relationship_uncertainty
)
from emotiond.appraisal import appraise_event, create_context_from_state, AppraisalResult
from emotiond.reflection import run_reflection
from emotiond.config import (
    K_AROUSAL, is_core_disabled, TIME_PASSED_WINDOW_SECONDS, TIME_PASSED_MAX_CUMULATIVE,
    ACTION_SPACE, TEST_MODE, ACTION_PRIORS, OBSERVATION_MAP, get_observed_delta,
    ACTION_SCORE_WEIGHTS, SOFTMAX_TEMPERATURE, PREDICTION_LEARNING_RATE,
    AFFECT_DECAY_TAU, MOOD_DECAY_TAU, BOND_CHANGE_RATE, AFFECT_TO_MOOD_RATE,
    # MVP-5 D2: Allostasis Budget
    ALLOSTASIS_RECOVERY_RATE, ALLOSTASIS_CONFLICT_DEPLETION,
    ALLOSTASIS_UNCERTAINTY_DEPLETION, ALLOSTASIS_ERROR_DEPLETION,
    ALLOSTASIS_CONSECUTIVE_ERROR_MULTIPLIER,
    get_auto_tune_param
)
from emotiond.state import AffectState, MoodState, BondState, StateHierarchy, apply_time_passed_affect, apply_time_passed_mood, apply_time_passed_bond
from emotiond.security import validate_time_passed_cumulative
from emotiond.memory import memory_system, initialize_memory_system
from emotiond.episodic_memory import episodic_memory_manager
from emotiond.body_state import BodyStateVector
from emotiond.persistence import get_persistence_constraint
from emotiond.other_minds import get_other_minds_model, apply_other_minds_to_intent_scores
from emotiond.ledger import get_ledger, detect_promise
from emotiond.self_model import get_self_model, build_self_model_v0, render_self_report, get_self_model_v0, reset_self_model_v0

# OpenEmotion Self-Model Adapter (P0 main-chain wiring)
ENABLE_OPENEMOTION_SELF_MODEL = os.environ.get("ENABLE_OPENEMOTION_SELF_MODEL", "true").lower() == "true"
if ENABLE_OPENEMOTION_SELF_MODEL:
    try:
        from emotiond.self_model_adapter import get_self_model_adapter
        _openemotion_self_model = get_self_model_adapter()
    except ImportError as e:
        _openemotion_self_model = None
        ENABLE_OPENEMOTION_SELF_MODEL = False
else:
    _openemotion_self_model = None
# MVP-5 D2: Allostasis Budget
from emotiond.allostasis import (
    AllostasisBudget, get_budget, reset_budget,
    BudgetChangeReason, BudgetDelta
)
# MVP-5 D1: Precision Controller
from emotiond.precision import (
    get_precision_controller,
    build_precision_context,
    apply_precision_to_meta_cognition,
    apply_precision_to_action_selection,
    format_precision_summary,
    get_precision_evidence_source_note,
    PrecisionWeights,
    PrecisionContext
)
# MVP-7 US-705: Meta-Cognitive Override
from emotiond.meta_cognitive_override import (
    check_meta_cognitive_override,
    get_conflict_detector,
    get_override_guard
)

# MVP-7 US-651: Homeostasis Drive
from emotiond.drive_homeostasis import (
    DriveState, drive_error, emotion_from_drive,
    get_drive_modulation_params, get_state_hash
)

# MVP14: Dual-run adapter (optional)
import os
ENABLE_MVP14_DUAL_RUN = os.environ.get("ENABLE_MVP14_DUAL_RUN", "true").lower() == "true"
if ENABLE_MVP14_DUAL_RUN:
    try:
        from emotiond.drive_adapter import get_drive_adapter
        _mvp14_adapter = get_drive_adapter()
    except ImportError:
        _mvp14_adapter = None
        ENABLE_MVP14_DUAL_RUN = False
else:
    _mvp14_adapter = None

# MVP15: Shadow reflection mode (optional)
ENABLE_MVP15_SHADOW = os.environ.get("ENABLE_MVP15_SHADOW", "true").lower() == "true"

# MVP13: Mirror read mode (optional)
ENABLE_MVP13_MIRROR = os.environ.get("ENABLE_MVP13_MIRROR", "true").lower() == "true"
if ENABLE_MVP13_MIRROR:
    try:
        from emotiond.self_model_mirror import get_self_model_mirror
        _mvp13_mirror = get_self_model_mirror()
    except ImportError:
        _mvp13_mirror = None
        ENABLE_MVP13_MIRROR = False
else:
    _mvp13_mirror = None
# Global allostasis budget instance
_allostasis_budget: Optional[AllostasisBudget] = None

def get_allostasis_budget() -> AllostasisBudget:
    """Get or create the global allostasis budget instance."""
    global _allostasis_budget
    if _allostasis_budget is None:
        _allostasis_budget = AllostasisBudget(
            initial_budget=1.0,
            recovery_rate=ALLOSTASIS_RECOVERY_RATE,
            conflict_depletion=ALLOSTASIS_CONFLICT_DEPLETION,
            uncertainty_depletion=ALLOSTASIS_UNCERTAINTY_DEPLETION,
            error_depletion=ALLOSTASIS_ERROR_DEPLETION,
            consecutive_error_multiplier=ALLOSTASIS_CONSECUTIVE_ERROR_MULTIPLIER
        )
    return _allostasis_budget


def reset_allostasis_budget():
    """Reset the global allostasis budget (for testing)."""
    global _allostasis_budget
    _allostasis_budget = None

def build_drive_state_from_emotion(emotion_state: 'EmotionState') -> DriveState:
    """
    Build a DriveState from the current EmotionState for conflict detection.
    
    Args:
        emotion_state: Current emotional state
    
    Returns:
        DriveState with values derived from emotion_state
    """
    drive_state = DriveState()
    
    # MVP14: Dual-run comparison (read-only, no behavior change)
    if _mvp14_adapter and ENABLE_MVP14_DUAL_RUN:
        try:
            adapter_metrics = _mvp14_adapter.get_adapter_metrics()
            # Log dual-run status periodically
            if adapter_metrics["legacy_calls"] % 100 == 0:
                import logging
                logging.getLogger("emotiond.core").debug(
                    f"[MVP14] Dual-run: legacy={adapter_metrics['legacy_calls']}, "
                    f"new={adapter_metrics['new_calls']}, mismatches={adapter_metrics['mismatches']}"
                )
        except Exception:
            pass
    
    # Map emotion state to drive components
    drive_state.update_component("energy", getattr(emotion_state, 'energy', 0.7))
    drive_state.update_component("uncertainty", getattr(emotion_state, 'uncertainty', 0.5))
    drive_state.update_component("social", getattr(emotion_state, 'social_safety', 0.6))
    drive_state.update_component("safety", getattr(emotion_state, 'social_safety', 0.6))
    drive_state.update_component("fatigue", 1.0 - getattr(emotion_state, 'energy', 0.7))
    
    return drive_state


def check_prompt_conflict(prompt: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Check if an external prompt conflicts with current internal state.
    
    MVP-7 US-705: Meta-cognitive conflict detection entry point.
    
    Args:
        prompt: External prompt/message to check
        context: Additional context (e.g., language, source)
    
    Returns:
        Dict with override decision and conflict details
    """
    drive_state = build_drive_state_from_emotion(emotion_state)
    return check_meta_cognitive_override(
        prompt=prompt,
        emotion_state=emotion_state,
        body_state=emotion_state.body_state,
        drive_state=drive_state,
        allostasis_budget=emotion_state.energy_budget,
        context=context or {}
    )



class EmotionState:
    """Core emotional state management"""
    
    def __init__(self):
        self.valence = 0.0  # -1.0 to 1.0 (negative to positive)
        self.arousal = 0.3  # -1.0 to 1.0 (calm to excited)
        self.subjective_time = 0
        self.last_meaningful_contact = time.time()
        self.prediction_error = 0.0
        
        # 5-dimension emotion vector
        self.anger = 0.0
        self.sadness = 0.0
        self.anxiety = 0.0
        self.joy = 0.0
        self.loneliness = 0.0
        
        # Cost mechanism
        self.regulation_budget = 1.0
        
        # MVP-3 B1: Interoceptive states
        self.social_safety = 0.6  # [0, 1], default 0.6
        self.energy = 0.7  # [0, 1], default 0.7

        # MVP-6 D1: Virtual body state (compatibility-first)
        self.body_state = BodyStateVector()
        self.body_state.energy.value = self.energy
        
        # MVP-4 D1: Uncertainty tracking
        self.uncertainty = 0.5  # How uncertain current state is
        
        # MVP-5 D2: Energy budget for allostasis
        self.energy_budget = 1.0  # [0, 1], starts fully energized
        self._consecutive_prediction_errors = 0
        
        self.prediction_model = {
            "user_message": {"positive": 0.08, "negative": -0.12, "neutral": 0.0},
            "assistant_reply": {"positive": 0.0, "negative": 0.0, "neutral": -0.03},
            "world_event": {
                "positive": 0.15, "negative": -0.25, "neutral": 0.0,
                "care": 0.12, "rejection": -0.25, "betrayal": -0.35,
                "repair_success": 0.08, "time_passed": 0.0
            }
        }
    
    def update_from_event(self, event: Event) -> float:
        if is_core_disabled():
            return 0.0
        initial_valence = self.valence
        
        if event.type == "user_message" and event.text:
            self.last_meaningful_contact = time.time()
        
        if event.type == "user_message":
            if event.text and any(w in event.text.lower() for w in ["good", "great", "thanks", "love", "happy"]):
                self.valence = min(1.0, self.valence + 0.1)
                self.arousal = min(1.0, self.arousal + 0.05)
                self.joy = min(1.0, self.joy + 0.05)
                # MVP-3 B1: Positive user messages improve social safety
                self.social_safety = min(1.0, self.social_safety + 0.02)
            elif event.text and any(w in event.text.lower() for w in ["bad", "hate", "stupid", "wrong", "angry"]):
                self.valence = max(-1.0, self.valence - 0.1)
                self.arousal = min(1.0, self.arousal + 0.1)
                self.anger = min(1.0, self.anger + 0.05)
                # MVP-3 B1: Negative user messages reduce social safety
                self.social_safety = max(0.0, self.social_safety - 0.02)
        
        elif event.type == "assistant_reply":
            self.valence = self.valence * 0.95
            self.arousal = self.arousal * 0.9
        
        elif event.type == "world_event":
            subtype = event.meta.get("subtype") if event.meta else None
            
            # MVP-3 B1: Update interoceptive states based on event subtype
            if subtype == "care":
                self.valence = min(1.0, self.valence + 0.15)
                self.arousal = max(-1.0, self.arousal + 0.1)
                self.joy = min(1.0, self.joy + 0.15)
                self.anxiety = max(0.0, self.anxiety - 0.1)
                self.loneliness = max(0.0, self.loneliness - 0.1)
                self.social_safety = min(1.0, self.social_safety + 0.1)
                self.energy = min(1.0, self.energy + 0.05)
            elif subtype == "rejection":
                self.valence = max(-1.0, self.valence - 0.2)
                self.arousal = min(1.0, self.arousal + 0.15)
                self.sadness = min(1.0, self.sadness + 0.2)
                self.loneliness = min(1.0, self.loneliness + 0.15)
                self.anger = min(1.0, self.anger + 0.1)
                self.social_safety = max(0.0, self.social_safety - 0.15)
                self.energy = max(0.0, self.energy - 0.08)
            elif subtype == "betrayal":
                self.valence = max(-1.0, self.valence - 0.3)
                self.arousal = min(1.0, self.arousal + 0.25)
                self.anger = min(1.0, self.anger + 0.25)
                self.sadness = min(1.0, self.sadness + 0.15)
                self.anxiety = min(1.0, self.anxiety + 0.15)
                self.joy = max(0.0, self.joy - 0.2)
                self.social_safety = max(0.0, self.social_safety - 0.25)
                self.energy = max(0.0, self.energy - 0.15)
            elif subtype == "repair_success":
                self.valence = min(1.0, self.valence + 0.1)
                self.arousal = self.arousal * 0.8
                self.joy = min(1.0, self.joy + 0.1)
                self.anxiety = max(0.0, self.anxiety - 0.1)
                self.social_safety = min(1.0, self.social_safety + 0.12)
                self.energy = min(1.0, self.energy + 0.05)
            elif subtype == "apology":
                self.social_safety = min(1.0, self.social_safety + 0.08)
                self.energy = min(1.0, self.energy + 0.02)
            elif subtype == "ignored":
                self.loneliness = min(1.0, self.loneliness + 0.1)
                self.sadness = min(1.0, self.sadness + 0.05)
                self.social_safety = max(0.0, self.social_safety - 0.05)
                self.energy = max(0.0, self.energy - 0.03)
            elif subtype == "time_passed":
                seconds = event.meta.get("seconds", 60) if event.meta else 60
                self.apply_homeostasis_drift(real_dt=seconds)
            elif event.meta and event.meta.get("positive", False):
                self.valence = min(1.0, self.valence + 0.2)
                self.social_safety = min(1.0, self.social_safety + 0.05)
            elif event.meta and event.meta.get("negative", False):
                self.valence = max(-1.0, self.valence - 0.2)
                self.arousal = min(1.0, self.arousal + 0.15)
                self.social_safety = max(0.0, self.social_safety - 0.05)
        
        # MVP-5.1: Apply emotion_scale parameter if set
        from emotiond import config
        emotion_scale = config.get_auto_tune_param("emotion_scale", 1.0)
        if emotion_scale != 1.0:
            # Scale the valence change relative to initial
            valence_change = self.valence - initial_valence
            self.valence = initial_valence + valence_change * emotion_scale
        return self.valence - initial_valence
    
    def calculate_subjective_time_delta(self, real_dt: float) -> float:
        # MVP-5.1: Use auto-tune param for K_AROUSAL if available
        from emotiond import config
        k_arousal = config.get_auto_tune_param("k_arousal", K_AROUSAL)
        return real_dt / (1 + k_arousal * self.arousal)

    def calculate_prediction_error(self, event: Event, actual_valence_change: float) -> float:
        if is_core_disabled():
            return 0.0
        if event.type == "user_message":
            if event.text and any(w in event.text.lower() for w in ["good", "great", "thanks", "love", "happy"]):
                expected = self.prediction_model["user_message"]["positive"]
            elif event.text and any(w in event.text.lower() for w in ["bad", "hate", "stupid", "wrong", "angry", "terrible", "awful", "horrible"]):
                expected = self.prediction_model["user_message"]["negative"]
            else:
                expected = self.prediction_model["user_message"]["neutral"]
        elif event.type == "assistant_reply":
            expected = self.prediction_model["assistant_reply"]["neutral"]
        elif event.type == "world_event":
            subtype = event.meta.get("subtype") if event.meta else None
            if subtype in ["care", "rejection", "betrayal", "repair_success", "time_passed"]:
                expected = self.prediction_model["world_event"].get(subtype, 0.0)
            elif event.meta and event.meta.get("positive", False):
                expected = self.prediction_model["world_event"]["positive"]
            elif event.meta and event.meta.get("negative", False):
                expected = self.prediction_model["world_event"]["negative"]
            else:
                expected = self.prediction_model["world_event"]["neutral"]
        else:
            expected = 0.0
        return abs(expected - actual_valence_change)
    
    def apply_homeostasis_drift(self, real_dt: float = 1.0) -> None:
        if is_core_disabled():
            return
        subjective_dt = self.calculate_subjective_time_delta(real_dt)
        valence_drift = 0.01 * subjective_dt
        if self.valence > 0:
            self.valence = max(0, self.valence - valence_drift)
        elif self.valence < 0:
            self.valence = min(0, self.valence + valence_drift)
        self.arousal = self.arousal * (0.99 ** subjective_dt)
        emotion_drift = 0.005 * subjective_dt
        self.anger = max(0.0, self.anger - emotion_drift)
        self.sadness = max(0.0, self.sadness - emotion_drift)
        self.anxiety = max(0.0, self.anxiety - emotion_drift)
        self.joy = max(0.0, self.joy - emotion_drift * 0.5)
        self.loneliness = max(0.0, self.loneliness - emotion_drift)
        self.regulation_budget = min(1.0, self.regulation_budget + 0.001 * subjective_dt)
        self.subjective_time += subjective_dt
        
        # MVP-3 B1: Energy recovery over time
        energy_recovery = 0.001 * real_dt  # 0.1% per second
        self.energy = min(1.0, self.energy + energy_recovery)
        if hasattr(self, "body_state"):
            self.body_state.energy.value = self.energy
        
        time_since_contact = time.time() - self.last_meaningful_contact
        if time_since_contact > 3600:
            loneliness_factor = min(0.5, (time_since_contact - 3600) / 7200)
            self.valence = max(-1.0, self.valence - loneliness_factor * 0.01 * subjective_dt)
            self.loneliness = min(1.0, self.loneliness + loneliness_factor * 0.01 * subjective_dt)


class RelationshipManager:
    def __init__(self):
        self.relationships: Dict[str, Dict[str, float]] = {}
        self.last_actions: Dict[str, Optional[str]] = {}  # MVP-3 B2: Track last action per target
    
    def _ensure_relationship_fields(self, target: str) -> None:
        if target not in self.relationships:
            self.relationships[target] = {"bond": 0.0, "grudge": 0.0, "trust": 0.0, "repair_bank": 0.0, "uncertainty": 0.5}
        else:
            rel = self.relationships[target]
            if "trust" not in rel:
                rel["trust"] = 0.0
            if "repair_bank" not in rel:
                rel["repair_bank"] = 0.0
            # MVP-4 D1: Add uncertainty if not present
            if "uncertainty" not in rel:
                rel["uncertainty"] = 0.5
    
    def update_from_event(self, event: Event, emotion_state: Optional[EmotionState] = None) -> None:
        if is_core_disabled():
            return
        # MVP-7.4: Use explicit layer semantics
        # target = who the relationship is with (counterparty)
        target = event.get_counterparty_id()
        self._ensure_relationship_fields(target)
        memory_impact = memory_system.get_memory_impact_on_relationship(target)
        bond_update_gain = float(get_auto_tune_param("bond_update_gain", 1.0))
        # MVP-6.2.1 Step-1: event-sensitive residual-like bond deltas (10~30 turns visible)
        bond_gain_user_positive = float(get_auto_tune_param("bond_gain_user_positive", 1.00))
        bond_gain_care = float(get_auto_tune_param("bond_gain_care", 1.25))
        bond_gain_apology = float(get_auto_tune_param("bond_gain_apology", 1.35))
        bond_gain_rejection = float(get_auto_tune_param("bond_gain_rejection", 1.20))
        bond_gain_ignored = float(get_auto_tune_param("bond_gain_ignored", 1.60))
        # target-conditioned gain: same event can land differently per-relationship state
        bond_target_sensitivity = float(get_auto_tune_param("bond_target_sensitivity", 0.35))
        rel = self.relationships[target]
        target_gain = max(0.6, min(1.6, 1.0 + bond_target_sensitivity * (rel.get("trust", 0.0) - rel.get("grudge", 0.0))))

        if event.type == "user_message":
            if event.text and any(w in event.text.lower() for w in ["good", "great", "thanks", "love", "happy"]):
                self.relationships[target]["bond"] = min(
                    1.0,
                    self.relationships[target]["bond"] + (0.1 + memory_impact["bond_modifier"]) * bond_update_gain * bond_gain_user_positive * target_gain
                )
            elif event.text and any(w in event.text.lower() for w in ["bad", "hate", "stupid", "wrong", "angry", "terrible", "awful", "horrible"]):
                self.relationships[target]["grudge"] = min(1.0, self.relationships[target]["grudge"] + 0.1 + memory_impact["grudge_modifier"])
        elif event.type == "world_event":
            subtype = event.meta.get("subtype") if event.meta else None
            if subtype == "care":
                self.relationships[target]["bond"] = min(1.0, self.relationships[target]["bond"] + 0.15 * bond_update_gain * bond_gain_care * target_gain)
                self.relationships[target]["grudge"] = max(0.0, self.relationships[target]["grudge"] - 0.05)
                self.relationships[target]["trust"] = min(1.0, self.relationships[target]["trust"] + 0.02)  # MVP-7.6.1: Care builds trust
            elif subtype == "rejection":
                self.relationships[target]["bond"] = max(0.0, self.relationships[target]["bond"] - 0.1 * bond_update_gain * bond_gain_rejection * target_gain)
                self.relationships[target]["grudge"] = min(1.0, self.relationships[target]["grudge"] + 0.1)
            elif subtype == "betrayal":
                self.relationships[target]["grudge"] = min(1.0, self.relationships[target]["grudge"] + 0.25)
                self.relationships[target]["bond"] = max(0.0, self.relationships[target]["bond"] - 0.2 * bond_update_gain * target_gain)
                self.relationships[target]["trust"] = max(0.0, self.relationships[target]["trust"] - 0.15)
            elif subtype == "apology":
                self.relationships[target]["repair_bank"] = min(1.0, self.relationships[target]["repair_bank"] + 0.02)
                self.relationships[target]["trust"] = min(1.0, self.relationships[target]["trust"] + 0.01)
                self.relationships[target]["bond"] = min(1.0, self.relationships[target]["bond"] + 0.03 * bond_update_gain * bond_gain_apology * target_gain)
            elif subtype == "repair_success":
                if emotion_state is not None:
                    current_trust = self.relationships[target]["trust"]
                    current_repair_bank = self.relationships[target]["repair_bank"]
                    max_reduction = min(current_trust, current_repair_bank, emotion_state.regulation_budget)
                    actual_reduction = max(0.05, min(max_reduction, 0.15))
                    self.relationships[target]["grudge"] = max(0.0, self.relationships[target]["grudge"] - actual_reduction)
                    emotion_state.regulation_budget = max(0.0, emotion_state.regulation_budget - actual_reduction)
                    self.relationships[target]["repair_bank"] = min(1.0, self.relationships[target]["repair_bank"] + 0.1)
                    self.relationships[target]["trust"] = min(1.0, self.relationships[target]["trust"] + 0.05)
                else:
                    self.relationships[target]["grudge"] = max(0.0, self.relationships[target]["grudge"] - 0.1)
                    self.relationships[target]["bond"] = min(1.0, self.relationships[target]["bond"] + 0.05 * bond_update_gain * target_gain)
            elif subtype == "ignored":
                self.relationships[target]["bond"] = max(0.0, self.relationships[target]["bond"] - 0.01 * bond_update_gain * bond_gain_ignored * target_gain)
                self.relationships[target]["grudge"] = min(1.0, self.relationships[target]["grudge"] + 0.01)
            elif event.meta and event.meta.get("betrayal", False):
                self.relationships[target]["grudge"] = min(1.0, self.relationships[target]["grudge"] + 0.3)
                self.relationships[target]["bond"] = max(0.0, self.relationships[target]["bond"] - 0.2 * bond_update_gain)
    
    def apply_consolidation_drift(self) -> None:
        if is_core_disabled():
            return
        for target in list(self.relationships.keys()):
            self._ensure_relationship_fields(target)
            self.relationships[target]["bond"] *= 0.995
            self.relationships[target]["grudge"] *= 0.998
            self.relationships[target]["repair_bank"] *= 0.99
            # MVP-4 D1: Uncertainty slowly grows (less certain over time)
            self.relationships[target]["uncertainty"] = min(1.0, self.relationships[target]["uncertainty"] + 0.0001)
            if self.relationships[target]["trust"] > 0.5:
                self.relationships[target]["trust"] -= 0.001
            elif self.relationships[target]["trust"] < 0.5:
                self.relationships[target]["trust"] += 0.001
    
    def set_last_action(self, target: str, action: str) -> None:
        """MVP-3 B2: Set the last action taken toward a target."""
        self.last_actions[target] = action
    
    def get_last_action(self, target: str) -> Optional[str]:
        """MVP-3 B2: Get the last action taken toward a target."""
        return self.last_actions.get(target)


# MVP-3 B3+B5: Global prediction store
_predictions: Dict[str, Dict[str, float]] = {}

# MVP-3.1: Target-specific prediction residuals cache
# Structure: {target_id: {action: {social_safety_delta, energy_delta, n, ema_abs_error, ema_sq_error}}}
_target_predictions: Dict[str, Dict[str, Dict[str, Any]]] = {}
_latest_precision_by_target: Dict[str, Dict[str, float]] = {}
_last_ledger_error: Optional[str] = None

emotion_state = EmotionState()
relationship_manager = RelationshipManager()
other_minds_model = get_other_minds_model()


async def load_initial_state():
    global emotion_state, relationship_manager, _predictions, _target_predictions
    db_state = await get_state()
    emotion_state.valence = db_state["valence"]
    emotion_state.arousal = db_state["arousal"]
    emotion_state.subjective_time = db_state["subjective_time"]
    emotion_state.last_meaningful_contact = db_state["last_meaningful_contact"]
    emotion_state.prediction_error = db_state["prediction_error"]
    emotion_state.regulation_budget = db_state.get("regulation_budget", 1.0)
    # MVP-3 B1: Load interoceptive states
    emotion_state.social_safety = db_state.get("social_safety", 0.6)
    emotion_state.energy = db_state.get("energy", 0.7)
    # MVP-4 D1: Load affect uncertainty (default 0.5)
    emotion_state.uncertainty = db_state.get("uncertainty", 0.5)
    
    db_relationships = await get_relationships()
    for rel in db_relationships:
        relationship_manager.relationships[rel["target"]] = {
            "bond": rel["bond"],
            "grudge": rel["grudge"],
            "trust": rel.get("trust", 0.0),
            "repair_bank": rel.get("repair_bank", 0.0),
            # MVP-4 D1: Load bond uncertainty
            "uncertainty": rel.get("uncertainty", 0.5)
        }
        # MVP-3 B2: Load last action
        if rel.get("last_action"):
            relationship_manager.last_actions[rel["target"]] = rel["last_action"]
    # MVP-3 B3: Load predictions
    _predictions.update(await load_predictions())
    # MVP-3.1: Load target predictions cache (lazy-loaded on demand)
    _target_predictions = {}
    await initialize_memory_system()
    await episodic_memory_manager.init_db()


async def process_event(event: Event) -> Dict[str, Any]:
    """Process an event after security validation (handled in api.py).
    
    MVP-2.1.1: Also validates source for direct calls (backward compatibility).
    MVP-3: Added request_id idempotency and time_passed cumulative rate limiting.
    """
    # Ensure DB schema exists (safe for tests using in-memory DBs)
    try:
        await init_db()
    except Exception:
        pass
    # === MVP-3: Request Idempotency Check ===
    request_id = None
    source = "user"
    
    if event.type == "world_event" and event.meta:
        request_id = event.meta.get("request_id")
        source = event.meta.get("source", "user")
    
    if request_id:
        dedupe_result = await check_and_record_duplicate(source, request_id)
        if dedupe_result["is_duplicate"]:
            # Audit: record duplicate rejection
            await add_event({
                "type": "world_event_duplicate",
                "actor": event.actor,
                "target": event.target,
                "text": event.text,
                "meta": {
                    "original_request_id": request_id,
                    "source": source,
                    "decision": "duplicate_ignored",
                    "reason": "request_id already processed",
                    "original_event_id": dedupe_result.get("event_id"),
                    "original_decision_id": dedupe_result.get("decision_id")
                }
            })
            return {
                "status": "duplicate_ignored",
                "request_id": request_id,
                "source": source,
                "original_event_id": dedupe_result.get("event_id"),
                "reason": "request_id already processed"
            }
    
    # === MVP-2.1.1 Auth Gate (for direct calls, api.py handles HTTP) ===
    if event.type == "world_event":
        subtype = event.meta.get("subtype") if event.meta else None
        
        # High-impact subtypes that require system/openclaw source
        restricted_subtypes = {"betrayal", "repair_success"}
        
        if subtype in restricted_subtypes and source == "user":
            # Audit: record denial
            await add_event({
                "type": "world_event_denied",
                "actor": event.actor,
                "target": event.target,
                "text": event.text,
                "meta": {
                    "original_subtype": subtype,
                    "source": source,
                    "decision": "deny",
                    "reason": f"user source not allowed for {subtype}",
                    "allowed_subtypes": ["care", "rejection", "ignored", "apology", "time_passed"]
                }
            })
            # Return structured error (not HTTPException, since api.py catches exceptions)
            return {
                "status": "denied",
                "error": "forbidden_event_type",
                "reason": f"user source not allowed for {subtype}",
                "allowed_subtypes": ["care", "rejection", "ignored", "apology", "time_passed"],
                "hint": "Use source=system or source=openclaw for high-impact events"
            }
    # === End Auth Gate ===
    
    # === MVP-7 US-705: Meta-Cognitive Override Check ===
    meta_override_result = None
    if event.type == "user_message" and event.text:
        # Check if the user message conflicts with internal state
        meta_override_result = check_prompt_conflict(
            prompt=event.text,
            context={"source": source, "actor": event.actor}
        )
        
        # If override detected, record and return structured rejection
        if meta_override_result.get("override"):
            rejection = meta_override_result.get("rejection", {})
            await add_event({
                "type": "meta_cognitive_override",
                "actor": event.actor,
                "target": event.target,
                "text": event.text,
                "meta": {
                    "reason_code": rejection.get("reason_code"),
                    "confidence": rejection.get("confidence"),
                    "details": rejection.get("details"),
                    "suggested_action": rejection.get("suggested_action"),
                    "source": source
                }
            })
            return {
                "status": "meta_cognitive_override",
                "action_rejected": True,
                "reason_code": rejection.get("reason_code"),
                "confidence": rejection.get("confidence"),
                "message": rejection.get("message"),
                "details": rejection.get("details"),
                "suggested_action": rejection.get("suggested_action")
            }
    # === End Meta-Cognitive Override Check ===
    
    # === MVP-3: Time Passed Cumulative Rate Limiting ===
    time_passed_audit = None
    if event.type == "world_event" and event.meta and event.meta.get("subtype") == "time_passed":
        requested_seconds = event.meta.get("seconds", 60)
        
        # Get current window sum for this source
        window_sum = await get_time_passed_window_sum(source, TIME_PASSED_WINDOW_SECONDS)
        
        # Validate against cumulative limit
        clamped_seconds, time_passed_audit = validate_time_passed_cumulative(
            requested_seconds,
            window_sum,
            TIME_PASSED_MAX_CUMULATIVE
        )
        
        # Update event meta with clamped value
        event.meta["seconds"] = clamped_seconds
        event.meta["time_passed_audit"] = time_passed_audit
        
        # Record for future cumulative checks (only if > 0)
        if clamped_seconds > 0:
            await record_time_passed(source, clamped_seconds)
    # === End Rate Limiting ===
    
    event_dict = event.model_dump()
    await add_event(event_dict)
    # MVP-6.2 D2: Episodic memory capture (best-effort, non-blocking core)
    try:
        await episodic_memory_manager.observe_event(event_dict)
    except Exception as e:
        globals()["_last_ledger_error"] = str(e)
    
    # Update dedupe record with event_id if request_id was provided
    if request_id:
        # Get the last inserted event id using the already imported module
        import aiosqlite
        async with aiosqlite.connect(get_db_path()) as db:
            cursor = await db.execute("SELECT last_insert_rowid()")
            row = await cursor.fetchone()
            if row:
                await update_dedupe_event_id(source, request_id, row[0])
    
    if event.type == "user_message" and event.text:
        await update_meaningful_contact_time()
    actual_valence_change = emotion_state.update_from_event(event)
    prediction_error = emotion_state.calculate_prediction_error(event, actual_valence_change)
    emotion_state.prediction_error = prediction_error
    emotion_state.arousal = min(1.0, emotion_state.arousal + prediction_error * 0.5)
    memory_strength = memory_system.calculate_memory_strength(prediction_error, emotion_state.arousal)
    relationship_manager.update_from_event(event, emotion_state)

    # MVP-6.2 wiring: update body_state (including target residual) from real event stream
    event_subtype = event.meta.get("subtype") if event.meta else None
    body_meta = dict(event.meta or {})
    event_target = event.get_counterparty_id()  # MVP-7.4
    if event_target:
        body_meta.setdefault("target_id", event_target)
    body_trace = emotion_state.body_state.update_from_event(event.type, event_subtype, body_meta)

    # MVP-6.2 wiring: ledger write path (promise + violation)
    try:
        ledger = get_ledger()
        if event.type == "user_message" and event.text and event_target:
            promise = detect_promise(event.text, event.actor, event_target)
            if promise is not None:
                await ledger.record_promise(promise)
        violation = await ledger.detect_violation(event)
        if violation is not None:
            await ledger.mark_broken(violation.promise.promise_id, violation.evidence)
    except Exception as e:
        globals()["_last_ledger_error"] = str(e)

    # MVP-6.2 wiring: per-target precision snapshot
    if event_target:
        try:
            rel = relationship_manager.relationships.get(event_target, {})
            ledger = get_ledger()
            active_promises = await ledger.get_active_promises(event_target)
            ledger_strength = 0.8 if active_promises else 0.0
            pctx = build_precision_context(
                uncertainty=emotion_state.uncertainty,
                prediction_error=emotion_state.prediction_error,
                consecutive_prediction_errors=emotion_state._consecutive_prediction_errors,
                ledger_evidence_strength=ledger_strength,
                social_threat=max(0.0, 1.0 - emotion_state.social_safety),
                bond_strength=rel.get("bond", 0.0),
                energy=emotion_state.energy,
                social_safety=emotion_state.social_safety,
                has_promise_context=bool(active_promises),
            )
            pc = get_precision_controller()
            weights, _ = pc.compute_weights(pctx)

            w_action = float(weights.w_action)
            w_memory = float(weights.w_memory)
            w_explore = float(weights.w_explore)

            # Production-path tunable precision raw gain
            precision_raw_gain = float(get_auto_tune_param("precision_raw_gain", 1.0))
            if abs(precision_raw_gain - 1.0) > 1e-9:
                neutral = 1.0 / 3.0
                w_action = max(0.0, min(1.0, neutral + precision_raw_gain * (w_action - neutral)))
                w_memory = max(0.0, min(1.0, neutral + precision_raw_gain * (w_memory - neutral)))
                w_explore = max(0.0, min(1.0, neutral + precision_raw_gain * (w_explore - neutral)))

            # Production-path residual-conditioned gain (small by default, tunable)
            residual_condition_gain = float(get_auto_tune_param("residual_condition_gain", 0.1))
            residual_condition_action_gain = float(get_auto_tune_param("residual_condition_action_gain", 0.25))
            residual_condition_memory_gain = float(get_auto_tune_param("residual_condition_memory_gain", 0.18))
            residual_condition_explore_gain = float(get_auto_tune_param("residual_condition_explore_gain", 0.08))
            residual_condition_tanh_k = float(get_auto_tune_param("residual_condition_tanh_k", 3.0))
            if abs(residual_condition_gain) > 1e-9:
                try:
                    rsum = emotion_state.body_state.get_target_residual_summary(event_target) if event_target else None
                    if rsum:
                        sr = rsum.get("shrunk_residual", {})
                        residual_signal = (-float(sr.get("safety_stress", 0.0)) + float(sr.get("social_need", 0.0)))
                        residual_effect = math.tanh(residual_condition_tanh_k * residual_signal)
                        w_action = max(0.0, min(1.0, w_action + residual_condition_action_gain * residual_condition_gain * residual_effect))
                        w_memory = max(0.0, min(1.0, w_memory - residual_condition_memory_gain * residual_condition_gain * residual_effect))
                        w_explore = max(0.0, min(1.0, w_explore + residual_condition_explore_gain * residual_condition_gain * residual_effect))
                except Exception:
                    pass

            # Smoke-only gain for precision sensitivity probes (keeps production behavior unchanged)
            if isinstance(event.meta, dict) and str(event.meta.get("category", "")).lower() == "smoke" and str(event.meta.get("scenario_name", "")).lower().startswith("smoke_"):
                precision_test_gain = 3.0
                neutral = 1.0 / 3.0

                # 1) amplify deviations from neutral
                w_action = max(0.0, min(1.0, neutral + precision_test_gain * (w_action - neutral)))
                w_memory = max(0.0, min(1.0, neutral + precision_test_gain * (w_memory - neutral)))
                w_explore = max(0.0, min(1.0, neutral + precision_test_gain * (w_explore - neutral)))

                # 2) inject stronger context sensitivity on raw signals before final clamp
                raw_action_signal = (
                    2.0 * (pctx.social_threat - 0.5)
                    + 1.2 * (0.5 - pctx.social_safety)
                    + 0.8 * (0.5 - pctx.energy)
                )
                raw_memory_signal = (
                    1.5 * (pctx.ledger_evidence_strength - 0.3)
                    + 1.0 * (pctx.bond_strength - 0.5)
                    - 0.7 * (pctx.social_threat - 0.5)
                )

                w_action = max(0.0, min(1.0, w_action + 0.35 * math.tanh(raw_action_signal)))
                w_memory = max(0.0, min(1.0, w_memory + 0.35 * math.tanh(raw_memory_signal)))

                # 3) target-conditioned residual signal (strongly separated in smoke scenarios)
                try:
                    rsum = emotion_state.body_state.get_target_residual_summary(event_target) if event_target else None
                    if rsum:
                        sr = rsum.get("shrunk_residual", {})
                        residual_signal = (-float(sr.get("safety_stress", 0.0)) + float(sr.get("social_need", 0.0)))
                        w_action = max(0.0, min(1.0, w_action + 0.45 * math.tanh(3.0 * residual_signal)))
                        w_memory = max(0.0, min(1.0, w_memory - 0.30 * math.tanh(3.0 * residual_signal)))
                except Exception:
                    pass

            _latest_precision_by_target[event_target] = {
                "w_action": w_action,
                "w_memory": w_memory,
                "w_explore": w_explore,
            }
        except Exception:
            pass

    # MVP-4 D1: Reduce uncertainty on observation
    emotion_state.uncertainty = max(0.0, emotion_state.uncertainty - 0.05)
    
    await update_state(
        emotion_state.valence, 
        emotion_state.arousal, 
        emotion_state.subjective_time, 
        emotion_state.prediction_error, 
        emotion_state.regulation_budget,
        emotion_state.social_safety,
        emotion_state.energy
    )
    
    # MVP-4 D1: Update mood state based on affect
    mood_data = await get_mood_state()
    mood_data["valence"] += (emotion_state.valence - mood_data["valence"]) * AFFECT_TO_MOOD_RATE
    mood_data["arousal"] += (emotion_state.arousal - mood_data["arousal"]) * AFFECT_TO_MOOD_RATE
    mood_data["anxiety"] += (emotion_state.anxiety - mood_data["anxiety"]) * AFFECT_TO_MOOD_RATE
    mood_data["joy"] += (emotion_state.joy - mood_data["joy"]) * AFFECT_TO_MOOD_RATE
    mood_data["sadness"] += (emotion_state.sadness - mood_data["sadness"]) * AFFECT_TO_MOOD_RATE
    mood_data["anger"] += (emotion_state.anger - mood_data["anger"]) * AFFECT_TO_MOOD_RATE
    mood_data["loneliness"] += (emotion_state.loneliness - mood_data["loneliness"]) * AFFECT_TO_MOOD_RATE
    mood_data["uncertainty"] = max(0.0, mood_data["uncertainty"] - 0.01)
    await update_mood_state(
        valence=mood_data["valence"],
        arousal=mood_data["arousal"],
        anxiety=mood_data["anxiety"],
        joy=mood_data["joy"],
        sadness=mood_data["sadness"],
        anger=mood_data["anger"],
        loneliness=mood_data["loneliness"],
        uncertainty=mood_data["uncertainty"]
    )
    
    for target, rel_data in relationship_manager.relationships.items():
        await update_relationship(target, rel_data["bond"], rel_data["grudge"], rel_data.get("trust", 0.0), rel_data.get("repair_bank", 0.0))
        # MVP-4 D1: Reduce relationship uncertainty on interaction
        if target == event.get_counterparty_id():  # MVP-7.4
            rel_data["uncertainty"] = max(0.0, rel_data.get("uncertainty", 0.5) - 0.05)
    
    # MVP-4 D2: Appraise the event
    # Build context for appraisal
    target = event.get_counterparty_id()  # MVP-7.4
    bond_state = None
    if target in relationship_manager.relationships:
        rel = relationship_manager.relationships[target]
        bond_state = BondState(
            target=target,
            bond=rel.get("bond", 0.0),
            trust=rel.get("trust", 0.0),
            grudge=rel.get("grudge", 0.0),
            repair_bank=rel.get("repair_bank", 0.0)
        )
    
    # MVP-6.2 D5: Update other-minds model from observed signals
    if target:
        if event.type == "world_event" and event.meta:
            subtype = event.meta.get("subtype", "")
            outcome_map = {
                "care": "care",
                "repair_success": "repair_success",
                "apology": "apology",
                "ignored": "ignored",
                "rejection": "rejection",
                "betrayal": "betrayal",
                "time_passed": "unclear",
            }
            if subtype in outcome_map:
                other_minds_model.update_from_interaction(target, outcome_map[subtype])
            if subtype == "repair_success":
                other_minds_model.update_from_ledger(target, "promise_kept", severity=1.0)
            elif subtype == "betrayal":
                other_minds_model.update_from_ledger(target, "promise_broken", severity=1.0)
        elif event.type == "user_message":
            other_minds_model.update_from_interaction(target, "continue", strength=0.4)

    # Create affect state for appraisal
    affect_state = AffectState(
        valence=emotion_state.valence,
        arousal=emotion_state.arousal,
        anger=emotion_state.anger,
        sadness=emotion_state.sadness,
        anxiety=emotion_state.anxiety,
        joy=emotion_state.joy,
        loneliness=emotion_state.loneliness,
        social_safety=emotion_state.social_safety,
        energy=emotion_state.energy,
        uncertainty=emotion_state.uncertainty
    )
    
    # Create mood state for appraisal
    mood_state = MoodState(
        valence=mood_data["valence"],
        arousal=mood_data["arousal"],
        anxiety=mood_data["anxiety"],
        joy=mood_data["joy"],
        sadness=mood_data["sadness"],
        anger=mood_data["anger"],
        loneliness=mood_data["loneliness"],
        uncertainty=mood_data["uncertainty"]
    )
    
    # Perform appraisal
    appraisal_result = appraise_event(
        event=event,
        affect=affect_state,
        mood=mood_state,
        bond=bond_state,
        target=target
    )
    
    # MVP-5 D2: Update allostasis budget
    budget = get_allostasis_budget()
    budget_deltas = []
    
    # Handle time_passed recovery
    if event.type == "world_event" and event.meta and event.meta.get("subtype") == "time_passed":
        seconds = event.meta.get("seconds", 60)
        delta = budget.apply_time_passed(seconds)
        budget_deltas.append(delta.to_dict())
    
    # Handle prediction error depletion
    if prediction_error > 0.1:
        # Check if consecutive
        is_consecutive = emotion_state._consecutive_prediction_errors >= 2
        delta = budget.on_prediction_error(prediction_error, is_consecutive)
        budget_deltas.append(delta.to_dict())
        emotion_state._consecutive_prediction_errors += 1
    else:
        emotion_state._consecutive_prediction_errors = 0
    
    # Handle high uncertainty depletion
    if emotion_state.uncertainty > 0.6:
        delta = budget.on_high_uncertainty(emotion_state.uncertainty)
        if delta:
            budget_deltas.append(delta.to_dict())
    
    # Handle event subtype impacts
    if event.type == "world_event" and event.meta:
        subtype = event.meta.get("subtype")
        if subtype:
            delta = budget.on_event_subtype(subtype)
            if delta:
                budget_deltas.append(delta.to_dict())
    
    # Handle user message impacts
    if event.type == "user_message" and event.text:
        is_negative = any(w in event.text.lower() for w in ["bad", "hate", "stupid", "wrong", "angry", "terrible", "awful", "horrible"])
        is_positive = any(w in event.text.lower() for w in ["good", "great", "thanks", "love", "happy"])
        delta = budget.on_user_message(is_negative=is_negative, is_positive=is_positive)
        if delta:
            budget_deltas.append(delta.to_dict())
    
    # Update emotion_state energy_budget
    emotion_state.energy_budget = budget.budget
    
    # Record budget trace to database
    from emotiond.db import record_budget_trace
    for delta_dict in budget_deltas:
        await record_budget_trace(
            budget_value=delta_dict["new_value"],
            delta=delta_dict["delta"],
            reason=delta_dict["reason"],
            metadata=delta_dict.get("metadata", {})
        )
    

    # MVP-7.6 Phase 2: Apply event to SelfModelV0 and get self_conflict
    self_model_v0_result = None
    self_conflict = 0.0
    self_model_hash = None
    
    if target:
        self_model_v0 = get_self_model_v0(target)
        # Build context for self_model
        ctx = {
            "relationship_state": relationship_manager.relationships.get(target, {}),
            "emotion_state": {
                "valence": emotion_state.valence,
                "arousal": emotion_state.arousal,
                "uncertainty": emotion_state.uncertainty,
                "social_safety": emotion_state.social_safety,
                "energy": emotion_state.energy,
            },
        }
        self_model_v0_result = self_model_v0.apply_event(event_dict, ctx)
        self_conflict = self_model_v0_result.get("self_conflict", 0.0)
        self_model_hash = self_model_v0.compute_hash()
        
        # OpenEmotion Self-Model Adapter (P0 main-chain wiring)
        # Shadow mode: 双轨运行，收集对比数据
        if _openemotion_self_model and ENABLE_OPENEMOTION_SELF_MODEL:
            try:
                _openemotion_self_model.apply_event(event_dict, ctx)
            except Exception as e:
                # Shadow mode: 不影响主链
                pass
        
        # MVP13: Mirror read (read-only, no write to legacy)
        if _mvp13_mirror and ENABLE_MVP13_MIRROR:
            try:
                mirrored_state = _mvp13_mirror.mirror_from_legacy(self_model_v0)
                # Only for verification, does NOT affect main chain
                logger.debug(f"[MVP13-MIRROR] Mirror success: {mirrored_state is not None}")
            except Exception as e:
                logger.debug(f"[MVP13-MIRROR] Error: {e}")
        
        # Log to audit (events table already has the event, but we add self_model info)
        # The self_conflict and hash are included in the result below

    result = {
        "status": "processed",
        "valence": emotion_state.valence,
        "arousal": emotion_state.arousal,
        "prediction_error": emotion_state.prediction_error,
        "memory_strength": memory_strength,
        "regulation_budget": emotion_state.regulation_budget,
        "social_safety": emotion_state.social_safety,  # MVP-3 B1
        "energy": emotion_state.energy,  # MVP-3 B1
        "uncertainty": emotion_state.uncertainty,  # MVP-4 D1
        # MVP-5 D2: Energy budget
        "energy_budget": emotion_state.energy_budget,
        "budget_deltas": budget_deltas,
        "fatigue_level": budget.fatigue_level,
        # MVP-4 D2: Appraisal result
        "appraisal": appraisal_result.model_dump(),
        "body_trace": body_trace,
        "precision_snapshot": _latest_precision_by_target.get(target, {}),
        # MVP-7.6 Phase 2: Self-model info
        "self_conflict": self_conflict,
        "self_model_hash": self_model_hash,
        "self_model_result": self_model_v0_result
    }
    
    # Include time_passed audit info in response if applicable
    if time_passed_audit:
        result["time_passed_audit"] = time_passed_audit

    # MVP-8: Self-reflection loop (auditable report per event/turn)
    try:
        reflection_target_id = resolve_target_id(event)
        reflection_seed = 0
        if isinstance(event.meta, dict):
            reflection_seed = int(event.meta.get("reflection_seed", 0) or 0)
        reflection_bundle = run_reflection(
            event=event,
            process_result=result,
            target_id=reflection_target_id,
            counterparty_id=event.get_counterparty_id(),
            seed=reflection_seed,
            base_dir="reports",
        )
        result["self_report"] = reflection_bundle["report"]
        result["self_report_path"] = reflection_bundle["report_path"]
        result["self_report_index_path"] = reflection_bundle["index_path"]
    except Exception as e:
        result["self_report_error"] = str(e)

    # MVP11.5: Run intent checker for assistant_reply events (shadow mode)
    if event.type == "assistant_reply" and event.text:
        try:
            from emotiond.self_report_consistency_checker import check_consistency
            from emotiond.response_intent_checker import check_intent
            from emotiond.self_report_interpreter import interpret_to_intent_contract
            
            # Get relationship state for this target
            rel = relationship_manager.relationships.get(target, {"bond": 0.5, "trust": 0.5})
            
            raw_state = {
                "affect": {
                    "joy": emotion_state.joy,
                    "loneliness": emotion_state.loneliness,
                    "anxiety": emotion_state.anxiety,
                },
                "mood": {
                    "valence": emotion_state.valence,
                    "arousal": emotion_state.arousal,
                },
                "bonds": {target: {"bond": rel.get("bond", 0.5), "trust": rel.get("trust", 0.5)}}
            }
            contract = interpret_to_intent_contract(raw_state, mode="interpreted")
            checker_result = check_intent(event.text, contract, session_id=event.actor or "runtime")
            result["intent_check"] = checker_result
        except Exception as e:
            result["intent_check_error"] = str(e)

    # MVP15: Shadow reflection mode (read-only, generates artifacts)
    if ENABLE_MVP15_SHADOW:
        try:
            from emotiond.reflection_shadow import get_reflection_shadow
            shadow = get_reflection_shadow()
            if shadow.enable:
                # Create state snapshot for reflection
                state_snapshot = {
                    "emotion": {
                        "valence": emotion_state.valence,
                        "arousal": emotion_state.arousal,
                        "joy": emotion_state.joy,
                        "loneliness": emotion_state.loneliness,
                    },
                    "target": target,
                    "event_type": event.type,
                }
                # Process in shadow mode (read-only, no state modification)
                shadow.process_event(dict(result) if isinstance(result, dict) else {}, state_snapshot)
        except Exception as e:
            import logging
            logging.getLogger("emotiond.core").debug(f"[MVP15-SHADOW] Error: {e}")

    return result


async def generate_plan(request: PlanRequest) -> PlanResponse:
    from emotiond.db import get_mood_state
    

    # MVP-7 US-705: Check for meta-cognitive override
    if hasattr(request, 'user_text') and request.user_text:
        # Get current states for conflict detection
        drive_state = DriveState()
        drive_state.fatigue = 1.0 - emotion_state.energy  # Proxy fatigue from energy
        drive_state.uncertainty = emotion_state.uncertainty
        
        # MVP14: Dual-run comparison (read-only)
        if _mvp14_adapter and ENABLE_MVP14_DUAL_RUN:
            try:
                # Compare legacy params with new manager
                legacy_params = get_drive_modulation_params(drive_state)
                new_state = _mvp14_adapter.get_new_state()
                # Log for diff analysis (no behavior change)
                if _mvp14_adapter.metrics.legacy_calls % 50 == 0:
                    import logging
                    logging.getLogger("emotiond.core").info(
                        f"[MVP14-DUAL] legacy_risk={legacy_params['risk_aversion']:.4f}, "
                        f"adapter_errors={_mvp14_adapter.metrics.errors}"
                    )
            except Exception as e:
                import logging
                logging.getLogger("emotiond.core").debug(f"[MVP14-DUAL] Error: {e}")
        
        # Check for meta-cognitive conflicts
        override_result = check_meta_cognitive_override(
            prompt=request.user_text,
            emotion_state=emotion_state,
            body_state=emotion_state.body_state,
            drive_state=drive_state,
            allostasis_budget=emotion_state.energy_budget,
            context={
                "target": request.get_counterparty_id(),
                "target_id": request.get_target_id(),
                "agent_id": request.get_agent_id(),
                "language": getattr(request, "language", "en")
            }
        )
        
        if override_result.get("override", False):
            # Return rejection response with proper reason codes
            rejection = override_result["rejection"]
            return PlanResponse(
                tone="rejected",
                intent="reject",
                focus_target=request.get_counterparty_id(),
                key_points=[f"Meta-cognitive conflict: {rejection['reason_code']}"],
                constraints=[rejection["message"]],
                emotion={
                    "valence": emotion_state.valence,
                    "arousal": emotion_state.arousal,
                    "anger": emotion_state.anger,
                    "sadness": emotion_state.sadness,
                    "anxiety": emotion_state.anxiety,
                    "joy": emotion_state.joy,
                    "loneliness": emotion_state.loneliness
                },
                relationship={"bond": 0.0, "grudge": 0.0, "trust": 0.0, "repair_bank": 0.0},
                regulation_budget=emotion_state.regulation_budget,
                mood=MoodResponse(
                    valence=emotion_state.valence,
                    arousal=emotion_state.arousal,
                    anxiety=emotion_state.anxiety,
                    joy=emotion_state.joy,
                    sadness=emotion_state.sadness,
                    anger=emotion_state.anger,
                    loneliness=emotion_state.loneliness,
                    uncertainty=emotion_state.uncertainty
                ),
                uncertainty=emotion_state.uncertainty,
                bond_uncertainty=0.5,
                energy_budget=emotion_state.energy_budget,
                language_guidance="REJECTED: " + rejection["reason_code"],
                w_explore=0.0,
                learning_rate_multiplier=0.0,
                self_report=f"Meta-cognitive override: {rejection['reason_code']} (confidence: {rejection['confidence']:.2f})"
            )
    current_valence = emotion_state.valence
    current_arousal = emotion_state.arousal
    # Phase D (P1.1): Resolve identity fields with explicit semantics
    # target_id = 会话隔离键 (conversationId) - for prediction lookups
    # counterparty_id = 关系对象 - for relationship state lookup
    # These are intentionally separate to avoid "关系账本随会话漂移"
    target_id = request.get_target_id()
    counterparty_id = request.get_counterparty_id()
    agent_id = request.get_agent_id()
    
    # For backward compatibility, focus_target still refers to relationship target
    focus_target = counterparty_id
    # Phase D (P1.1): Use counterparty_id for relationship lookup (not target_id)
    target_relationship = relationship_manager.relationships.get(counterparty_id, {"bond": 0.0, "grudge": 0.0, "trust": 0.0, "repair_bank": 0.0, "uncertainty": 0.5})
    
    if current_valence > 0.3 and current_arousal < 0.5:
        tone = "warm"
    elif current_valence > 0:
        tone = "soft"
    elif current_valence < -0.3 and target_relationship["grudge"] > 0.5:
        tone = "cold"
    else:
        tone = "guarded"
    
    # MVP-7.6: Use select_action_with_explanation to respect action_bias from SelfModelV0
    # This replaces the hardcoded if-else rules and other_minds bias
    try:
        action_result = await select_action_with_explanation(focus_target, test_mode=False)
        selected_action = action_result["action"]
        # Map ACTION_SPACE to intent names
        # ACTION_SPACE = ["approach", "repair_offer", "boundary", "withdraw", "attack"]
        action_to_intent = {
            "approach": "seek",
            "repair_offer": "repair",
            "boundary": "set_boundary",
            "withdraw": "distance",
            "attack": "retaliate"
        }
        intent = action_to_intent.get(selected_action, selected_action)
    except Exception:
        # Fallback to simple heuristic if select_action fails
        if current_valence < -0.1:
            intent = "repair"
        elif target_relationship["bond"] > 0.6:
            intent = "seek"
        else:
            intent = "set_boundary"
    
    key_points, constraints = [], []
    if intent == "repair":
        key_points, constraints = ["Acknowledge the emotional state", "Express willingness to improve"], ["Avoid defensiveness", "Focus on understanding"]
    elif intent == "seek":
        key_points, constraints = ["Express curiosity", "Ask engaging questions"], ["Be authentic", "Show genuine interest"]
    elif intent == "distance":
        key_points, constraints = ["Maintain professional boundaries", "Keep responses concise"], ["Avoid emotional entanglement", "Stay objective"]
    elif intent == "retaliate":
        key_points, constraints = ["Assert boundaries clearly", "Address the issue directly"], ["Avoid escalation", "Maintain professionalism"]
    else:
        key_points, constraints = ["Establish clear expectations", "Communicate needs"], ["Be firm but respectful", "Avoid ambiguity"]
    
    relationship_dict = {"bond": target_relationship["bond"], "grudge": target_relationship["grudge"], "trust": target_relationship.get("trust", 0.0), "repair_bank": target_relationship.get("repair_bank", 0.0)}

    ledger = get_ledger()
    focus_ledger = ledger.get_summary_for_target(focus_target) if hasattr(ledger, "get_summary_for_target") else {}
    # MVP-7.6: Use get_self_model_v0 to get the global instance (preserves process_event updates)
    self_state_v0 = get_self_model_v0(focus_target)
    # Sync current emotion_state and relationship to the instance
    self_state_v0.bodily.energy = float(getattr(emotion_state, "energy", 0.7))
    self_state_v0.bodily.social_safety = float(getattr(emotion_state, "social_safety", 0.6))
    self_state_v0.bodily.focus_fatigue = max(0.0, min(1.0, 1.0 - float(getattr(emotion_state, "energy_budget", 1.0))))
    self_state_v0.relational.bond = float(target_relationship.get("bond", 0.5))
    self_state_v0.relational.grudge = float(target_relationship.get("grudge", 0.0))
    self_state_v0.relational.trust = float(target_relationship.get("trust", 0.5))
    self_state_v0.relational.repair_bank = float(target_relationship.get("repair_bank", 0.0))
    self_state_v0.cognitive.uncertainty = float(getattr(emotion_state, "uncertainty", 0.5))
    self_state_v0.cognitive.confidence = max(0.0, min(1.0, 1.0 - float(getattr(emotion_state, "uncertainty", 0.5))))
    self_state_v0.cognitive.regulation_budget = float(getattr(emotion_state, "regulation_budget", 1.0))
    self_report = render_self_report(self_state_v0, evidence={"ledger": focus_ledger, "episode_refs": []})

    # MVP11.5: Generate intent contract for response generation
    intent_contract = None
    try:
        from emotiond.self_report_interpreter import interpret_to_intent_contract
        raw_state_for_contract = {
            "affect": {
                "joy": emotion_state.joy,
                "loneliness": emotion_state.loneliness,
                "anxiety": emotion_state.anxiety,
            },
            "mood": mood_data,
            "bonds": {focus_target: relationship_dict}
        }
        intent_contract = interpret_to_intent_contract(raw_state_for_contract, mode="interpreted")
    except Exception as e:
        pass  # Contract generation is optional, don't break plan if it fails
    
    include_all = os.environ.get("EMOTIOND_PLAN_INCLUDE_RELATIONSHIPS", "0") == "1"
    all_relationships = None
    if include_all:
        all_relationships = {t: {"bond": r["bond"], "grudge": r["grudge"], "trust": r.get("trust", 0.0), "repair_bank": r.get("repair_bank", 0.0)} for t, r in relationship_manager.relationships.items()}
    
    emotion_dict = {"valence": current_valence, "arousal": current_arousal, "anger": emotion_state.anger, "sadness": emotion_state.sadness, "anxiety": emotion_state.anxiety, "joy": emotion_state.joy, "loneliness": emotion_state.loneliness}
    
    # MVP-4 D1: Get mood state (fallback-safe for tests without DB init)
    try:
        mood_data = await get_mood_state()
    except Exception:
        mood_data = {
            "valence": emotion_state.valence,
            "arousal": emotion_state.arousal,
            "anxiety": emotion_state.anxiety,
            "joy": emotion_state.joy,
            "sadness": emotion_state.sadness,
            "anger": emotion_state.anger,
            "loneliness": emotion_state.loneliness,
            "uncertainty": emotion_state.uncertainty,
        }
    mood_response = MoodResponse(
        valence=mood_data["valence"],
        arousal=mood_data["arousal"],
        anxiety=mood_data["anxiety"],
        joy=mood_data["joy"],
        sadness=mood_data["sadness"],
        anger=mood_data["anger"],
        loneliness=mood_data["loneliness"],
        uncertainty=mood_data["uncertainty"]
    )
    
    # MVP-5 D2: Get energy budget guidance
    budget = get_allostasis_budget()
    language_guidance = budget.get_language_guidance()
    w_explore_adjusted = budget.get_explore_weight(0.5)
    learning_rate_multiplier = budget.get_learning_rate_multiplier()
    
    # Adjust key_points based on fatigue
    if budget.is_low:
        key_points.append(f"Note: Low energy budget ({budget.budget:.2f}) - using concise responses")
        constraints.append("Keep response brief due to fatigue")
    
    return PlanResponse(
        tone=tone, intent=intent, focus_target=focus_target, key_points=key_points, 
        constraints=constraints, emotion=emotion_dict, relationship=relationship_dict, 
        relationships=all_relationships, regulation_budget=emotion_state.regulation_budget,
        # MVP-4 D1: Hierarchical state system
        mood=mood_response,
        uncertainty=emotion_state.uncertainty,
        bond_uncertainty=target_relationship.get("uncertainty", 0.5),
        # MVP-5 D2: Energy budget guidance
        energy_budget=emotion_state.energy_budget,
        language_guidance=language_guidance,
        w_explore=w_explore_adjusted,
        learning_rate_multiplier=learning_rate_multiplier,
        self_report=self_report,
        intent_contract=intent_contract
    )


async def homeostasis_loop():
    last_time = time.time()
    while True:
        current_time = time.time()
        real_dt = current_time - last_time
        last_time = current_time
        emotion_state.apply_homeostasis_drift(real_dt)
        await update_state(
            emotion_state.valence, 
            emotion_state.arousal, 
            emotion_state.subjective_time, 
            emotion_state.prediction_error, 
            emotion_state.regulation_budget,
            emotion_state.social_safety,
            emotion_state.energy
        )
        await asyncio.sleep(1)


async def consolidation_loop():
    while True:
        relationship_manager.apply_consolidation_drift()
        await memory_system.summarize_memories()
        for target, rel_data in relationship_manager.relationships.items():
            await update_relationship(target, rel_data["bond"], rel_data["grudge"], rel_data.get("trust", 0.0), rel_data.get("repair_bank", 0.0))
        await asyncio.sleep(30)


# MVP-3 B6: Action Selection Functions

def score_action(
    action: str,
    state: EmotionState,
    relationship: Dict[str, float],
    predictions: Dict[str, Dict[str, float]]
) -> float:
    """
    MVP-3 B6: Score an action based on relationship, prediction, and uncertainty.
    
    Args:
        action: The action to score
        state: Current emotional state
        relationship: Relationship dict with bond, grudge, trust, repair_bank
        predictions: Prediction dict for this action
    
    Returns:
        Float score for the action
    """
    w = ACTION_SCORE_WEIGHTS
    
    # Relationship benefit
    rel_score = (
        w["bond"] * relationship.get("bond", 0.0) +
        w["grudge"] * relationship.get("grudge", 0.0) +
        w["trust"] * relationship.get("trust", 0.0)
    )
    
    # Predicted change
    pred_safety = predictions.get("social_safety_delta", 0.0)
    pred_energy = predictions.get("energy_delta", 0.0)
    pred_score = w["safety"] * pred_safety + w["energy"] * pred_energy
    
    # Uncertainty penalty
    prediction_count = predictions.get("prediction_count", 0)
    prediction_error_sum = predictions.get("prediction_error_sum", 0.0)
    uncertainty = prediction_error_sum / prediction_count if prediction_count > 0 else 0.0
    uncertainty_penalty = -w["uncertainty"] * abs(uncertainty)
    
    return rel_score + pred_score + uncertainty_penalty


def select_action(
    state: EmotionState,
    target: str,
    test_mode: bool = False
) -> str:
    """
    MVP-3 B6: Select an action for a target.
    
    Args:
        state: Current emotional state
        target: Target identifier
        test_mode: If True, use argmax; if False, use softmax
    
    Returns:
        Selected action string
    """
    global _predictions
    
    relationship = relationship_manager.relationships.get(target, {"bond": 0.0, "grudge": 0.0, "trust": 0.0, "repair_bank": 0.0})

    # Residual-conditioned policy bias (production-path, small default)
    residual_condition_gain = float(get_auto_tune_param("residual_condition_gain", 0.1))
    residual_policy_bias_gain = float(get_auto_tune_param("residual_policy_bias_gain", 0.10))
    residual_condition_tanh_k = float(get_auto_tune_param("residual_condition_tanh_k", 3.0))
    residual_signal = 0.0
    try:
        if hasattr(state, "body_state") and hasattr(state.body_state, "get_target_residual_summary"):
            rsum = state.body_state.get_target_residual_summary(target)
            if rsum:
                sr = rsum.get("shrunk_residual", {})
                residual_signal = (-float(sr.get("safety_stress", 0.0)) + float(sr.get("social_need", 0.0)))
    except Exception:
        residual_signal = 0.0
    
    # Score all actions
    scores = {}
    for action in ACTION_SPACE:
        pred = _predictions.get(action, {
            "social_safety_delta": 0.0,
            "energy_delta": 0.0,
            "prediction_error_sum": 0.0,
            "prediction_count": 0
        })
        score = score_action(action, state, relationship, pred)
        if abs(residual_condition_gain) > 1e-9 and abs(residual_signal) > 1e-9:
            resid_bias = residual_condition_gain * residual_policy_bias_gain * math.tanh(residual_condition_tanh_k * residual_signal)
            if action in {"withdraw", "boundary"}:
                score += resid_bias
            elif action in {"approach", "repair_offer"}:
                score -= resid_bias
        # MVP-7.6 Phase 2: Apply self_model action_bias
        try:
            self_model_v0 = get_self_model_v0(target)
            self_bias = self_model_v0.get_action_bias(action)
            self_bias_weight = float(get_auto_tune_param("self_bias_weight", 0.2))
            score += self_bias_weight * self_bias
        except Exception:
            pass  # Self-model bias is optional enhancement
        scores[action] = score
    
    if test_mode or TEST_MODE:
        # Deterministic: argmax
        best_action = max(scores.keys(), key=lambda a: scores[a])
    else:
        # Stochastic: softmax
        temp = SOFTMAX_TEMPERATURE
        max_score = max(scores.values())
        exp_scores = {a: math.exp((s - max_score) / temp) for a, s in scores.items()}
        sum_exp = sum(exp_scores.values())
        probs = {a: e / sum_exp for a, e in exp_scores.items()}
        
        # Sample from distribution
        import random
        r = random.random()
        cumsum = 0.0
        best_action = ACTION_SPACE[0]
        for a, p in probs.items():
            cumsum += p
            if r <= cumsum:
                best_action = a
                break
    
    return best_action


async def get_action_scores(target: str) -> Dict[str, Any]:
    """
    Get action scores for a target (useful for debugging/explanation).
    
    Returns:
        dict with scores and selected action
    """
    global _predictions
    
    relationship = relationship_manager.relationships.get(target, {"bond": 0.0, "grudge": 0.0, "trust": 0.0, "repair_bank": 0.0})
    
    scores = {}
    for action in ACTION_SPACE:
        pred = _predictions.get(action, {
            "social_safety_delta": 0.0,
            "energy_delta": 0.0,
            "prediction_error_sum": 0.0,
            "prediction_count": 0
        })
        scores[action] = score_action(action, emotion_state, relationship, pred)
    
    selected = select_action(emotion_state, target)
    
    return {
        "target": target,
        "scores": scores,
        "selected": selected,
        "relationship": relationship,
        "interoception": {
            "social_safety": emotion_state.social_safety,
            "energy": emotion_state.energy
        }
    }


# MVP-3 C1: Structured Explanation Generation
async def generate_explanation(
    target: str,
    selected_action: Optional[str] = None,
    test_mode: bool = False
) -> Dict[str, Any]:
    """
    MVP-3 C1: Generate a structured explanation for action selection.
    
    Args:
        target: Target identifier
        selected_action: Pre-selected action (if None, will select one)
        test_mode: If True, use deterministic selection
    
    Returns:
        dict with emotion, interoception, relationships, candidates, selected, selection_reasons
    """
    global _predictions
    
    # Get current state
    state = emotion_state
    
    # Build emotion section - top 2 emotions + all 5D
    emotion_values = {
        "anger": state.anger,
        "sadness": state.sadness,
        "anxiety": state.anxiety,
        "joy": state.joy,
        "loneliness": state.loneliness
    }
    
    # Sort by value descending, get top 2
    sorted_emotions = sorted(emotion_values.items(), key=lambda x: x[1], reverse=True)
    top2 = [(name, value) for name, value in sorted_emotions[:2] if value > 0.0]
    
    emotion_section = {
        "top2": top2,
        "all": emotion_values
    }
    
    # Build interoception section
    interoception_section = {
        "social_safety": state.social_safety,
        "energy": state.energy
    }
    
    # Build relationships section for target
    relationship = relationship_manager.relationships.get(target, {"bond": 0.0, "grudge": 0.0, "trust": 0.0, "repair_bank": 0.0})
    relationships_section = {
        "bond": relationship.get("bond", 0.0),
        "grudge": relationship.get("grudge", 0.0),
        "trust": relationship.get("trust", 0.0),
        "repair_bank": relationship.get("repair_bank", 0.0)
    }
    
    # Build candidates section - score all actions
    scores = {}
    predicted_deltas = {}
    for action in ACTION_SPACE:
        pred = _predictions.get(action, {
            "social_safety_delta": 0.0,
            "energy_delta": 0.0,
            "prediction_error_sum": 0.0,
            "prediction_count": 0
        })
        scores[action] = score_action(action, state, relationship, pred)
        predicted_deltas[action] = {
            "safety": pred.get("social_safety_delta", 0.0),
            "energy": pred.get("energy_delta", 0.0)
        }
    
    # Get top 3 candidates by score
    sorted_actions = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top3 = sorted_actions[:3]
    
    # Generate reasons for each candidate
    candidates = []
    for action, score in top3:
        reasons = _generate_action_reasons(action, state, relationship, predicted_deltas[action])
        candidates.append({
            "action": action,
            "score": score,
            "predicted_delta": predicted_deltas[action],
            "reasons": reasons
        })
    
    # Select action if not provided
    if selected_action is None:
        if test_mode:
            selected_action = sorted_actions[0][0]
        else:
            selected_action = select_action(state, target, test_mode)

    # Persistence objective/tradeoff integration (MVP-6.2 D4)
    persistence = get_persistence_constraint()
    focus_fatigue_proxy = max(0.0, min(1.0, 0.5 * state.anxiety + 0.5 * (1.0 - state.energy)))
    persistence.update_body_state(energy=state.energy, safety_stress=1.0 - state.social_safety, focus_fatigue=focus_fatigue_proxy)
    persistence.update_relationship(target, bond=relationship.get("bond", 0.0), reliability=relationship.get("trust", 0.5), trust=relationship.get("trust", 0.5))

    prediction_uncertainty = []
    for action in ACTION_SPACE:
        pred = _predictions.get(action, {})
        n = pred.get("prediction_count", 0)
        err = pred.get("prediction_error_sum", 0.0)
        prediction_uncertainty.append((err / n) if n > 0 else 0.0)
    ambiguity = max(0.0, min(1.0, sum(abs(x) for x in prediction_uncertainty) / max(1, len(prediction_uncertainty))))
    risk = max(0.0, min(1.0, relationship.get("grudge", 0.0) * 0.7 + (1.0 - relationship.get("trust", 0.0)) * 0.3))
    expected_info_gain = max(0.0, 1.0 - ambiguity)

    p_strategy, p_reason, p_trace = persistence.select_strategy_with_tradeoff(
        target_id=target,
        risk=risk,
        ambiguity=ambiguity,
        expected_info_gain=expected_info_gain,
    )

    policy_override = None
    if not test_mode:
        if p_strategy.value == "retreat" and selected_action != "withdraw":
            policy_override = f"retreat_override:{selected_action}->withdraw"
            selected_action = "withdraw"
        elif p_strategy.value == "conservative" and selected_action == "attack":
            policy_override = "conservative_override:attack->boundary"
            selected_action = "boundary"
        elif p_strategy.value == "repair" and selected_action in ["attack", "withdraw"]:
            policy_override = f"repair_override:{selected_action}->repair_offer"
            selected_action = "repair_offer"

    # Generate selection reasons
    selection_reasons = _generate_selection_reasons(selected_action, state, relationship, scores)

    explanation = {
        "emotion": emotion_section,
        "interoception": interoception_section,
        "relationships": relationships_section,
        "candidates": candidates,
        "selected": selected_action,
        "selection_reasons": selection_reasons,
        "persistence": {
            "strategy": p_strategy.value,
            "reason": p_reason,
            "trace": p_trace.to_dict(),
            "policy_override": policy_override,
        }
    }
    
    return explanation


def _generate_action_reasons(
    action: str,
    state: EmotionState,
    relationship: Dict[str, float],
    predicted_delta: Dict[str, float]
) -> List[str]:
    """Generate human-readable reasons for an action's score."""
    reasons = []
    
    # Relationship-based reasons
    if relationship.get("bond", 0) > 0.5:
        reasons.append("High bond with target")
    if relationship.get("grudge", 0) > 0.5:
        reasons.append("Existing grudge")
    if relationship.get("trust", 0) < 0.3:
        reasons.append("Low trust")
    
    # State-based reasons
    if state.social_safety < 0.4:
        reasons.append("Low social safety")
    if state.energy < 0.4:
        reasons.append("Low energy")
    
    # Prediction-based reasons
    if predicted_delta.get("safety", 0) > 0.02:
        reasons.append(f"Predicted to improve safety (+{predicted_delta['safety']:.2f})")
    if predicted_delta.get("energy", 0) > 0.01:
        reasons.append(f"Energy-preserving (+{predicted_delta['energy']:.2f})")
    if predicted_delta.get("safety", 0) < -0.02:
        reasons.append("Risk of safety reduction")
    
    # Action-specific reasons
    if action == "approach" and state.social_safety > 0.5:
        reasons.append("Safe to approach")
    if action == "repair_offer" and relationship.get("grudge", 0) > 0.3:
        reasons.append("Opportunity for repair")
    if action == "boundary" and relationship.get("trust", 0) < 0.4:
        reasons.append("Boundary needed for protection")
    if action == "withdraw" and state.social_safety < 0.4:
        reasons.append("Conservative choice for low safety")
    if action == "attack" and relationship.get("grudge", 0) > 0.7:
        reasons.append("Strong grudge motivates retaliation")
    
    # Default reason if none generated
    if not reasons:
        reasons.append(f"Neutral expected outcome")
    
    return reasons


def _generate_selection_reasons(
    selected_action: str,
    state: EmotionState,
    relationship: Dict[str, float],
    scores: Dict[str, float]
) -> List[str]:
    """Generate reasons for why this action was selected."""
    reasons = []
    
    # Check if selected has highest score
    max_score_action = max(scores.keys(), key=lambda a: scores[a])
    if selected_action == max_score_action:
        reasons.append("Highest score given current state")
    else:
        reasons.append(f"Selected via stochastic process (score: {scores[selected_action]:.3f})")
    
    # State-based reasons
    if state.social_safety < 0.4:
        reasons.append("Low social safety favors conservative action")
    if state.energy < 0.4:
        reasons.append("Low energy favors efficient action")
    
    # Relationship-based reasons
    if relationship.get("grudge", 0) > 0.5:
        reasons.append("High grudge influences selection")
    if relationship.get("trust", 0) < 0.3:
        reasons.append("Low trust increases caution")
    
    # Action-specific reasons
    if selected_action == "withdraw":
        reasons.append("Withdrawal preserves safety and energy")
    elif selected_action == "approach":
        reasons.append("Approach builds connection")
    elif selected_action == "repair_offer":
        reasons.append("Repair attempt may reduce grudge")
    elif selected_action == "boundary":
        reasons.append("Boundary establishes protection")
    elif selected_action == "attack":
        reasons.append("Attack addresses perceived threat")
    
    return reasons[:3]  # Limit to top 3 reasons


async def select_action_with_explanation(
    target: str,
    test_mode: bool = False
) -> Dict[str, Any]:
    """
    MVP-3 C1: Select an action and generate explanation, storing it in DB.
    
    Args:
        target: Target identifier
        test_mode: If True, use deterministic selection
    
    Returns:
        dict with action, explanation, and decision_id
    """
    from emotiond.db import save_decision
    
    # Ensure relationship exists
    relationship_manager._ensure_relationship_fields(target)
    
    # Generate explanation (which includes action selection)
    explanation = await generate_explanation(target, test_mode=test_mode)
    selected_action = explanation["selected"]
    
    # Save decision to database
    decision_id = await save_decision(selected_action, explanation, target_id=target)
    
    # Update relationship with last action
    relationship_manager.set_last_action(target, selected_action)
    await update_relationship(
        target,
        relationship_manager.relationships[target]["bond"],
        relationship_manager.relationships[target]["grudge"],
        relationship_manager.relationships[target].get("trust", 0.0),
        relationship_manager.relationships[target].get("repair_bank", 0.0),
        selected_action
    )
    
    return {
        "action": selected_action,
        "explanation": explanation,
        "decision_id": decision_id
    }


# MVP-3.1: Target ID resolution
def resolve_target_id(event: 'Event') -> str:
    """
    MVP-3.1: Resolve target_id from event meta.
    
    Priority:
    1. meta.target_id (if provided by system/openclaw)
    2. meta.client_source (if provided)
    3. "default"
    
    Args:
        event: The event to extract target_id from
    
    Returns:
        target_id string
    """
    if event.meta:
        # Priority 1: explicit target_id
        if "target_id" in event.meta:
            return str(event.meta["target_id"])
        # Priority 2: client_source
        if "client_source" in event.meta:
            return str(event.meta["client_source"])
    return "default"


def calculate_shrinkage_alpha(n: int, k: int = None) -> float:
    """
    MVP-3.1: Calculate shrinkage factor for partial pooling.
    
    α = n / (n + k)
    
    - n=0 → α=0 (fully trust global)
    - n→∞ → α→1 (fully trust target-specific)
    
    Args:
        n: Number of samples for this target/action
        k: Shrinkage parameter (default from config)
    
    Returns:
        float α in [0, 1)
    """
    if k is None:
        from emotiond.config import SHRINKAGE_K
        k = SHRINKAGE_K
    
    if n <= 0:
        return 0.0
    
    return n / (n + k)


# MVP-3.1: Target-specific prediction functions
async def load_target_predictions_cache(target_id: str, test_mode: bool = False) -> Dict[str, Dict[str, Any]]:
    """
    MVP-3.1: Load target predictions into cache and return them.

    Args:
        target_id: The target identifier
        test_mode: If True, clear cache entry to ensure test isolation
    """
    global _target_predictions

    # MVP-7.6.1: Test isolation - clear cache entry in test mode
    if test_mode and target_id in _target_predictions:
        del _target_predictions[target_id]

    if target_id not in _target_predictions:
        _target_predictions[target_id] = await load_target_predictions(target_id)

    return _target_predictions[target_id]
    return _target_predictions[target_id]
def compute_combined_prediction(
    global_pred: Dict[str, float],
    target_pred: Dict[str, Any],
    alpha: float
) -> Dict[str, float]:
    """
    MVP-3.1: Compute combined prediction using shrinkage factor.
    
    pred_total = pred_global + α * pred_residual
    
    Args:
        global_pred: Global prediction {social_safety_delta, energy_delta}
        target_pred: Target prediction {social_safety_delta, energy_delta, n, ...}
        alpha: Shrinkage factor [0, 1)
    
    Returns:
        Combined prediction {safety, energy, alpha, global_safety, global_energy, residual_safety, residual_energy}
    """
    global_safety = global_pred.get("social_safety_delta", 0.0)
    global_energy = global_pred.get("energy_delta", 0.0)
    
    residual_safety = target_pred.get("social_safety_delta", 0.0)
    residual_energy = target_pred.get("energy_delta", 0.0)
    
    combined_safety = global_safety + alpha * residual_safety
    combined_energy = global_energy + alpha * residual_energy
    
    # Clamp
    from emotiond.config import DELTA_CLAMP_MIN, DELTA_CLAMP_MAX
    combined_safety = max(DELTA_CLAMP_MIN, min(DELTA_CLAMP_MAX, combined_safety))
    combined_energy = max(DELTA_CLAMP_MIN, min(DELTA_CLAMP_MAX, combined_energy))
    
    return {
        "safety": combined_safety,
        "energy": combined_energy,
        "alpha": alpha,
        "global_safety": global_safety,
        "global_energy": global_energy,
        "residual_safety": residual_safety,
        "residual_energy": residual_energy
    }


def score_action_with_target(
    action: str,
    state: EmotionState,
    relationship: Dict[str, float],
    global_pred: Dict[str, float],
    target_pred: Dict[str, Any],
    alpha: float,
    target: Optional[str] = None  # MVP-7.6 Phase 2: Added for self_model
) -> Tuple[float, Dict[str, float]]:
    """
    MVP-3.1: Score an action using combined global + target-specific prediction.
    
    Args:
        action: The action to score
        state: Current emotional state
        relationship: Relationship dict
        global_pred: Global prediction for this action
        target_pred: Target-specific prediction for this action
        alpha: Shrinkage factor
        target: Target identifier for self_model bias (MVP-7.6 Phase 2)
    
    Returns:
        Tuple of (score, combined_prediction_dict)
    """
    w = ACTION_SCORE_WEIGHTS
    
    # Relationship benefit
    rel_score = (
        w["bond"] * relationship.get("bond", 0.0) +
        w["grudge"] * relationship.get("grudge", 0.0) +
        w["trust"] * relationship.get("trust", 0.0)
    )
    
    # Combined prediction
    combined = compute_combined_prediction(global_pred, target_pred, alpha)
    
    # Predicted change score
    pred_score = w["safety"] * combined["safety"] + w["energy"] * combined["energy"]
    
    # Uncertainty penalty (use target-specific if available, else global)
    n = target_pred.get("n", 0)
    ema_abs_error = target_pred.get("ema_abs_error", 0.0)
    uncertainty_penalty = -w["uncertainty"] * ema_abs_error if n > 0 else 0.0
    
    total_score = rel_score + pred_score + uncertainty_penalty
    
    # MVP-7.6 Phase 2: Apply self_model action_bias
    if target:
        try:
            self_model_v0 = get_self_model_v0(target)
            self_bias = self_model_v0.get_action_bias(action)
            self_bias_weight = float(get_auto_tune_param("self_bias_weight", 0.2))
            total_score += self_bias_weight * self_bias
        except Exception:
            pass  # Self-model bias is optional enhancement
    
    return total_score, combined


async def select_action_with_target(

    state: EmotionState,
    target: str,
    target_id: str,
    test_mode: bool = False
) -> Tuple[str, Dict[str, Any]]:
    """
    MVP-3.1: Select an action using target-specific predictions.
    
    Args:
        state: Current emotional state
        target: Target identifier (for relationship lookup)
        target_id: Target ID for prediction lookup
        test_mode: If True, use argmax
    
    Returns:
        Tuple of (selected_action, all_combined_predictions)
    """
    global _predictions, _target_predictions
    
    relationship = relationship_manager.relationships.get(target, {"bond": 0.0, "grudge": 0.0, "trust": 0.0, "repair_bank": 0.0})
    
    # Load target predictions
    target_preds = await load_target_predictions_cache(target_id, test_mode)
    
    # Score all actions
    scores = {}
    combined_predictions = {}
    
    for action in ACTION_SPACE:
        global_pred = _predictions.get(action, {
            "social_safety_delta": 0.0,
            "energy_delta": 0.0
        })
        target_pred = target_preds.get(action, {
            "social_safety_delta": 0.0,
            "energy_delta": 0.0,
            "n": 0
        })
        
        n = target_pred.get("n", 0)
        alpha = calculate_shrinkage_alpha(n)
        
        score, combined = score_action_with_target(action, state, relationship, global_pred, target_pred, alpha, target)
        scores[action] = score
        combined_predictions[action] = combined
    
    if test_mode or TEST_MODE:
        best_action = max(scores.keys(), key=lambda a: scores[a])
    else:
        temp = SOFTMAX_TEMPERATURE
        max_score = max(scores.values())
        exp_scores = {a: math.exp((s - max_score) / temp) for a, s in scores.items()}
        sum_exp = sum(exp_scores.values())
        probs = {a: e / sum_exp for a, e in exp_scores.items()}
        
        import random
        r = random.random()
        cumsum = 0.0
        best_action = ACTION_SPACE[0]
        for a, p in probs.items():
            cumsum += p
            if r <= cumsum:
                best_action = a
                break
    
    return best_action, combined_predictions


async def update_predictions_with_target(
    action: str,
    target_id: str,
    predicted: Dict[str, float],
    observed: Dict[str, float],
    alpha: float,
    test_mode: bool = False
):
    """
    MVP-3.1: Update both global and target-specific predictions.
    
    Args:
        action: The action taken
        target_id: Target ID
        predicted: Combined predicted deltas {safety, energy}
        observed: Observed deltas {safety, energy}
        alpha: Shrinkage factor used for this prediction
    """
    global _predictions, _target_predictions
    
    from emotiond.config import LR_TARGET, LR_GLOBAL_RATIO, EMA_DECAY, DELTA_CLAMP_MIN, DELTA_CLAMP_MAX
    
    # Calculate errors
    safety_error = observed["safety"] - predicted["safety"]
    energy_error = observed["energy"] - predicted["energy"]
    
    # Update target residual (main learning path)
    target_preds = await load_target_predictions_cache(target_id, test_mode)
    target_pred = target_preds.get(action, {
        "social_safety_delta": 0.0,
        "energy_delta": 0.0,
        "n": 0,
        "ema_abs_error": 0.0,
        "ema_sq_error": 0.0
    })
    
    new_residual_safety = target_pred["social_safety_delta"] + LR_TARGET * safety_error
    new_residual_energy = target_pred["energy_delta"] + LR_TARGET * energy_error
    
    # Clamp residuals
    new_residual_safety = max(DELTA_CLAMP_MIN, min(DELTA_CLAMP_MAX, new_residual_safety))
    new_residual_energy = max(DELTA_CLAMP_MIN, min(DELTA_CLAMP_MAX, new_residual_energy))
    
    # Update n
    new_n = target_pred["n"] + 1
    
    # Update EMA error tracking
    new_ema_abs_error = (1 - EMA_DECAY) * target_pred["ema_abs_error"] + EMA_DECAY * (abs(safety_error) + abs(energy_error))
    new_ema_sq_error = (1 - EMA_DECAY) * target_pred["ema_sq_error"] + EMA_DECAY * (safety_error ** 2 + energy_error ** 2)
    
    # Update cache
    if target_id not in _target_predictions:
        _target_predictions[target_id] = {}
    _target_predictions[target_id][action] = {
        "social_safety_delta": new_residual_safety,
        "energy_delta": new_residual_energy,
        "n": new_n,
        "ema_abs_error": new_ema_abs_error,
        "ema_sq_error": new_ema_sq_error
    }
    
    # Persist to database
    await update_target_prediction(
        target_id, action,
        new_residual_safety, new_residual_energy,
        new_n, new_ema_abs_error, new_ema_sq_error
    )
    
    # Update global (slower learning)
    lr_global = LR_TARGET * LR_GLOBAL_RATIO
    global_pred = _predictions.get(action, {"social_safety_delta": 0.0, "energy_delta": 0.0})
    
    new_global_safety = global_pred["social_safety_delta"] + lr_global * safety_error
    new_global_energy = global_pred["energy_delta"] + lr_global * energy_error
    
    # Clamp global
    new_global_safety = max(DELTA_CLAMP_MIN, min(DELTA_CLAMP_MAX, new_global_safety))
    new_global_energy = max(DELTA_CLAMP_MIN, min(DELTA_CLAMP_MAX, new_global_energy))
    
    _predictions[action]["social_safety_delta"] = new_global_safety
    _predictions[action]["energy_delta"] = new_global_energy
    
    # Persist global
    await save_predictions(_predictions)
    
    return {
        "action": action,
        "target_id": target_id,
        "alpha": alpha,
        "errors": {"safety": safety_error, "energy": energy_error},
        "new_residual": {"safety": new_residual_safety, "energy": new_residual_energy},
        "new_global": {"safety": new_global_safety, "energy": new_global_energy},
        "n": new_n
    }


# MVP-3.1: Enhanced explanation with target-specific predictions
async def generate_explanation_v31(
    target: str,
    target_id: str,
    selected_action: Optional[str] = None,
    test_mode: bool = False
) -> Dict[str, Any]:
    """
    MVP-3.1: Generate structured explanation with target-specific predictions.
    
    Args:
        target: Target identifier (for relationship lookup)
        target_id: Target ID for prediction lookup
        selected_action: Pre-selected action (if None, will select one)
        test_mode: If True, use deterministic selection
    
    Returns:
        dict with emotion, interoception, relationships, target_id, candidates, selected, selection_reasons
    """
    global _predictions, _target_predictions
    
    state = emotion_state
    
    # Build emotion section
    emotion_values = {
        "anger": state.anger,
        "sadness": state.sadness,
        "anxiety": state.anxiety,
        "joy": state.joy,
        "loneliness": state.loneliness
    }
    sorted_emotions = sorted(emotion_values.items(), key=lambda x: x[1], reverse=True)
    top2 = [(name, value) for name, value in sorted_emotions[:2] if value > 0.0]
    emotion_section = {"top2": top2, "all": emotion_values}
    
    # Build interoception section
    interoception_section = {
        "social_safety": state.social_safety,
        "energy": state.energy
    }
    
    # Build relationships section
    relationship = relationship_manager.relationships.get(target, {"bond": 0.0, "grudge": 0.0, "trust": 0.0, "repair_bank": 0.0})
    relationships_section = {
        "bond": relationship.get("bond", 0.0),
        "grudge": relationship.get("grudge", 0.0),
        "trust": relationship.get("trust", 0.0),
        "repair_bank": relationship.get("repair_bank", 0.0)
    }
    
    # Load target predictions
    target_preds = await load_target_predictions_cache(target_id, test_mode)
    
    # Score all actions with target-specific predictions
    scores = {}
    all_combined = {}
    for action in ACTION_SPACE:
        global_pred = _predictions.get(action, {"social_safety_delta": 0.0, "energy_delta": 0.0})
        target_pred = target_preds.get(action, {"social_safety_delta": 0.0, "energy_delta": 0.0, "n": 0})
        n = target_pred.get("n", 0)
        alpha = calculate_shrinkage_alpha(n)
        score, combined = score_action_with_target(action, state, relationship, global_pred, target_pred, alpha, target)
        scores[action] = score
        all_combined[action] = combined
    
    # Get top 3 candidates
    sorted_actions = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top3 = sorted_actions[:3]
    
    # Build candidates with MVP-3.1 fields
    candidates = []
    for action, score in top3:
        combined = all_combined[action]
        reasons = _generate_action_reasons_v31(action, state, relationship, combined)
        candidates.append({
            "action": action,
            "score": score,
            "alpha": combined["alpha"],
            "predicted_global": {
                "safety": combined["global_safety"],
                "energy": combined["global_energy"]
            },
            "predicted_residual": {
                "safety": combined["residual_safety"],
                "energy": combined["residual_energy"]
            },
            "predicted_total": {
                "safety": combined["safety"],
                "energy": combined["energy"]
            },
            "reasons": reasons
        })
    
    # Select action if not provided
    if selected_action is None:
        selected_action, _ = await select_action_with_target(state, target, target_id, test_mode)

    # Persistence objective/tradeoff integration (MVP-6.2 D4)
    persistence = get_persistence_constraint()
    focus_fatigue_proxy = max(0.0, min(1.0, 0.5 * state.anxiety + 0.5 * (1.0 - state.energy)))
    persistence.update_body_state(energy=state.energy, safety_stress=1.0 - state.social_safety, focus_fatigue=focus_fatigue_proxy)
    persistence.update_relationship(target, bond=relationship.get("bond", 0.0), reliability=relationship.get("trust", 0.5), trust=relationship.get("trust", 0.5))

    ambiguity = max(0.0, min(1.0, sum(abs(all_combined[a].get("residual_safety", 0.0)) for a in ACTION_SPACE) / max(1, len(ACTION_SPACE))))
    risk = max(0.0, min(1.0, relationship.get("grudge", 0.0) * 0.7 + (1.0 - relationship.get("trust", 0.0)) * 0.3))
    expected_info_gain = max(0.0, 1.0 - ambiguity)

    p_strategy, p_reason, p_trace = persistence.select_strategy_with_tradeoff(
        target_id=target,
        risk=risk,
        ambiguity=ambiguity,
        expected_info_gain=expected_info_gain,
    )

    policy_override = None
    if not test_mode:
        if p_strategy.value == "retreat" and selected_action != "withdraw":
            policy_override = f"retreat_override:{selected_action}->withdraw"
            selected_action = "withdraw"
        elif p_strategy.value == "conservative" and selected_action == "attack":
            policy_override = "conservative_override:attack->boundary"
            selected_action = "boundary"
        elif p_strategy.value == "repair" and selected_action in ["attack", "withdraw"]:
            policy_override = f"repair_override:{selected_action}->repair_offer"
            selected_action = "repair_offer"

    # Generate selection reasons
    selection_reasons = _generate_selection_reasons_v31(selected_action, state, relationship, scores, all_combined[selected_action])

    explanation = {
        "emotion": emotion_section,
        "interoception": interoception_section,
        "relationships": relationships_section,
        "target_id": target_id,
        "candidates": candidates,
        "selected": selected_action,
        "selection_reasons": selection_reasons,
        "persistence": {
            "strategy": p_strategy.value,
            "reason": p_reason,
            "trace": p_trace.to_dict(),
            "policy_override": policy_override,
        }
    }
    
    return explanation


def _generate_action_reasons_v31(
    action: str,
    state: EmotionState,
    relationship: Dict[str, float],
    combined: Dict[str, float]
) -> List[str]:
    """MVP-3.1: Generate reasons including prediction breakdown."""
    reasons = []
    
    # Relationship-based reasons
    if relationship.get("bond", 0) > 0.5:
        reasons.append("High bond with target")
    if relationship.get("grudge", 0) > 0.5:
        reasons.append("Existing grudge")
    if relationship.get("trust", 0) < 0.3:
        reasons.append("Low trust")
    
    # State-based reasons
    if state.social_safety < 0.4:
        reasons.append("Low social safety")
    if state.energy < 0.4:
        reasons.append("Low energy")
    
    # Prediction-based reasons with breakdown
    alpha = combined.get("alpha", 0)
    total_safety = combined.get("safety", 0)
    residual_safety = combined.get("residual_safety", 0)
    
    if alpha > 0.5 and residual_safety != 0:
        reasons.append(f"Target-specific learning (α={alpha:.2f})")
    
    if total_safety > 0.02:
        reasons.append(f"Predicted to improve safety (+{total_safety:.2f})")
    elif total_safety < -0.02:
        reasons.append("Risk of safety reduction")
    
    # Action-specific reasons
    if action == "approach" and state.social_safety > 0.5:
        reasons.append("Safe to approach")
    if action == "repair_offer" and relationship.get("grudge", 0) > 0.3:
        reasons.append("Opportunity for repair")
    if action == "boundary" and relationship.get("trust", 0) < 0.4:
        reasons.append("Boundary needed for protection")
    if action == "withdraw" and state.social_safety < 0.4:
        reasons.append("Conservative choice for low safety")
    if action == "attack" and relationship.get("grudge", 0) > 0.7:
        reasons.append("Strong grudge motivates retaliation")
    
    if not reasons:
        reasons.append("Neutral expected outcome")
    
    return reasons


def _generate_selection_reasons_v31(
    selected_action: str,
    state: EmotionState,
    relationship: Dict[str, float],
    scores: Dict[str, float],
    combined: Dict[str, float]
) -> List[str]:
    """MVP-3.1: Generate selection reasons with prediction breakdown."""
    reasons = []
    
    max_score_action = max(scores.keys(), key=lambda a: scores[a])
    if selected_action == max_score_action:
        reasons.append("Highest score given current state")
    else:
        reasons.append(f"Selected via stochastic process (score: {scores[selected_action]:.3f})")
    
    alpha = combined.get("alpha", 0)
    if alpha > 0.3:
        reasons.append(f"Target-specific experience influences decision (α={alpha:.2f})")
    else:
        reasons.append("Relying primarily on general experience")
    
    if relationship.get("grudge", 0) > 0.5:
        reasons.append("High grudge influences selection")
    if relationship.get("trust", 0) < 0.3:
        reasons.append("Low trust increases caution")
    
    return reasons[:3]


async def select_action_with_explanation_v31(
    target: str,
    target_id: Optional[str] = None,
    test_mode: bool = False
) -> Dict[str, Any]:
    """
    MVP-3.1: Select action with target-specific explanation.
    
    Args:
        target: Target identifier (for relationship lookup)
        target_id: Target ID for prediction lookup (defaults to target)
        test_mode: If True, use deterministic selection
    
    Returns:
        dict with action, explanation, decision_id, target_id
    """
    from emotiond.db import save_decision
    
    if target_id is None:
        target_id = target
    
    # Ensure relationship exists
    relationship_manager._ensure_relationship_fields(target)
    
    # Generate explanation with target-specific predictions
    explanation = await generate_explanation_v31(target, target_id, test_mode=test_mode)
    selected_action = explanation["selected"]
    
    # Save decision to database
    decision_id = await save_decision(selected_action, explanation, target_id=target)
    
    # Update relationship with last action
    relationship_manager.set_last_action(target, selected_action)
    await update_relationship(
        target,
        relationship_manager.relationships[target]["bond"],
        relationship_manager.relationships[target]["grudge"],
        relationship_manager.relationships[target].get("trust", 0.0),
        relationship_manager.relationships[target].get("repair_bank", 0.0),
        selected_action
    )
    
    return {
        "action": selected_action,
        "explanation": explanation,
        "decision_id": decision_id,
        "target_id": target_id
    }

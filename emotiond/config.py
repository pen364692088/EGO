"""
Configuration for emotiond
"""
import os
import logging
import threading
from typing import Any, Mapping


def get_db_path():
    """Get database path from environment (dynamic, not cached)"""
    return os.getenv("EMOTIOND_DB_PATH", "./data/emotiond.db")


def is_core_disabled():
    """Check if core functionality is disabled (dynamic, checked at runtime)"""
    return os.getenv("EMOTIOND_DISABLE_CORE", "").strip().lower() in ["1", "true", "yes", "on"]


def is_rollouts_enabled():
    """Check if rollouts are enabled (dynamic, checked at runtime). Default: False."""
    return os.getenv("EMOTIOND_ENABLE_ROLLOUTS", "").strip().lower() in ["1", "true", "yes", "on"]


# Global auto-tune parameter storage (set by auto_tune scripts)
_lock = threading.RLock()
_auto_tune_params: dict[str, Any] = {}


def set_auto_tune_params(params: Mapping[str, Any]) -> None:
    """Replace overrides atomically for deterministic tuning."""
    with _lock:
        _auto_tune_params.clear()
        _auto_tune_params.update(dict(params))


def set_auto_tune_param(name: str, value: float) -> None:
    """Backward-compatible single-parameter setter."""
    with _lock:
        _auto_tune_params[name] = value


def get_auto_tune_param(name: str, default: Any = None) -> Any:
    """Get parameter value, checking auto-tune overrides first."""
    with _lock:
        return _auto_tune_params.get(name, default)


def get_auto_tune_params_snapshot() -> dict[str, Any]:
    """Return a copy of effective auto-tune overrides for reporting/debugging."""
    with _lock:
        return dict(_auto_tune_params)


def clear_auto_tune_params() -> None:
    """Clear all auto-tune parameter overrides."""
    with _lock:
        _auto_tune_params.clear()


# Static values for backward compatibility
DB_PATH = get_db_path()
PORT = int(os.getenv("EMOTIOND_PORT", "18080"))
HOST = os.getenv("EMOTIOND_HOST", "127.0.0.1")
K_AROUSAL = float(os.getenv("EMOTIOND_K_AROUSAL", "2.0"))
DISABLE_CORE = is_core_disabled()

# MVP-3: Time passed cumulative rate limiting
TIME_PASSED_WINDOW_SECONDS = float(os.getenv("EMOTIOND_TIME_PASSED_WINDOW_SECONDS", "10.0"))
TIME_PASSED_MAX_CUMULATIVE = float(os.getenv("EMOTIOND_TIME_PASSED_MAX_CUMULATIVE", "60.0"))

# MVP-3 B2: Action Space
ACTION_SPACE = ["approach", "repair_offer", "boundary", "withdraw", "attack"]

# MVP-3 B6: Test mode for deterministic action selection
TEST_MODE = os.getenv("EMOTIOND_TEST_MODE", "").strip().lower() in ["1", "true", "yes", "on"]

# MVP-3 B3: Initial priors for action predictions
ACTION_PRIORS = {
    "approach": {"safety": 0.03, "energy": -0.02},
    "repair_offer": {"safety": 0.05, "energy": -0.04},
    "boundary": {"safety": 0.02, "energy": -0.03},
    "withdraw": {"safety": 0.01, "energy": 0.02},
    "attack": {"safety": -0.05, "energy": -0.05},
}

# MVP-3 B5: Learning rate for prediction updates
PREDICTION_LEARNING_RATE = 0.1

# MVP-3 B4: Observation mapping - event subtype to (safety_delta, energy_delta)
OBSERVATION_MAP = {
    "care": {"safety": 0.1, "energy": 0.05},
    "apology": {"safety": 0.08, "energy": 0.02},
    "repair_success": {"safety": 0.12, "energy": 0.05},
    "rejection": {"safety": -0.15, "energy": -0.08},
    "ignored": {"safety": -0.05, "energy": -0.03},
    "betrayal": {"safety": -0.25, "energy": -0.15},
    "time_passed": {"safety": 0.0, "energy": 0.01},  # per second base rate
}

# MVP-3 B6: Action scoring weights
ACTION_SCORE_WEIGHTS = {
    "bond": 0.3,
    "grudge": -0.25,
    "trust": 0.2,
    "safety": 0.35,
    "energy": 0.25,
    "uncertainty": 0.1,
}

# MVP-3 B6: Softmax temperature for action selection
SOFTMAX_TEMPERATURE = 0.5


def setup_logging():
    """Setup logging configuration for the daemon"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('/tmp/emotiond.log')
        ]
    )


def get_observed_delta(event_subtype: str) -> dict:
    """
    MVP-3 B4: Get observed delta for an event subtype.
    
    Returns:
        dict with 'safety' and 'energy' keys, defaulting to 0.0 if subtype not found.
    """
    if event_subtype in OBSERVATION_MAP:
        return OBSERVATION_MAP[event_subtype].copy()
    return {"safety": 0.0, "energy": 0.0}

# MVP-3.1: Shrinkage factor for partial pooling
# α = n / (n + k), where k controls how quickly we trust target-specific data
SHRINKAGE_K = int(os.getenv("EMOTIOND_SHRINKAGE_K", "20"))

# MVP-3.1: Learning rates for residual vs global predictions
LR_TARGET = float(os.getenv("EMOTIOND_LR_TARGET", "0.1"))
LR_GLOBAL_RATIO = float(os.getenv("EMOTIOND_LR_GLOBAL_RATIO", "0.2"))  # lr_global = lr_target * ratio

# MVP-3.1: EMA decay for uncertainty tracking
EMA_DECAY = float(os.getenv("EMOTIOND_EMA_DECAY", "0.1"))

# MVP-3.1: Delta clamping range
DELTA_CLAMP_MAX = float(os.getenv("EMOTIOND_DELTA_CLAMP_MAX", "0.2"))
DELTA_CLAMP_MIN = float(os.getenv("EMOTIOND_DELTA_CLAMP_MIN", "-0.2"))

# MVP-4 D1: Hierarchical State System - Time Constants (in seconds of subjective time)
# Affect changes in seconds/minutes
AFFECT_DECAY_TAU = float(os.getenv("EMOTIOND_AFFECT_DECAY_TAU", "300.0"))  # 5 minutes

# Mood changes in hours
MOOD_DECAY_TAU = float(os.getenv("EMOTIOND_MOOD_DECAY_TAU", "86400.0"))  # 24 hours

# Bond/Trust changes in days/weeks
BOND_CHANGE_RATE = float(os.getenv("EMOTIOND_BOND_CHANGE_RATE", "0.001"))  # Very slow

# MVP-4 D1: Mood baseline values (where mood returns to when no events)
MOOD_BASELINE_VALENCE = 0.0
MOOD_BASELINE_AROUSAL = 0.3

# MVP-4 D1: Affect -> Mood integration rate
# How much affect influences mood (0-1)
AFFECT_TO_MOOD_RATE = float(os.getenv("EMOTIOND_AFFECT_TO_MOOD_RATE", "0.01"))

# MVP-4 D1: Uncertainty dynamics
UNCERTAINTY_DECAY = float(os.getenv("EMOTIOND_UNCERTAINTY_DECAY", "0.001"))  # Uncertainty slowly increases
UNCERTAINTY_REDUCTION_ON_OBSERVATION = float(os.getenv("EMOTIOND_UNCERTAINTY_REDUCTION_ON_OBSERVATION", "0.1"))

# MVP-5 D2: Allostasis Budget Configuration
# Energy budget recovery rate (per minute of rest)
ALLOSTASIS_RECOVERY_RATE = float(os.getenv("EMOTIOND_ALLOSTASIS_RECOVERY_RATE", "0.05"))

# Depletion rates for different stressors
ALLOSTASIS_CONFLICT_DEPLETION = float(os.getenv("EMOTIOND_ALLOSTASIS_CONFLICT_DEPLETION", "0.15"))
ALLOSTASIS_UNCERTAINTY_DEPLETION = float(os.getenv("EMOTIOND_ALLOSTASIS_UNCERTAINTY_DEPLETION", "0.08"))
ALLOSTASIS_ERROR_DEPLETION = float(os.getenv("EMOTIOND_ALLOSTASIS_ERROR_DEPLETION", "0.10"))

# Multiplier for consecutive errors
ALLOSTASIS_CONSECUTIVE_ERROR_MULTIPLIER = float(os.getenv("EMOTIOND_ALLOSTASIS_CONSECUTIVE_ERROR_MULTIPLIER", "1.5"))

# Budget thresholds
ALLOSTASIS_LOW_THRESHOLD = float(os.getenv("EMOTIOND_ALLOSTASIS_LOW_THRESHOLD", "0.3"))
ALLOSTASIS_CRITICAL_THRESHOLD = float(os.getenv("EMOTIOND_ALLOSTASIS_CRITICAL_THRESHOLD", "0.1"))


# MVP-6 D1: Virtual body state constants
BODY_STATE_ENERGY_RECOVERY = float(os.getenv("BODY_STATE_ENERGY_RECOVERY", "0.001"))
BODY_STATE_SAFETY_RECOVERY = float(os.getenv("BODY_STATE_SAFETY_RECOVERY", "0.0012"))
BODY_STATE_SOCIAL_RECOVERY = float(os.getenv("BODY_STATE_SOCIAL_RECOVERY", "0.0008"))
BODY_STATE_NOVELTY_RECOVERY = float(os.getenv("BODY_STATE_NOVELTY_RECOVERY", "0.0009"))
BODY_STATE_FOCUS_RECOVERY = float(os.getenv("BODY_STATE_FOCUS_RECOVERY", "0.0015"))

BODY_STATE_ENERGY_BASELINE = float(os.getenv("BODY_STATE_ENERGY_BASELINE", "0.7"))
BODY_STATE_SAFETY_BASELINE = float(os.getenv("BODY_STATE_SAFETY_BASELINE", "0.6"))
BODY_STATE_SOCIAL_BASELINE = float(os.getenv("BODY_STATE_SOCIAL_BASELINE", "0.5"))
BODY_STATE_NOVELTY_BASELINE = float(os.getenv("BODY_STATE_NOVELTY_BASELINE", "0.5"))
BODY_STATE_FOCUS_BASELINE = float(os.getenv("BODY_STATE_FOCUS_BASELINE", "0.3"))

# MVP-7.5: Audit trail version constants
POLICY_VERSION = os.getenv("EMOTIOND_POLICY_VERSION", "7.5.0")
SCHEMA_VERSION = os.getenv("EMOTIOND_SCHEMA_VERSION", "1.0")

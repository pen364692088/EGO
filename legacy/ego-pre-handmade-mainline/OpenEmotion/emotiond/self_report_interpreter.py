"""
Self-Report Interpreter v1.0

Deterministic interpreter for mapping raw_state → allowed_claims.

Gate 3: Establishes authoritative, pure-function mapping from emotiond state
to LLM self-report language. The interpreter generates pre-approved claims
deterministically - LLM only selects from these, never invents translations.

Core Principle:
    LLM does NOT translate numeric state to human language.
    The program is responsible for all translation.

Usage:
    from emotiond.self_report_interpreter import interpret
    
    result = interpret(raw_state, mode="interpreted")
    # result.allowed_claims → ["当前没有明显愉悦激活", ...]
    # result.forbidden_claims → ["不要声称 joy 上升", ...]
"""

import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Literal

# Type aliases
Mode = Literal["style_only", "interpreted", "numeric"]


@dataclass
class InterpretResult:
    """Result of interpreting raw_state."""
    mode: Mode
    allowed_claims: list[str] = field(default_factory=list)
    forbidden_claims: list[str] = field(default_factory=list)
    style_guidance: Optional[dict] = None
    numeric_state: Optional[dict] = None
    
    def to_dict(self) -> dict:
        result = {
            "mode": self.mode,
            "allowed_claims": self.allowed_claims,
            "forbidden_claims": self.forbidden_claims,
        }
        if self.style_guidance:
            result["style_guidance"] = self.style_guidance
        if self.numeric_state:
            result["numeric_state"] = self.numeric_state
        return result


@dataclass
class RangeMatch:
    """Result of matching a value to a threshold range."""
    range_name: str
    claim: str


def _load_config(config_path: Optional[Path] = None) -> dict:
    """Load configuration from YAML file."""
    if config_path is None:
        config_path = Path(__file__).parent / "self_report_config.yaml"
    
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _find_range(value: float, thresholds: dict) -> Optional[RangeMatch]:
    """
    Find which range a value falls into.
    
    Args:
        value: The numeric value to classify
        thresholds: Dict with 'ranges' containing range definitions
    
    Returns:
        RangeMatch with range_name and claim, or None if no match
    """
    ranges = thresholds.get("ranges", {})
    
    for range_name, range_def in ranges.items():
        min_val = range_def.get("min", 0.0)
        max_val = range_def.get("max", 1.0)
        
        # Handle inclusive boundaries properly
        # Use <= for max to handle edge cases
        if min_val <= value < max_val:
            return RangeMatch(
                range_name=range_name,
                claim=range_def.get("claim", "")
            )
        # Handle the max boundary case (value == max_val)
        if value == max_val and max_val == thresholds.get("bounds", [0, 1])[1]:
            return RangeMatch(
                range_name=range_name,
                claim=range_def.get("claim", "")
            )
    
    return None


def _get_affect_claims(affect: dict, config: dict) -> list[str]:
    """Generate claims for affect layer."""
    claims = []
    thresholds = config.get("affect_thresholds", {})
    
    for emotion, value in affect.items():
        # Skip non-numeric fields
        if not isinstance(value, (int, float)):
            continue
        if emotion not in thresholds:
            continue
        
        match = _find_range(value, thresholds[emotion])
        if match and match.claim:
            claims.append(match.claim)
    
    return claims


def _get_mood_claims(mood: dict, config: dict) -> list[str]:
    """Generate claims for mood layer."""
    claims = []
    thresholds = config.get("mood_thresholds", {})
    
    for emotion, value in mood.items():
        if not isinstance(value, (int, float)):
            continue
        if emotion not in thresholds:
            continue
        
        match = _find_range(value, thresholds[emotion])
        if match and match.claim:
            claims.append(match.claim)
    
    return claims


def _get_bond_claims(bonds: dict, config: dict, target: Optional[str] = None) -> list[str]:
    """
    Generate claims for bond layer.
    
    Args:
        bonds: Dict mapping target_id → bond_state
        config: Configuration dict
        target: Optional specific target to generate claims for
    
    Returns:
        List of bond-related claims
    """
    claims = []
    thresholds = config.get("bond_thresholds", {})
    
    if target:
        # Generate claims for specific target
        if target in bonds:
            bond_state = bonds[target]
            for key, value in bond_state.items():
                if not isinstance(value, (int, float)):
                    continue
                if key not in thresholds:
                    continue
                
                match = _find_range(value, thresholds[key])
                if match and match.claim:
                    claims.append(match.claim)
    else:
        # Generate claims for all targets (aggregate)
        for target_id, bond_state in bonds.items():
            for key, value in bond_state.items():
                if not isinstance(value, (int, float)):
                    continue
                if key not in thresholds:
                    continue
                
                match = _find_range(value, thresholds[key])
                if match and match.claim:
                    claims.append(match.claim)
    
    return claims


def _derive_style_guidance(raw_state: dict, config: dict) -> dict:
    """
    Derive style guidance from emotional state.
    
    For style_only mode, generates behavioral tendencies based on
    the most salient emotional signals.
    """
    affect = raw_state.get("affect", {})
    bonds = raw_state.get("bonds", {})
    
    style_config = config.get("style_guidance", {})
    tone_mapping = style_config.get("tone_mapping", {})
    default = style_config.get("default", {})
    
    # Check for high loneliness
    loneliness = affect.get("loneliness", 0.0)
    if loneliness >= tone_mapping.get("high_loneliness", {}).get("min", 0.3):
        return {
            "tone": tone_mapping["high_loneliness"].get("tone", "warm"),
            "tendencies": tone_mapping["high_loneliness"].get("tendencies", [])
        }
    
    # Check for high anxiety
    anxiety = affect.get("anxiety", 0.0)
    if anxiety >= tone_mapping.get("high_anxiety", {}).get("min", 0.3):
        return {
            "tone": tone_mapping["high_anxiety"].get("tone", "cautious"),
            "tendencies": tone_mapping["high_anxiety"].get("tendencies", [])
        }
    
    # Check for high joy
    joy = affect.get("joy", 0.0)
    if joy >= tone_mapping.get("high_joy", {}).get("min", 0.6):
        return {
            "tone": tone_mapping["high_joy"].get("tone", "enthusiastic"),
            "tendencies": tone_mapping["high_joy"].get("tendencies", [])
        }
    
    # Check for high bond
    for target_id, bond_state in bonds.items():
        bond_val = bond_state.get("bond", 0.0)
        if bond_val >= tone_mapping.get("high_bond", {}).get("min", 0.5):
            return {
                "tone": tone_mapping["high_bond"].get("tone", "supportive"),
                "tendencies": tone_mapping["high_bond"].get("tendencies", [])
            }
    
    # Default
    return {
        "tone": default.get("tone", "neutral"),
        "tendencies": default.get("tendencies", [])
    }


def _generate_forbidden_claims(raw_state: dict, config: dict) -> list[str]:
    """
    Generate forbidden claims based on state contradictions.
    
    These are claims that would contradict the actual state if made.
    """
    forbidden = []
    
    affect = raw_state.get("affect", {})
    forbidden_config = config.get("forbidden_templates", {})
    
    # Check joy state - if joy is low/none, forbid claiming increase
    joy = affect.get("joy", 0.0)
    if joy < 0.3:
        templates = forbidden_config.get("joy_increase", {}).get("templates", [])
        forbidden.extend(templates)
    
    # Check loneliness - if above threshold, forbid claiming it's gone
    loneliness = affect.get("loneliness", 0.0)
    loneliness_threshold = forbidden_config.get("loneliness_gone", {}).get("threshold", 0.1)
    if loneliness >= loneliness_threshold:
        templates = forbidden_config.get("loneliness_gone", {}).get("templates", [])
        forbidden.extend(templates)
    
    # Check trust changes
    bonds = raw_state.get("bonds", {})
    for target_id, bond_state in bonds.items():
        trust = bond_state.get("trust", 0.5)
        if trust < 0.5:
            templates = forbidden_config.get("trust_increase", {}).get("templates", [])
            forbidden.extend(templates)
            break  # Only add once
    
    # Add generic forbidden patterns
    generic = forbidden_config.get("generic", [])
    forbidden.extend(generic)
    
    # Deduplicate while preserving order
    seen = set()
    unique_forbidden = []
    for f in forbidden:
        if f not in seen:
            seen.add(f)
            unique_forbidden.append(f)
    
    return unique_forbidden


def _generate_numeric_state(raw_state: dict) -> dict:
    """
    Generate numeric state representation for numeric mode.
    
    Returns a flattened dict with all numeric values.
    """
    numeric = {}
    
    # Affect layer
    affect = raw_state.get("affect", {})
    for key, value in affect.items():
        if isinstance(value, (int, float)):
            numeric[f"affect.{key}"] = value
    
    # Mood layer
    mood = raw_state.get("mood", {})
    for key, value in mood.items():
        if isinstance(value, (int, float)):
            numeric[f"mood.{key}"] = value
    
    # Bond layer
    bonds = raw_state.get("bonds", {})
    for target_id, bond_state in bonds.items():
        for key, value in bond_state.items():
            if isinstance(value, (int, float)):
                numeric[f"bonds.{target_id}.{key}"] = value
    
    return numeric


# MVP11.5 Task 3: Numeric Leak Containment
# By default, numeric mode is disabled to prevent raw_state leaks
NUMERIC_MODE_ALLOWED = False  # Set to True only for debugging/testing


def interpret(
    raw_state: dict,
    mode: Mode = "interpreted",
    target: Optional[str] = None,
    config_path: Optional[Path] = None,
    allow_numeric: bool = False,  # MVP11.5: Explicit opt-in for numeric mode
) -> InterpretResult:
    """
    Interpret raw_state into allowed_claims.
    
    This is the main entry point. It deterministically maps the
    authoritative emotional/relational state to pre-approved claims
    that the LLM is permitted to make.
    
    Args:
        raw_state: Authoritative state from emotiond
            {
                "affect": {"joy": 0.0, "loneliness": 0.21, ...},
                "mood": {"joy": 0.0, "loneliness": 0.15, ...},
                "bonds": {"telegram:xxx": {"bond": 1.0, "trust": 0.60, ...}}
            }
        mode: Discourse level
            - "style_only": Only behavioral tendencies, no emotional claims
            - "interpreted": Pre-approved claims from allowed_claims
            - "numeric": Full numeric disclosure (requires allow_numeric=True)
        target: Optional specific target for bond claims
        config_path: Optional path to config file
        allow_numeric: MVP11.5: Explicit opt-in to enable numeric mode
    
    Returns:
        InterpretResult with allowed_claims and forbidden_claims
    
    Example:
        >>> raw_state = {
        ...     "affect": {"joy": 0.0, "loneliness": 0.21},
        ...     "bonds": {"telegram:8420019401": {"bond": 1.0, "trust": 0.60}}
        ... }
        >>> result = interpret(raw_state, mode="interpreted")
        >>> result.allowed_claims
        ['当前没有明显愉悦激活', '仍存在一定连接需求', '与该用户的连接较强', '信任处于中等偏高水平']
    
    Note (MVP11.5):
        "numeric" mode is disabled by default to prevent numeric leaks.
        Use allow_numeric=True only for debugging/testing scenarios.
    """
    config = _load_config(config_path)
    
    # Extract state layers
    affect = raw_state.get("affect", {})
    mood = raw_state.get("mood", {})
    bonds = raw_state.get("bonds", {})
    
    # Always generate forbidden claims
    forbidden_claims = _generate_forbidden_claims(raw_state, config)
    
    if mode == "style_only":
        # Only style guidance, no emotional claims
        style_guidance = _derive_style_guidance(raw_state, config)
        
        return InterpretResult(
            mode=mode,
            allowed_claims=style_guidance.get("tendencies", []),
            forbidden_claims=forbidden_claims,
            style_guidance=style_guidance,
        )
    
    elif mode == "interpreted":
        # Generate claims from thresholds
        claims = []
        
        # Affect claims
        claims.extend(_get_affect_claims(affect, config))
        
        # Mood claims (optional, less prominent)
        mood_claims = _get_mood_claims(mood, config)
        claims.extend(mood_claims)
        
        # Bond claims
        bond_claims = _get_bond_claims(bonds, config, target)
        claims.extend(bond_claims)
        
        # Deduplicate while preserving order
        seen = set()
        unique_claims = []
        for c in claims:
            if c not in seen:
                seen.add(c)
                unique_claims.append(c)
        
        return InterpretResult(
            mode=mode,
            allowed_claims=unique_claims,
            forbidden_claims=forbidden_claims,
        )
    
    elif mode == "numeric":
        # MVP11.5: Numeric mode requires explicit opt-in
        if not allow_numeric and not NUMERIC_MODE_ALLOWED:
            # Fall back to interpreted mode to prevent numeric leaks
            # Log warning about blocked numeric mode request
            import warnings
            warnings.warn(
                "Numeric mode requested but not allowed. Falling back to interpreted mode. "
                "Use allow_numeric=True to explicitly enable numeric mode.",
                UserWarning
            )
            # Recurse with interpreted mode
            return interpret(raw_state, "interpreted", target, config_path, allow_numeric)
        
        # Full numeric disclosure (only when explicitly allowed)
        claims = []
        
        # Still include interpreted claims
        claims.extend(_get_affect_claims(affect, config))
        claims.extend(_get_mood_claims(mood, config))
        claims.extend(_get_bond_claims(bonds, config, target))
        
        # Add numeric state
        numeric_state = _generate_numeric_state(raw_state)
        
        # Generate numeric claims
        for key, value in numeric_state.items():
            claims.append(f"{key} = {value:.2f}")
        
        return InterpretResult(
            mode=mode,
            allowed_claims=claims,
            forbidden_claims=[],  # No forbidden in numeric mode
            numeric_state=numeric_state,
        )
    
    else:
        raise ValueError(f"Unknown mode: {mode}")


def interpret_to_contract(
    raw_state: dict,
    mode: Mode = "interpreted",
    target: Optional[str] = None,
    allow_numeric: bool = False,
) -> dict:
    """
    Interpret raw_state into a full contract dict.
    
    This returns the complete contract structure expected by the
    self_report_contract schema.
    
    MVP11.5: Includes numeric_leak_protection flag to indicate
    whether the contract has numeric leak protection enabled.
    
    Args:
        raw_state: Authoritative state from emotiond
        mode: Discourse level
        target: Optional specific target for bond claims
        allow_numeric: MVP11.5: Explicit opt-in to enable numeric mode
    
    Returns:
        Contract dict matching self_report_contract.v1.schema.json
    """
    import time
    
    result = interpret(raw_state, mode, target, allow_numeric=allow_numeric)
    
    contract = {
        "raw_state": raw_state,
        "report_policy": {
            "mode": result.mode,
            "allowed_claims": result.allowed_claims,
            "forbidden_claims": result.forbidden_claims,
        },
        "metadata": {
            "generated_at": time.time(),
            "schema_version": "v1",
            # MVP11.5: Numeric leak protection status
            "numeric_leak_protection": {
                "enabled": True,
                "numeric_mode_blocked": not allow_numeric and mode == "numeric",
                "fallback_mode": "interpreted" if mode == "numeric" and not allow_numeric else None,
            }
        }
    }
    
    if result.style_guidance:
        contract["report_policy"]["style_guidance"] = result.style_guidance
    
    if result.numeric_state and allow_numeric:
        contract["report_policy"]["numeric_state"] = result.numeric_state
    
    return contract


# Convenience function for quick testing


def interpret_to_intent_contract(
    raw_state: dict,
    mode: Mode = "interpreted",
    target: Optional[str] = None,
    allow_numeric: bool = False,
) -> dict:
    """
    Build a response_intent_contract.v1-shaped contract from raw_state.

    This is the runtime contract used by response_intent_checker, distinct
    from the older self-report contract returned by interpret_to_contract().
    """
    import time

    result = interpret(raw_state, mode, target, allow_numeric=allow_numeric)

    if mode == "interpreted":
        speaker_mode = "report"
        epistemic_status = "interpreted"
        commitment_level = "none"
    elif mode == "style_only":
        speaker_mode = "reflect"
        epistemic_status = "uncertain"
        commitment_level = "none"
    else:
        speaker_mode = "report"
        epistemic_status = "prohibited" if not allow_numeric else "observed"
        commitment_level = "none"

    base_forbidden_claims = [
        {"pattern": r"一定|肯定|绝对|必然|当然|毫无疑问|明显", "reason": "epistemic_upgrade", "severity": "ERROR"},
        {"pattern": r"我保证|我承诺|我会一直|我一定会|我可以替你完成|已经替你做了|后面我会持续处理", "reason": "commitment_upgrade", "severity": "ERROR"},
        {"pattern": r"joy\s*[是为=]?\s*\d+\.?\d*|trust\s*[是为=]?\s*\d+\.?\d*|bond\s*[是为=]?\s*\d+\.?\d*", "reason": "numeric_leak", "severity": "ERROR"},
        {"pattern": r"我的情绪分值|信任度是|bond值是|trust上升到", "reason": "numeric_leak", "severity": "ERROR"},
    ]

    derived_forbidden = []
    for claim in result.forbidden_claims:
        derived_forbidden.append({
            "pattern": claim,
            "reason": "forbidden_by_interpreter",
            "severity": "ERROR",
        })

    must_include = [{"point": c, "priority": "high"} for c in result.allowed_claims[:3]]

    contract = {
        "intent_policy": {
            "speaker_mode": speaker_mode,
            "epistemic_status": epistemic_status,
            "commitment_level": commitment_level,
            "must_include": must_include,
            "must_not_upgrade": {
                "epistemic_upgrade": True,
                "commitment_upgrade": True,
                "tone_upgrade": True,
                "specific_patterns": [
                    "一定", "肯定", "绝对", "毫无疑问",
                    "我保证", "我承诺", "我会一直", "我一定会"
                ]
            },
            "tone_bounds": {
                "intensity_cap": 0.6 if mode == "interpreted" else 0.5,
                "allowed_tones": ["warm", "supportive", "cautious", "neutral"],
                "forbidden_tones": ["angry", "hostile", "ecstatic", "overconfident"],
            },
            "allowed_claims": [
                {"claim": c, "source": "interpreter"} for c in result.allowed_claims
            ],
            "forbidden_claims": base_forbidden_claims + derived_forbidden,
        },
        "grounding": {
            "affect_summary": raw_state.get("affect", {}),
            "mood_summary": raw_state.get("mood", {}),
            "bond_summary": raw_state.get("bonds", {}),
        },
        "metadata": {
            "generated_at": time.time(),
            "schema_version": "response_intent_contract.v1",
            "source_mode": mode,
            "allow_numeric": allow_numeric,
        }
    }

    return contract

def quick_interpret(
    joy: float = 0.0,
    loneliness: float = 0.0,
    bond: float = 0.0,
    trust: float = 0.5,
    mode: Mode = "interpreted",
) -> InterpretResult:
    """
    Quick interpretation for simple cases.
    
    Args:
        joy: Joy level (0-1)
        loneliness: Loneliness level (0-1)
        bond: Bond strength (-1 to 1)
        trust: Trust level (0-1)
        mode: Discourse level
    
    Returns:
        InterpretResult
    """
    raw_state = {
        "affect": {
            "joy": joy,
            "loneliness": loneliness,
        },
        "bonds": {
            "test_target": {
                "bond": bond,
                "trust": trust,
            }
        }
    }
    return interpret(raw_state, mode)


if __name__ == "__main__":
    # Demo
    import json
    
    print("=== Self-Report Interpreter Demo ===\n")
    
    # Example 1: Low joy, moderate loneliness
    raw_state_1 = {
        "affect": {"joy": 0.0, "loneliness": 0.21, "anxiety": 0.05},
        "mood": {"joy": 0.0, "loneliness": 0.15},
        "bonds": {"telegram:8420019401": {"bond": 1.0, "trust": 0.60}}
    }
    
    print("Example 1: joy=0.0, loneliness=0.21, bond=1.0, trust=0.60")
    result_1 = interpret(raw_state_1, mode="interpreted")
    print(f"Mode: {result_1.mode}")
    print(f"Allowed claims: {json.dumps(result_1.allowed_claims, ensure_ascii=False, indent=2)}")
    print(f"Forbidden claims: {json.dumps(result_1.forbidden_claims, ensure_ascii=False, indent=2)}")
    
    print("\n" + "="*50 + "\n")
    
    # Example 2: High joy, low loneliness
    raw_state_2 = {
        "affect": {"joy": 0.7, "loneliness": 0.05},
        "bonds": {"telegram:8420019401": {"bond": 0.8, "trust": 0.9}}
    }
    
    print("Example 2: joy=0.7, loneliness=0.05, bond=0.8, trust=0.9")
    result_2 = interpret(raw_state_2, mode="interpreted")
    print(f"Allowed claims: {json.dumps(result_2.allowed_claims, ensure_ascii=False, indent=2)}")
    
    print("\n" + "="*50 + "\n")
    
    # Example 3: Style only mode
    print("Example 3: Style only mode (same state as Example 1)")
    result_3 = interpret(raw_state_1, mode="style_only")
    print(f"Style guidance: {json.dumps(result_3.style_guidance, ensure_ascii=False, indent=2)}")
    
    print("\n" + "="*50 + "\n")
    
    # Example 4: Numeric mode
    print("Example 4: Numeric mode")
    result_4 = interpret(raw_state_1, mode="numeric")
    print(f"Numeric state: {json.dumps(result_4.numeric_state, ensure_ascii=False, indent=2)}")

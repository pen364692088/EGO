"""
Security module for MVP-2.1.1: Source resolution + meta sanitization

Provides:
- Server-side source resolution from auth tokens
- Meta key validation and sanitization
- Time_passed clamping for user sources
- Secure token loading with auto-generation
"""
import os
import secrets
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple


# Environment variable names for tokens
SYSTEM_TOKEN_ENV = "EMOTIOND_SYSTEM_TOKEN"
OPENCLAW_TOKEN_ENV = "EMOTIOND_OPENCLAW_TOKEN"
GENERAL_TOKEN_ENV = "EMOTIOND_TOKEN"  # New: general token env var

# Token file paths (in priority order)
TOKEN_FILE_PATHS = [
    Path.home() / ".config" / "openemotion" / "emotiond_token",
    Path.home() / ".openemotion" / "emotiond_token",
]

# User-allowed subtypes for world_event
USER_ALLOWED_SUBTYPES = {"care", "rejection", "ignored", "apology", "time_passed"}

# User-allowed meta keys for world_event WITH subtype (source is server-controlled)
USER_ALLOWED_META_KEYS = {"subtype", "seconds", "client_source", "request_id", "test", "severity"}

# Time_passed clamp bounds for user sources
TIME_PASSED_MIN_SECONDS = 1
TIME_PASSED_MAX_SECONDS = 300

# Logger for token operations
logger = logging.getLogger("emotiond.security")


def load_token_from_file(path: Path) -> Optional[str]:
    """Load token from a file if it exists and is secure."""
    if not path.exists():
        return None
    
    # Check file permissions (should be 600 or 400)
    try:
        stat_info = path.stat()
        mode = stat_info.st_mode & 0o777
        if mode not in (0o600, 0o400):
            logger.warning(
                f"Token file {path} has insecure permissions {oct(mode)}, "
                f"expected 600 or 400"
            )
    except OSError as e:
        logger.debug(f"Could not check permissions for {path}: {e}")
    
    try:
        return path.read_text().strip()
    except OSError as e:
        logger.warning(f"Could not read token file {path}: {e}")
        return None


def generate_and_save_token(path: Path) -> str:
    """Generate a random token and save it to the given path."""
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Generate 32 bytes of random data (64 hex chars)
    token = secrets.token_hex(32)
    
    # Write with secure permissions (created with 0600)
    path.write_text(token)
    
    # Set explicit permissions
    try:
        path.chmod(0o600)
    except OSError as e:
        logger.warning(f"Could not set permissions on {path}: {e}")
    
    logger.info(f"Generated new token and saved to {path}")
    return token


def get_or_create_token(env_var: str = GENERAL_TOKEN_ENV) -> Optional[str]:
    """
    Get or create a token with the following priority:
    
    1. Environment variable: EMOTIOND_TOKEN (or specified env_var)
    2. User directory: ~/.config/openemotion/emotiond_token
    3. User directory: ~/.openemotion/emotiond_token
    4. If none exists: generate random token, write to user directory (mode 600)
    
    Args:
        env_var: Environment variable name to check (default: EMOTIOND_TOKEN)
    
    Returns:
        Token string, or None if generation fails
    """
    # Priority 1: Check environment variable
    token = os.environ.get(env_var)
    if token:
        logger.debug(f"Token loaded from environment variable {env_var}")
        return token
    
    # Priority 2 & 3: Check user directory files
    for path in TOKEN_FILE_PATHS:
        token = load_token_from_file(path)
        if token:
            logger.debug(f"Token loaded from {path}")
            return token
    
    # Priority 4: Generate and save new token
    # Use the first preferred path
    preferred_path = TOKEN_FILE_PATHS[0]
    try:
        token = generate_and_save_token(preferred_path)
        logger.info(f"Auto-generated token saved to {preferred_path}")
        return token
    except OSError as e:
        logger.error(f"Failed to generate token at {preferred_path}: {e}")
        
        # Try fallback path
        fallback_path = TOKEN_FILE_PATHS[1]
        try:
            token = generate_and_save_token(fallback_path)
            logger.info(f"Auto-generated token saved to {fallback_path}")
            return token
        except OSError as e2:
            logger.error(f"Failed to generate token at {fallback_path}: {e2}")
            return None


def get_token_file_location() -> Optional[Path]:
    """
    Get the path where the token file is stored or would be stored.
    
    Returns the first existing token file path, or the preferred path if none exists.
    """
    for path in TOKEN_FILE_PATHS:
        if path.exists():
            return path
    return TOKEN_FILE_PATHS[0]


def get_system_token() -> Optional[str]:
    """Get the system token from environment (legacy, kept for compatibility)."""
    return os.environ.get(SYSTEM_TOKEN_ENV)


def get_openclaw_token() -> Optional[str]:
    """
    Get the openclaw token.
    
    Priority: EMOTIOND_OPENCLAW_TOKEN env var, then auto-generated token.
    """
    # First check dedicated env var
    token = os.environ.get(OPENCLAW_TOKEN_ENV)
    if token:
        return token
    
    # Fall back to general token mechanism
    return get_or_create_token(OPENCLAW_TOKEN_ENV)


def init_tokens() -> Dict[str, Optional[str]]:
    """
    Initialize all tokens at startup.
    
    This should be called once when emotiond starts to ensure tokens are available.
    
    Returns:
        Dict with token names and their values (or None if unavailable)
    """
    tokens = {
        "system": get_system_token(),
        "openclaw": get_openclaw_token(),
        "general": get_or_create_token(),
    }
    
    # Log token status (without revealing values)
    for name, value in tokens.items():
        if value:
            logger.info(f"Token '{name}' loaded successfully")
        else:
            logger.warning(f"Token '{name}' not available")
    
    return tokens


def resolve_server_source(authorization_header: Optional[str], x_token_header: Optional[str]) -> str:
    """
    Resolve the server-determined source from auth headers.
    
    Priority:
    1. Authorization: Bearer <token>
    2. X-Emotiond-Token: <token>
    
    Returns:
        "system" if token matches system token
        "openclaw" if token matches openclaw token
        "user" otherwise (default)
    """
    token = None
    
    # Try Authorization header first
    if authorization_header:
        if authorization_header.lower().startswith("bearer "):
            token = authorization_header[7:].strip()
        else:
            token = authorization_header.strip()
    
    # Fall back to X-Emotiond-Token
    if not token and x_token_header:
        token = x_token_header.strip()
    
    if not token:
        return "user"
    
    # Check against configured tokens
    system_token = get_system_token()
    openclaw_token = get_openclaw_token()
    
    if system_token and token == system_token:
        return "system"
    
    if openclaw_token and token == openclaw_token:
        return "openclaw"
    
    return "user"


def sanitize_meta_for_user(
    meta: Optional[Dict[str, Any]], 
    event_type: str
) -> Tuple[Dict[str, Any], Optional[str], Optional[Dict[str, Any]]]:
    """
    Sanitize meta dict for user source.
    
    Args:
        meta: The meta dict from the event
        event_type: The event type (e.g., "world_event")
    
    Returns:
        Tuple of (sanitized_meta, deny_reason, audit_info)
        - sanitized_meta: cleaned meta dict
        - deny_reason: None if allowed, error string if denied
        - audit_info: additional info for audit log
    """
    if meta is None:
        meta = {}
    
    if event_type != "world_event":
        # Non-world_event types: pass through
        result = dict(meta)
        return result, None, None
    
    # For world_event, check subtype
    subtype = meta.get("subtype")
    
    # If no subtype, allow all meta keys (backward compatibility with generic world_events)
    # These are informational events without emotional dynamics
    if not subtype:
        result = dict(meta)
        return result, None, None
    
    # Check if subtype is allowed for users (restricted subtypes)
    if subtype in {"betrayal", "repair_success"}:
        return (
            meta,
            f"user source not allowed for {subtype}",
            {
                "denied_subtype": subtype,
                "allowed_subtypes": sorted(USER_ALLOWED_SUBTYPES),
                "reason": "high_impact_event_requires_elevated_source"
            }
        )
    
    # For other subtypes (care, rejection, ignored, apology, time_passed),
    # validate meta keys to prevent injection
    # Note: 'source' is added by API layer (server-controlled), so exclude it from check
    allowed_keys = USER_ALLOWED_META_KEYS
    meta_keys_to_check = set(meta.keys()) - {"source"}  # source is server-controlled
    unknown_keys = meta_keys_to_check - allowed_keys
    if unknown_keys:
        return (
            meta,
            f"unknown meta keys for user source with subtype: {sorted(unknown_keys)}",
            {
                "denied_keys": sorted(unknown_keys),
                "allowed_keys": sorted(allowed_keys),
                "reason": "unauthorized_meta_keys"
            }
        )
    
    # Validate time_passed seconds
    result = dict(meta)
    audit_info = None
    
    if subtype == "time_passed":
        seconds = meta.get("seconds", 60)
        
        # Validate minimum
        if seconds < TIME_PASSED_MIN_SECONDS:
            return (
                meta,
                f"time_passed seconds must be >= {TIME_PASSED_MIN_SECONDS}, got {seconds}",
                {
                    "denied_seconds": seconds,
                    "min_allowed": TIME_PASSED_MIN_SECONDS,
                    "reason": "invalid_time_passed_value"
                }
            )
        
        # Clamp maximum
        if seconds > TIME_PASSED_MAX_SECONDS:
            result["seconds"] = TIME_PASSED_MAX_SECONDS
            result["clamped_from"] = seconds
            audit_info = {
                "original_seconds": seconds,
                "clamped_to": TIME_PASSED_MAX_SECONDS,
                "reason": "time_passed_clamped"
            }
    
    return result, None, audit_info


def validate_time_passed_cumulative(
    seconds: float,
    current_window_sum: float,
    max_cumulative: float = 60.0
) -> Tuple[float, Dict[str, Any]]:
    """
    Validate time_passed against cumulative rate limit.
    
    Args:
        seconds: Requested seconds
        current_window_sum: Current sum of seconds in the window
        max_cumulative: Maximum allowed cumulative seconds (default 60)
    
    Returns:
        Tuple of (clamped_seconds, audit_info)
        - clamped_seconds: Allowed seconds (may be clamped)
        - audit_info: Details about clamping decision
    """
    remaining_budget = max_cumulative - current_window_sum
    
    if remaining_budget <= 0:
        # Budget exhausted, reject entirely
        return 0.0, {
            "window_sum": current_window_sum,
            "requested": seconds,
            "clamped_to": 0.0,
            "reason": "cumulative_budget_exhausted"
        }
    
    if seconds <= remaining_budget:
        # Within budget, allow fully
        return seconds, {
            "window_sum": current_window_sum,
            "requested": seconds,
            "clamped_to": seconds,
            "reason": "within_budget"
        }
    
    # Partial budget available, clamp to remaining
    return remaining_budget, {
        "window_sum": current_window_sum,
        "requested": seconds,
        "clamped_to": remaining_budget,
        "reason": "clamped_to_remaining_budget"
    }


def validate_event_for_source(
    event_type: str,
    meta: Optional[Dict[str, Any]],
    server_source: str
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Validate an event for a given server source.
    
    Args:
        event_type: The event type
        meta: The meta dict
        server_source: Server-resolved source ("system", "openclaw", "user")
    
    Returns:
        Tuple of (allowed, deny_reason, sanitized_meta)
        - allowed: True if event should be processed
        - deny_reason: None if allowed, error string if denied
        - sanitized_meta: sanitized meta (with clamping if applicable)
    """
    if meta is None:
        meta = {}
    
    # System and openclaw sources: no restrictions
    if server_source in {"system", "openclaw"}:
        return True, None, dict(meta)
    
    # User source: apply sanitization
    sanitized, deny_reason, audit_info = sanitize_meta_for_user(meta, event_type)
    
    if deny_reason:
        return False, deny_reason, meta  # Return original meta for audit
    
    return True, None, sanitized

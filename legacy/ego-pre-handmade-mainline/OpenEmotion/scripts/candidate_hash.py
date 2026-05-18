"""
Candidate Parameter Hashing (US-644)

Provides consistent hashing for candidate parameters to enable
traceability and debugging of parameter evolution.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Optional


def _resolve_git_worktree_cwd() -> Optional[Path]:
    """Return a repo-local cwd suitable for git commands."""
    script_path = Path(__file__).resolve()
    for parent in script_path.parents:
        if (parent / ".git").exists():
            return parent
    return script_path.parent.parent if script_path.parent.parent.exists() else None


def _get_code_version() -> str:
    """Return short git SHA when available, otherwise 'unknown'."""
    git_cwd = _resolve_git_worktree_cwd()
    if git_cwd is None:
        return "unknown"

    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(git_cwd),
            stderr=subprocess.DEVNULL,
        ).decode("utf-8").strip()[:12]
    except (subprocess.CalledProcessError, FileNotFoundError, NotADirectoryError, OSError):
        return "unknown"


def compute_candidate_param_hash(params: Dict[str, Any]) -> str:
    """
    Compute a deterministic hash for candidate parameters.

    Args:
        params: Dictionary of parameter names to values

    Returns:
        SHA-256 hex digest
    """
    # Filter to only hashable parameter types
    hashable = {}
    for k, v in sorted(params.items()):
        if isinstance(v, (str, int, float, bool, type(None))):
            hashable[k] = v
        elif isinstance(v, (list, dict)):
            try:
                # Serialize complex types
                hashable[k] = json.dumps(v, sort_keys=True, ensure_ascii=False)
            except (TypeError, ValueError):
                pass  # Skip unserializable values

    canonical = json.dumps(hashable, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_threshold_config_hash(config: Dict[str, Any]) -> str:
    """
    Compute hash for threshold configuration.

    Args:
        config: Threshold configuration dictionary

    Returns:
        SHA-256 hex digest
    """
    # Extract version and thresholds
    relevant = {
        "version": config.get("version", "unknown"),
        "thresholds": config.get("thresholds", {}),
    }
    canonical = json.dumps(relevant, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_report_hashes(
    report: Dict[str, Any],
    expected_threshold_hash: Optional[str] = None,
    expected_candidate_hash: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Validate that a report contains required hashes.

    Args:
        report: Evaluation report dictionary
        expected_threshold_hash: Expected threshold config hash
        expected_candidate_hash: Expected candidate param hash (for AutoTune reports)

    Returns:
        Validation result with 'valid' and 'issues' keys
    """
    issues = []

    # Check threshold config hash
    threshold_config = report.get("aggregate_metrics", {}).get("threshold_config", {})
    threshold_hash = threshold_config.get("hash")

    if not threshold_hash:
        issues.append("missing_threshold_config_hash")
    elif expected_threshold_hash and threshold_hash != expected_threshold_hash:
        issues.append(f"threshold_hash_mismatch: expected {expected_threshold_hash[:8]}..., got {threshold_hash[:8]}...")

    # Check candidate param hash (for AutoTune reports)
    if expected_candidate_hash is not None:
        candidate_hash = report.get("candidate_param_hash")
        if not candidate_hash:
            issues.append("missing_candidate_param_hash")
        elif candidate_hash != expected_candidate_hash:
            issues.append(f"candidate_hash_mismatch: expected {expected_candidate_hash[:8]}..., got {candidate_hash[:8]}...")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
    }


def annotate_report_with_hashes(
    report: Dict[str, Any],
    threshold_config: Dict[str, Any],
    candidate_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Add hash annotations to a report.

    Args:
        report: Report dictionary to annotate
        threshold_config: Threshold configuration
        candidate_params: Optional candidate parameters (for AutoTune)

    Returns:
        Annotated report
    """
    if "aggregate_metrics" not in report:
        report["aggregate_metrics"] = {}

    # Add threshold config hash
    threshold_hash = compute_threshold_config_hash(threshold_config)
    report["aggregate_metrics"]["threshold_config"] = {
        "version": threshold_config.get("version", "unknown"),
        "hash": threshold_hash,
    }

    # Add candidate param hash if provided
    if candidate_params:
        report["candidate_param_hash"] = compute_candidate_param_hash(candidate_params)

    # Add code version
    report["code_version"] = _get_code_version()

    return report

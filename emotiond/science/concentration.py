"""Concentration metrics for cycle signature analysis.

Computes concentration indicators for φ signatures within a rolling window.

Metrics:
- phi_top1_share: Top-1 φ signature share in window
- phi_top3_share: Top-3 φ signatures combined share
- phi_hhi: Herfindahl-Hirschman Index (concentration)
- unique_phi_per_1000: Unique φ count per 1000 ticks

Determinism guarantees:
- Same input produces identical output
- Tie-breaking is deterministic (alphabetical by signature)
- Supports rolling_window=50/100
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any, Dict, List, Optional

from .cycle import build_cycle_bucket, signature_phi


def _extract_phi_signature(event: Dict[str, Any]) -> str:
    """Extract phi signature from event, computing if necessary."""
    # Prefer pre-computed signature
    sig = event.get("cycle_signature_phi")
    if sig:
        return str(sig)
    
    # Fall back to computing from cycle_bucket
    bucket = event.get("cycle_bucket")
    if bucket:
        return signature_phi(bucket)
    
    # Build bucket from event
    bucket = build_cycle_bucket(event)
    return signature_phi(bucket)


def _deterministic_top_k(counter: Counter, k: int) -> List[str]:
    """Get top-k items from counter with deterministic tie-breaking.
    
    Tie-breaking: alphabetical order by signature.
    """
    if not counter:
        return []
    
    # Sort by (-count, signature) for deterministic ordering
    # Negative count for descending, signature for alphabetical tie-break
    sorted_items = sorted(counter.items(), key=lambda x: (-x[1], x[0]))
    return [item[0] for item in sorted_items[:k]]


def compute_concentration(
    events: List[Dict[str, Any]],
    *,
    rolling_window: int = 100,
) -> Dict[str, Any]:
    """Compute concentration metrics for φ signatures.
    
    Args:
        events: List of events containing cycle_signature_phi or cycle_bucket
        rolling_window: Window size for rolling metrics (50 or 100)
    
    Returns:
        Dict with concentration metrics:
        - phi_top1_share: Top-1 signature share
        - phi_top3_share: Top-3 signatures combined share
        - phi_hhi: Herfindahl-Hirschman Index
        - unique_phi_per_1000: Unique signatures per 1000 ticks
        - window_size: The window size used
    """
    n = len(events)
    if n == 0:
        return {
            "phi_top1_share": 0.0,
            "phi_top3_share": 0.0,
            "phi_hhi": 0.0,
            "unique_phi_per_1000": 0.0,
            "window_size": rolling_window,
        }
    
    # Extract phi signatures
    signatures: List[str] = []
    for event in events:
        signatures.append(_extract_phi_signature(event))
    
    # Use the last rolling_window events (or all if fewer)
    window_size = min(rolling_window, n)
    window_signatures = signatures[-window_size:]
    
    # Count signatures in window
    counter = Counter(window_signatures)
    total = len(window_signatures)
    
    if total == 0:
        return {
            "phi_top1_share": 0.0,
            "phi_top3_share": 0.0,
            "phi_hhi": 0.0,
            "unique_phi_per_1000": 0.0,
            "window_size": rolling_window,
        }
    
    # Compute top-k shares with deterministic tie-breaking
    top_k_sigs = _deterministic_top_k(counter, 3)
    
    # phi_top1_share
    if top_k_sigs:
        top1_count = counter[top_k_sigs[0]]
        phi_top1_share = round(top1_count / total, 6)
    else:
        phi_top1_share = 0.0
    
    # phi_top3_share
    if len(top_k_sigs) >= 3:
        top3_count = sum(counter[sig] for sig in top_k_sigs[:3])
        phi_top3_share = round(top3_count / total, 6)
    elif top_k_sigs:
        top3_count = sum(counter[sig] for sig in top_k_sigs)
        phi_top3_share = round(top3_count / total, 6)
    else:
        phi_top3_share = 0.0
    
    # phi_hhi: Herfindahl-Hirschman Index
    # HHI = sum of squared market shares (proportions)
    # For concentration: higher HHI = more concentrated
    hhi = 0.0
    for count in counter.values():
        share = count / total
        hhi += share * share
    phi_hhi = round(hhi, 6)
    
    # unique_phi_per_1000: unique signatures per 1000 ticks
    # Scale by total events, capped at window
    unique_count = len(counter)
    if total > 0:
        unique_phi_per_1000 = round(unique_count * 1000.0 / total, 6)
    else:
        unique_phi_per_1000 = 0.0
    
    return {
        "phi_top1_share": phi_top1_share,
        "phi_top3_share": phi_top3_share,
        "phi_hhi": phi_hhi,
        "unique_phi_per_1000": unique_phi_per_1000,
        "window_size": rolling_window,
    }


def compute_concentration_from_run(
    run_path: str,
    *,
    rolling_window: int = 100,
) -> Dict[str, Any]:
    """Load run.jsonl and compute concentration metrics.
    
    Args:
        run_path: Path to run.jsonl file
        rolling_window: Window size (50 or 100)
    
    Returns:
        Concentration metrics dict
    """
    from pathlib import Path
    path = Path(run_path)
    
    events: List[Dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    
    return compute_concentration(events, rolling_window=rolling_window)


def render_concentration_markdown(metrics: Dict[str, Any]) -> str:
    """Render concentration metrics as markdown."""
    lines = [
        "# Concentration Report",
        "",
        "## φ Signature Concentration Metrics",
        "",
        f"- **phi_top1_share**: `{metrics.get('phi_top1_share', 0.0):.6f}`",
        f"- **phi_top3_share**: `{metrics.get('phi_top3_share', 0.0):.6f}`",
        f"- **phi_hhi**: `{metrics.get('phi_hhi', 0.0):.6f}`",
        f"- **unique_phi_per_1000**: `{metrics.get('unique_phi_per_1000', 0.0):.6f}`",
        f"- **window_size**: `{metrics.get('window_size', 100)}`",
        "",
        "## Interpretation",
        "",
        "- **phi_top1_share**: Proportion of events with the most common φ signature",
        "- **phi_top3_share**: Combined proportion of top-3 most common φ signatures",
        "- **phi_hhi**: Herfindahl-Hirschman Index; higher = more concentrated",
        "- **unique_phi_per_1000**: Diversity measure; higher = more unique states",
        "",
    ]
    return "\n".join(lines)

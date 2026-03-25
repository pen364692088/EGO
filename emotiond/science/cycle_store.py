"""Cycle consolidation store (MVP11.3 C2).

Stores compressed structural invariants only (no raw text trajectories).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_MAX_ENTRIES = 10_000


@dataclass
class ConsolidatedCycle:
    signature: str
    prototype_bucket: Dict[str, Any]
    stats: Dict[str, Any]
    provenance: Dict[str, Any]
    plan_template_hash: Optional[str] = None


def _hash_json(payload: Any) -> str:
    txt = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(txt.encode("utf-8")).hexdigest()


def _normalize_plan_template_hash(value: Any) -> Optional[str]:
    if value in (None, "", {}):
        return None
    if isinstance(value, str):
        return value
    return _hash_json(value)


def _parse_consolidated_cycle(item: Dict[str, Any]) -> ConsolidatedCycle:
    return ConsolidatedCycle(
        signature=str(item.get("signature", "")),
        prototype_bucket=item.get("prototype_bucket") or {},
        stats=item.get("stats") or {},
        provenance=item.get("provenance") or {},
        plan_template_hash=item.get("plan_template_hash"),
    )


def _confidence_score(c: ConsolidatedCycle) -> float:
    stats = c.stats or {}
    counts = float(stats.get("counts", 0.0) or 0.0)
    oi = float(stats.get("order_invariance_score", 0.0) or 0.0)
    support = float(stats.get("support_ratio", 0.0) or 0.0)
    return counts * (0.6 + 0.4 * oi) + support


def _merge_stats(old: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    old_counts = float(old.get("counts", 0.0) or 0.0)
    new_counts = float(new.get("counts", 0.0) or 0.0)
    total = max(1.0, old_counts + new_counts)

    merged = {
        "counts": int(old_counts + new_counts),
        "support_ratio": round(float(new.get("support_ratio", old.get("support_ratio", 0.0))), 6),
        "cycle_member": bool(new.get("cycle_member", old.get("cycle_member", False))),
        "cycle_persistence_score": round(float(new.get("cycle_persistence_score", old.get("cycle_persistence_score", 0.0))), 6),
    }

    for key in ("return_time_mean", "return_time_p50", "order_invariance_score"):
        ov = float(old.get(key, 0.0) or 0.0)
        nv = float(new.get(key, 0.0) or 0.0)
        merged[key] = round((ov * old_counts + nv * new_counts) / total, 6)

    return merged


def build_consolidated_cycles(
    *,
    run_id: str,
    candidates: List[Dict[str, Any]],
    seed: Optional[int] = None,
    scenario_id: Optional[str] = None,
    policy_version: Optional[str] = None,
    schema_version: str = "mvp11.3.v1",
) -> List[ConsolidatedCycle]:
    out: List[ConsolidatedCycle] = []

    for c in candidates:
        stats = {
            "counts": int(c.get("counts", 0)),
            "support_ratio": float(c.get("support_ratio", 0.0)),
            "return_time_mean": float(c.get("return_time_mean", 0.0)),
            "return_time_p50": float(c.get("return_time_p50", 0.0)),
            "order_invariance_score": float(c.get("order_invariance_score", 0.0)),
            "cycle_member": bool(c.get("cycle_member", False)),
            "cycle_persistence_score": float(c.get("cycle_persistence_score", 0.0)),
        }
        provenance = {
            "run_id": run_id,
            "scenario_id": scenario_id or "global",
            "seed": seed,
            "policy_version": policy_version,
            "schema_version": schema_version,
            "ts": time.time(),
        }

        out.append(
            ConsolidatedCycle(
                signature=str(c.get("signature", "")),
                prototype_bucket=c.get("prototype_bucket") or {},
                stats=stats,
                provenance=provenance,
                plan_template_hash=_normalize_plan_template_hash(c.get("plan_template_hash")),
            )
        )

    return out


def _dedupe_and_cap(cycles: List[ConsolidatedCycle], *, max_entries: int) -> tuple[List[ConsolidatedCycle], int]:
    by_sig: Dict[str, ConsolidatedCycle] = {}

    for c in cycles:
        sig = c.signature
        if not sig:
            continue

        if sig not in by_sig:
            by_sig[sig] = c
            continue

        prev = by_sig[sig]
        # Merge rolling stats, keep latest provenance and bucket.
        by_sig[sig] = ConsolidatedCycle(
            signature=sig,
            prototype_bucket=c.prototype_bucket or prev.prototype_bucket,
            stats=_merge_stats(prev.stats or {}, c.stats or {}),
            provenance=c.provenance or prev.provenance,
            plan_template_hash=c.plan_template_hash or prev.plan_template_hash,
        )

    deduped = list(by_sig.values())
    deduped.sort(
        key=lambda x: (
            -_confidence_score(x),
            -float((x.provenance or {}).get("ts", 0.0) or 0.0),
            x.signature,
        )
    )

    if max_entries < 1:
        max_entries = 1
    evicted = max(0, len(deduped) - max_entries)
    return deduped[:max_entries], evicted


def save_cycle_store(
    cycles: List[ConsolidatedCycle],
    path: str | Path,
    *,
    run_id: str,
    sanity: Dict[str, Any],
    source_report: Optional[str] = None,
    max_entries: int = DEFAULT_MAX_ENTRIES,
) -> Dict[str, Any]:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    existing: List[ConsolidatedCycle] = []
    if p.exists():
        try:
            prior = json.loads(p.read_text(encoding="utf-8"))
            existing_items = prior.get("items") or []
            existing = [_parse_consolidated_cycle(item) for item in existing_items]
        except Exception:
            # Corrupt or incompatible store; overwrite with current batch.
            existing = []

    merged, evicted = _dedupe_and_cap(existing + cycles, max_entries=max_entries)

    payload = {
        "schema_version": "cycle_store.v1",
        "run_id": run_id,
        "sanity": sanity,
        "source_report": source_report,
        "count": len(merged),
        "max_entries": int(max_entries),
        "evicted_entries": int(evicted),
        "items": [asdict(c) for c in merged],
        "ts": time.time(),
    }
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def load_cycle_store(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {
            "schema_version": "cycle_store.v1",
            "count": 0,
            "items": [],
            "missing": True,
        }
    return json.loads(p.read_text(encoding="utf-8"))

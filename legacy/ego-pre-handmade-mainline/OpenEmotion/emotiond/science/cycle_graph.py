"""CycleGraph utilities for MVP11.4.

Deterministic, lightweight latent navigation graph built from cycle signatures.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple


DEFAULT_MAX_NODES = 256
DEFAULT_MAX_EDGES = 2048


def _event_signature(event: Dict[str, Any]) -> str:
    sig = event.get("cycle_signature")
    if sig:
        return str(sig)
    bucket = event.get("cycle_bucket") or {}
    # fallback for compatibility if signature wasn't precomputed
    if isinstance(bucket, dict):
        return str(bucket.get("signature") or bucket.get("sig") or "")
    return ""


def _recency_rank(last_seen: Dict[str, int], key: str) -> int:
    return int(last_seen.get(key, -1))


def build_cycle_graph(
    events: List[Dict[str, Any]],
    *,
    max_nodes: int = DEFAULT_MAX_NODES,
    max_edges: int = DEFAULT_MAX_EDGES,
) -> Dict[str, Any]:
    """Build deterministic cycle graph payload from event stream.

    Output contains:
    - nodes: [{signature, count, last_seen_idx}]
    - edges: [{from, to, count, last_seen_idx}]
    - transition_counts: map("from->to" -> count)
    - top_edges: top transitions by count/recency
    """
    signatures: List[str] = []
    for e in events:
        sig = _event_signature(e)
        if sig:
            signatures.append(sig)

    node_counts = Counter(signatures)
    edge_counts = Counter((a, b) for a, b in zip(signatures, signatures[1:]))

    node_last_seen: Dict[str, int] = {}
    edge_last_seen: Dict[Tuple[str, str], int] = {}

    for idx, sig in enumerate(signatures):
        node_last_seen[sig] = idx
    for idx, (a, b) in enumerate(zip(signatures, signatures[1:])):
        edge_last_seen[(a, b)] = idx

    # Capacity governance: keep highest support, then newest, then lexical
    kept_nodes = sorted(
        node_counts.keys(),
        key=lambda s: (-node_counts[s], -_recency_rank(node_last_seen, s), s),
    )[: max(1, int(max_nodes))]
    kept_node_set = set(kept_nodes)

    filtered_edges = {
        edge: c
        for edge, c in edge_counts.items()
        if edge[0] in kept_node_set and edge[1] in kept_node_set
    }

    kept_edges = sorted(
        filtered_edges.keys(),
        key=lambda e: (-filtered_edges[e], -int(edge_last_seen.get(e, -1)), e[0], e[1]),
    )[: max(1, int(max_edges))]

    nodes = [
        {
            "signature": s,
            "count": int(node_counts[s]),
            "last_seen_idx": int(node_last_seen.get(s, -1)),
        }
        for s in kept_nodes
    ]

    edges = [
        {
            "from": a,
            "to": b,
            "count": int(filtered_edges[(a, b)]),
            "last_seen_idx": int(edge_last_seen.get((a, b), -1)),
        }
        for a, b in kept_edges
    ]

    transition_counts = {f"{a}->{b}": int(filtered_edges[(a, b)]) for a, b in kept_edges}

    top_edges = [
        {"from": e["from"], "to": e["to"], "count": e["count"]}
        for e in edges[: min(20, len(edges))]
    ]

    return {
        "schema_version": "cycle_graph.v1",
        "events": int(len(events)),
        "signatures": int(len(signatures)),
        "node_count": int(len(nodes)),
        "edge_count": int(len(edges)),
        "max_nodes": int(max_nodes),
        "max_edges": int(max_edges),
        "nodes": nodes,
        "edges": edges,
        "transition_counts": transition_counts,
        "top_edges": top_edges,
    }


def save_cycle_graph(graph: Dict[str, Any], path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(graph)
    payload["path"] = str(p)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def load_cycle_graph(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {
            "schema_version": "cycle_graph.v1",
            "missing": True,
            "node_count": 0,
            "edge_count": 0,
            "nodes": [],
            "edges": [],
            "transition_counts": {},
            "top_edges": [],
            "path": str(p),
        }
    return json.loads(p.read_text(encoding="utf-8"))

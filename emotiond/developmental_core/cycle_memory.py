"""
MVP12 Cycle Memory

Persists cycle state for replay and traceability.
All cycles must be deterministic and replayable.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import CycleContext, CycleResult, Candidate


class CycleMemory:
    """
    Manages persistence and retrieval of developmental cycle data.

    All cycles are stored with full trace information for replay verification.
    """

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path or "artifacts/mvp12")
        self.cycles_file = self.storage_path / "developmental_cycles.json"
        self.pool_file = self.storage_path / "candidate_pool.json"
        self.traces_dir = self.storage_path / "cycle_traces"

        # Ensure directories exist
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.traces_dir.mkdir(parents=True, exist_ok=True)

        # Initialize storage
        self._cycles: Dict[str, Dict[str, Any]] = {}
        self._candidate_pool: List[Dict[str, Any]] = []

        self._load()

    def _load(self) -> None:
        """Load existing data from storage."""
        if self.cycles_file.exists():
            try:
                with open(self.cycles_file, "r") as f:
                    self._cycles = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._cycles = {}

        if self.pool_file.exists():
            try:
                with open(self.pool_file, "r") as f:
                    self._candidate_pool = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._candidate_pool = []

    def _save(self) -> None:
        """Save data to storage."""
        with open(self.cycles_file, "w") as f:
            json.dump(self._cycles, f, indent=2, default=str)

        with open(self.pool_file, "w") as f:
            json.dump(self._candidate_pool, f, indent=2, default=str)

    def store_cycle(self, result: CycleResult) -> None:
        """Store a completed cycle result."""
        cycle_data = result.to_dict()
        self._cycles[result.context.cycle_id] = cycle_data

        # Write trace file
        trace_file = self.traces_dir / f"{result.context.cycle_id}.json"
        with open(trace_file, "w") as f:
            json.dump(cycle_data, f, indent=2, default=str)

        self._save()

    def add_to_pool(self, candidate: Candidate, score: float) -> None:
        """Add an approved candidate to the candidate pool."""
        pool_entry = {
            "candidate": candidate.to_dict(),
            "score": score,
            "added_at": datetime.utcnow().isoformat(),
            "status": "pending",
        }
        self._candidate_pool.append(pool_entry)
        self._save()

    def get_cycle(self, cycle_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a cycle by ID."""
        return self._cycles.get(cycle_id)

    def get_candidate_pool(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get candidates from the pool, optionally filtered by status."""
        if status is None:
            return self._candidate_pool.copy()
        return [c for c in self._candidate_pool if c.get("status") == status]

    def update_candidate_status(
        self,
        candidate_id: str,
        status: str,
        notes: Optional[str] = None,
    ) -> bool:
        """Update the status of a candidate in the pool."""
        for entry in self._candidate_pool:
            if entry.get("candidate", {}).get("id") == candidate_id:
                entry["status"] = status
                if notes:
                    entry["notes"] = notes
                self._save()
                return True
        return False

    def get_cycle_count(self) -> int:
        """Get total number of stored cycles."""
        return len(self._cycles)

    def get_pool_size(self) -> int:
        """Get current size of candidate pool."""
        return len(self._candidate_pool)

    def get_pending_candidates(self) -> List[Dict[str, Any]]:
        """Get all pending candidates from the pool."""
        return self.get_candidate_pool(status="pending")

    def clear_pool(self) -> None:
        """Clear the candidate pool."""
        self._candidate_pool.clear()
        self._save()

    def verify_replay(self, cycle_id: str) -> Dict[str, Any]:
        """
        Verify that a cycle can be replayed.

        Returns verification result with trace_hash match status.
        """
        cycle = self.get_cycle(cycle_id)
        if not cycle:
            return {"verified": False, "error": "Cycle not found"}

        trace_file = self.traces_dir / f"{cycle_id}.json"
        if not trace_file.exists():
            return {"verified": False, "error": "Trace file not found"}

        try:
            with open(trace_file, "r") as f:
                trace_data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            return {"verified": False, "error": f"Trace read error: {e}"}

        # Verify trace_hash match
        stored_hash = cycle.get("trace_hash")
        trace_hash = trace_data.get("trace_hash")

        if stored_hash != trace_hash:
            return {
                "verified": False,
                "error": "Trace hash mismatch",
                "stored": stored_hash,
                "trace": trace_hash,
            }

        return {"verified": True, "cycle_id": cycle_id}

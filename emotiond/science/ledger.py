"""
MVP-10/11 Event Log Writer + Snapshot Generator

Provides deterministic logging for replay and analysis.
Output: artifacts/mvp{10,11}/run_<id>.jsonl + snapshot_<id>.json

Backward compat: MVP10 writer unchanged, MVP11 adds new fields.
"""
import json
import os
import time
import uuid
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum


# ============================================================================
# Shared Dataclasses (MVP10 + MVP11)
# ============================================================================

@dataclass
class Candidate:
    """A candidate intent/focus considered during decision."""
    id: str
    score: float
    type: str = "intent"
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Action:
    """An action to be executed."""
    type: str  # seek_info, attempt_solution, run_check, apply_fix, commit_progress, noop
    params: Dict[str, Any] = field(default_factory=dict)
    target: Optional[str] = None


@dataclass
class Outcome:
    """Result of an action."""
    status: str  # success, fail, partial
    reason: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StateDelta:
    """Changes to state after a tick."""
    before: Dict[str, Any] = field(default_factory=dict)
    after: Dict[str, Any] = field(default_factory=dict)
    changed_keys: List[str] = field(default_factory=list)


@dataclass
class Intervention:
    """An intervention applied during execution."""
    type: str
    reason: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Result of plan validation."""
    passed: bool
    violations: List[str] = field(default_factory=list)
    replan_count: int = 0


# ============================================================================
# MVP10 Event Log (unchanged for backward compat)
# ============================================================================

@dataclass
class EventLog:
    """A single event log entry (MVP10)."""
    tick_id: int
    run_id: str
    seed: int
    ts: float
    candidates: List[Candidate]
    chosen_focus: str
    chosen_intent: str
    policy_params: Dict[str, Any]
    plan: Dict[str, Any]
    action: Action
    outcome: Outcome
    state_delta: StateDelta
    interventions: List[Intervention] = field(default_factory=list)
    validation: Optional[ValidationResult] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        # Convert dataclass objects
        d['candidates'] = [asdict(c) if isinstance(c, Candidate) else c for c in self.candidates]
        d['action'] = asdict(self.action) if isinstance(self.action, Action) else self.action
        d['outcome'] = asdict(self.outcome) if isinstance(self.outcome, Outcome) else self.outcome
        d['state_delta'] = asdict(self.state_delta) if isinstance(self.state_delta, StateDelta) else self.state_delta
        d['interventions'] = [asdict(i) if isinstance(i, Intervention) else i for i in self.interventions]
        if self.validation:
            d['validation'] = asdict(self.validation)
        return d


# ============================================================================
# MVP11 New Dataclasses
# ============================================================================

class GovernorDecision(str, Enum):
    """Governor v2 decision types."""
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    DENY = "DENY"


@dataclass
class HomeostasisState:
    """
    6-dimensional homeostasis state.
    Represents virtual resource/pressure levels.
    """
    energy: float = 1.0        # 0.0-1.0: Available energy
    safety: float = 1.0        # 0.0-1.0: Safety margin
    affiliation: float = 1.0   # 0.0-1.0: Social connection
    certainty: float = 1.0     # 0.0-1.0: Predictability
    autonomy: float = 1.0      # 0.0-1.0: Agency/control
    fairness: float = 1.0      # 0.0-1.0: Perceived fairness
    
    def to_dict(self) -> Dict[str, float]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HomeostasisState":
        return cls(
            energy=data.get("energy", 1.0),
            safety=data.get("safety", 1.0),
            affiliation=data.get("affiliation", 1.0),
            certainty=data.get("certainty", 1.0),
            autonomy=data.get("autonomy", 1.0),
            fairness=data.get("fairness", 1.0),
        )
    
    def compute_checksum(self) -> str:
        """Compute checksum of state for integrity."""
        state_str = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(state_str.encode()).hexdigest()[:16]


@dataclass
class EFETerms:
    """
    Expected Free Energy terms for Active-Inference style decision making.
    
    EFE = risk + ambiguity - info_gain + cost
    
    Lower is better (minimize surprise).
    """
    risk: float = 0.0          # Expected prediction error
    ambiguity: float = 0.0     # Model uncertainty
    info_gain: float = 0.0     # Expected information gain (negative in EFE)
    cost: float = 0.0          # Action cost
    
    def compute_total(self) -> float:
        """Compute total EFE value."""
        return self.risk + self.ambiguity - self.info_gain + self.cost
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "risk": self.risk,
            "ambiguity": self.ambiguity,
            "info_gain": self.info_gain,
            "cost": self.cost,
            "total": self.compute_total(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EFETerms":
        return cls(
            risk=data.get("risk", 0.0),
            ambiguity=data.get("ambiguity", 0.0),
            info_gain=data.get("info_gain", 0.0),
            cost=data.get("cost", 0.0),
        )


@dataclass
class GovernorDecisionRecord:
    """
    Record of Governor v2 decision.
    """
    decision: str  # ALLOW, REQUIRE_APPROVAL, DENY
    reason: str = ""
    override: bool = False  # Was this overridden?
    confidence: float = 1.0
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GovernorDecisionRecord":
        return cls(
            decision=data.get("decision", "ALLOW"),
            reason=data.get("reason", ""),
            override=data.get("override", False),
            confidence=data.get("confidence", 1.0),
            details=data.get("details", {}),
        )


@dataclass
class EventLogMVP11:
    """
    MVP11 Event Log with homeostasis, EFE, and governor fields.
    Extends MVP10 schema while maintaining backward compatibility.
    """
    # MVP10 fields (unchanged)
    tick_id: int
    run_id: str
    seed: int
    ts: float
    candidates: List[Candidate]
    chosen_focus: str
    chosen_intent: str
    policy_params: Dict[str, Any]
    plan: Dict[str, Any]
    action: Action
    outcome: Outcome
    state_delta: StateDelta
    interventions: List[Intervention] = field(default_factory=list)
    validation: Optional[ValidationResult] = None
    
    # MVP11 new fields
    homeostasis_state: Optional[HomeostasisState] = None
    efe_terms: Optional[EFETerms] = None
    governor_decision: Optional[GovernorDecisionRecord] = None
    # MVP11.2 cycle evidence fields (optional)
    cycle_signature: Optional[str] = None
    cycle_bucket: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = {
            # MVP10 fields
            "tick_id": self.tick_id,
            "run_id": self.run_id,
            "seed": self.seed,
            "ts": self.ts,
            "candidates": [asdict(c) if isinstance(c, Candidate) else c for c in self.candidates],
            "chosen_focus": self.chosen_focus,
            "chosen_intent": self.chosen_intent,
            "policy_params": self.policy_params,
            "plan": self.plan,
            "action": asdict(self.action) if isinstance(self.action, Action) else self.action,
            "outcome": asdict(self.outcome) if isinstance(self.outcome, Outcome) else self.outcome,
            "state_delta": asdict(self.state_delta) if isinstance(self.state_delta, StateDelta) else self.state_delta,
            "interventions": [asdict(i) if isinstance(i, Intervention) else i for i in self.interventions],
        }
        
        if self.validation:
            d["validation"] = asdict(self.validation)
        
        # MVP11 fields
        if self.homeostasis_state:
            d["homeostasis_state"] = self.homeostasis_state.to_dict()
        if self.efe_terms:
            d["efe_terms"] = self.efe_terms.to_dict()
        if self.governor_decision:
            d["governor_decision"] = self.governor_decision.to_dict()
        if self.cycle_signature:
            d["cycle_signature"] = self.cycle_signature
        if self.cycle_bucket:
            d["cycle_bucket"] = self.cycle_bucket
        
        return d


# ============================================================================
# State Snapshot (shared)
# ============================================================================

@dataclass
class StateSnapshot:
    """A snapshot of state at a key point."""
    snapshot_id: str
    run_id: str
    tick_id: int
    ts: float
    state: Dict[str, Any]
    checksum: str = ""

    def compute_checksum(self) -> str:
        """Compute checksum of state for integrity."""
        state_str = json.dumps(self.state, sort_keys=True)
        return hashlib.sha256(state_str.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "snapshot_id": self.snapshot_id,
            "run_id": self.run_id,
            "tick_id": self.tick_id,
            "ts": self.ts,
            "state": self.state,
            "checksum": self.checksum or self.compute_checksum()
        }


@dataclass
class StateSnapshotMVP11:
    """MVP11 snapshot with homeostasis state."""
    snapshot_id: str
    run_id: str
    tick_id: int
    ts: float
    state: Dict[str, Any]
    homeostasis_state: Optional[HomeostasisState] = None
    checksum: str = ""

    def compute_checksum(self) -> str:
        """Compute checksum of state for integrity."""
        state_str = json.dumps(self.state, sort_keys=True)
        return hashlib.sha256(state_str.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = {
            "snapshot_id": self.snapshot_id,
            "run_id": self.run_id,
            "tick_id": self.tick_id,
            "ts": self.ts,
            "state": self.state,
            "checksum": self.checksum or self.compute_checksum()
        }
        if self.homeostasis_state:
            d["homeostasis_state"] = self.homeostasis_state.to_dict()
        return d


# ============================================================================
# MVP10 Ledger (unchanged for backward compat)
# ============================================================================

class Ledger:
    """Event log writer and snapshot generator for MVP-10."""

    def __init__(self, artifacts_dir: str = "artifacts/mvp10"):
        self.artifacts_dir = Path(artifacts_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.run_id: str = ""
        self.seed: int = 0
        self.events: List[EventLog] = []
        self.snapshots: List[StateSnapshot] = []
        self._file_handle = None

    def start_run(self, seed: int = 0, run_id: Optional[str] = None) -> str:
        """Start a new run with given seed."""
        self.seed = seed
        self.run_id = run_id or f"run_{uuid.uuid4().hex[:8]}"
        self.events = []
        self.snapshots = []
        
        # Open JSONL file for this run
        log_path = self.artifacts_dir / f"{self.run_id}.jsonl"
        self._file_handle = open(log_path, 'a')
        
        return self.run_id

    def log_event(self, event: EventLog) -> None:
        """Log an event to the JSONL file."""
        if self._file_handle is None:
            raise RuntimeError("Run not started. Call start_run() first.")
        
        self.events.append(event)
        line = json.dumps(event.to_dict())
        self._file_handle.write(line + '\n')
        self._file_handle.flush()

    def take_snapshot(self, state: Dict[str, Any], tick_id: int) -> StateSnapshot:
        """Take a snapshot of the current state."""
        snapshot = StateSnapshot(
            snapshot_id=f"snap_{uuid.uuid4().hex[:8]}",
            run_id=self.run_id,
            tick_id=tick_id,
            ts=time.time(),
            state=state
        )
        snapshot.checksum = snapshot.compute_checksum()
        self.snapshots.append(snapshot)
        
        # Write snapshot file
        snapshot_path = self.artifacts_dir / f"snapshot_{self.run_id}_{tick_id}.json"
        with open(snapshot_path, 'w') as f:
            json.dump(snapshot.to_dict(), f, indent=2)
        
        return snapshot

    def end_run(self) -> Dict[str, Any]:
        """End the current run and return summary."""
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None
        
        summary = {
            "run_id": self.run_id,
            "seed": self.seed,
            "total_ticks": len(self.events),
            "snapshots": len(self.snapshots),
            "start_ts": self.events[0].ts if self.events else None,
            "end_ts": self.events[-1].ts if self.events else None,
        }
        
        # Write summary file
        summary_path = self.artifacts_dir / f"summary_{self.run_id}.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        return summary

    def load_run(self, run_id: str) -> List[Dict[str, Any]]:
        """Load events from a previous run."""
        log_path = self.artifacts_dir / f"{run_id}.jsonl"
        events = []
        with open(log_path, 'r') as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        return events

    def load_snapshot(self, run_id: str, tick_id: int) -> Optional[Dict[str, Any]]:
        """Load a snapshot from a previous run."""
        snapshot_path = self.artifacts_dir / f"snapshot_{run_id}_{tick_id}.json"
        if snapshot_path.exists():
            with open(snapshot_path, 'r') as f:
                return json.load(f)
        return None


# ============================================================================
# MVP11 Ledger
# ============================================================================

class LedgerMVP11:
    """Event log writer and snapshot generator for MVP-11."""

    def __init__(self, artifacts_dir: str = "artifacts/mvp11"):
        self.artifacts_dir = Path(artifacts_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.run_id: str = ""
        self.seed: int = 0
        self.events: List[EventLogMVP11] = []
        self.snapshots: List[StateSnapshotMVP11] = []
        self._file_handle = None

    def start_run(self, seed: int = 0, run_id: Optional[str] = None) -> str:
        """Start a new run with given seed."""
        self.seed = seed
        self.run_id = run_id or f"run_{uuid.uuid4().hex[:8]}"
        self.events = []
        self.snapshots = []
        
        # Open JSONL file for this run
        log_path = self.artifacts_dir / f"{self.run_id}.jsonl"
        self._file_handle = open(log_path, 'a')
        
        return self.run_id

    def log_event(self, event: EventLogMVP11) -> None:
        """Log an MVP11 event to the JSONL file."""
        if self._file_handle is None:
            raise RuntimeError("Run not started. Call start_run() first.")
        
        self.events.append(event)
        line = json.dumps(event.to_dict())
        self._file_handle.write(line + '\n')
        self._file_handle.flush()

    def take_snapshot(
        self, 
        state: Dict[str, Any], 
        tick_id: int,
        homeostasis_state: Optional[HomeostasisState] = None
    ) -> StateSnapshotMVP11:
        """Take a snapshot of the current state with homeostasis."""
        snapshot = StateSnapshotMVP11(
            snapshot_id=f"snap_{uuid.uuid4().hex[:8]}",
            run_id=self.run_id,
            tick_id=tick_id,
            ts=time.time(),
            state=state,
            homeostasis_state=homeostasis_state
        )
        snapshot.checksum = snapshot.compute_checksum()
        self.snapshots.append(snapshot)
        
        # Write snapshot file
        snapshot_path = self.artifacts_dir / f"snapshot_{self.run_id}_{tick_id}.json"
        with open(snapshot_path, 'w') as f:
            json.dump(snapshot.to_dict(), f, indent=2)
        
        return snapshot

    def end_run(self) -> Dict[str, Any]:
        """End the current run and return summary."""
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None
        
        summary = {
            "run_id": self.run_id,
            "seed": self.seed,
            "total_ticks": len(self.events),
            "snapshots": len(self.snapshots),
            "start_ts": self.events[0].ts if self.events else None,
            "end_ts": self.events[-1].ts if self.events else None,
            "schema_version": "mvp11.v1",
        }
        
        # Write summary file
        summary_path = self.artifacts_dir / f"summary_{self.run_id}.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        return summary

    def load_run(self, run_id: str) -> List[Dict[str, Any]]:
        """Load events from a previous run."""
        log_path = self.artifacts_dir / f"{run_id}.jsonl"
        events = []
        with open(log_path, 'r') as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        return events

    def load_snapshot(self, run_id: str, tick_id: int) -> Optional[Dict[str, Any]]:
        """Load a snapshot from a previous run."""
        snapshot_path = self.artifacts_dir / f"snapshot_{run_id}_{tick_id}.json"
        if snapshot_path.exists():
            with open(snapshot_path, 'r') as f:
                return json.load(f)
        return None


# ============================================================================
# Helper Functions
# ============================================================================

def create_event_log(
    tick_id: int,
    run_id: str,
    seed: int,
    candidates: List[Dict[str, Any]],
    chosen_focus: str,
    chosen_intent: str,
    policy_params: Dict[str, Any],
    plan: Dict[str, Any],
    action_type: str,
    action_params: Dict[str, Any],
    outcome_status: str,
    outcome_reason: str = "",
    state_delta: Optional[Dict[str, Any]] = None,
    interventions: Optional[List[Dict[str, Any]]] = None,
    validation: Optional[Dict[str, Any]] = None,
) -> EventLog:
    """Helper function to create an MVP10 EventLog."""
    return EventLog(
        tick_id=tick_id,
        run_id=run_id,
        seed=seed,
        ts=time.time(),
        candidates=[Candidate(**c) for c in candidates],
        chosen_focus=chosen_focus,
        chosen_intent=chosen_intent,
        policy_params=policy_params,
        plan=plan,
        action=Action(type=action_type, params=action_params),
        outcome=Outcome(status=outcome_status, reason=outcome_reason),
        state_delta=StateDelta(**(state_delta or {})),
        interventions=[Intervention(**i) for i in (interventions or [])],
        validation=ValidationResult(**validation) if validation else None,
    )


def create_event_log_mvp11(
    tick_id: int,
    run_id: str,
    seed: int,
    candidates: List[Dict[str, Any]],
    chosen_focus: str,
    chosen_intent: str,
    policy_params: Dict[str, Any],
    plan: Dict[str, Any],
    action_type: str,
    action_params: Dict[str, Any],
    outcome_status: str,
    outcome_reason: str = "",
    state_delta: Optional[Dict[str, Any]] = None,
    interventions: Optional[List[Dict[str, Any]]] = None,
    validation: Optional[Dict[str, Any]] = None,
    # MVP11 fields
    homeostasis_state: Optional[Dict[str, float]] = None,
    efe_terms: Optional[Dict[str, float]] = None,
    governor_decision: Optional[Dict[str, Any]] = None,
    cycle_signature: Optional[str] = None,
    cycle_bucket: Optional[Dict[str, Any]] = None,
) -> EventLogMVP11:
    """Helper function to create an MVP11 EventLog."""
    return EventLogMVP11(
        tick_id=tick_id,
        run_id=run_id,
        seed=seed,
        ts=time.time(),
        candidates=[Candidate(**c) for c in candidates],
        chosen_focus=chosen_focus,
        chosen_intent=chosen_intent,
        policy_params=policy_params,
        plan=plan,
        action=Action(type=action_type, params=action_params),
        outcome=Outcome(status=outcome_status, reason=outcome_reason),
        state_delta=StateDelta(**(state_delta or {})),
        interventions=[Intervention(**i) for i in (interventions or [])],
        validation=ValidationResult(**validation) if validation else None,
        # MVP11 fields
        homeostasis_state=HomeostasisState.from_dict(homeostasis_state) if homeostasis_state else None,
        efe_terms=EFETerms.from_dict(efe_terms) if efe_terms else None,
        governor_decision=GovernorDecisionRecord.from_dict(governor_decision) if governor_decision else None,
        cycle_signature=cycle_signature,
        cycle_bucket=cycle_bucket,
    )

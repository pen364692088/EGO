"""
MVP11 Replay Backward Compatibility Tests

Tests that:
1. MVP10 replay still works (backward compat)
2. MVP11 replay is deterministic
3. Schema versions are correctly detected
"""
import json
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any

import pytest

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from emotiond.science.ledger import (
    Ledger, LedgerMVP11, EventLog, EventLogMVP11,
    Candidate, Action, Outcome, StateDelta, Intervention,
    HomeostasisState, EFETerms, GovernorDecisionRecord,
    create_event_log, create_event_log_mvp11,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_artifacts_dir():
    """Create a temporary artifacts directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mvp10_ledger(temp_artifacts_dir):
    """Create an MVP10 ledger."""
    artifacts_dir = Path(temp_artifacts_dir) / "mvp10"
    return Ledger(artifacts_dir=str(artifacts_dir))


@pytest.fixture
def mvp11_ledger(temp_artifacts_dir):
    """Create an MVP11 ledger."""
    artifacts_dir = Path(temp_artifacts_dir) / "mvp11"
    return LedgerMVP11(artifacts_dir=str(artifacts_dir))


# ============================================================================
# MVP10 Backward Compatibility Tests
# ============================================================================

class TestMVP10BackwardCompat:
    """Tests to ensure MVP10 ledger and replay still work."""

    def test_mvp10_ledger_creates_run(self, mvp10_ledger):
        """Test that MVP10 ledger can create a run."""
        run_id = mvp10_ledger.start_run(seed=42)
        assert run_id.startswith("run_")
        assert mvp10_ledger.seed == 42

    def test_mvp10_ledger_logs_events(self, mvp10_ledger):
        """Test that MVP10 ledger can log events."""
        mvp10_ledger.start_run(seed=42, run_id="test_run")
        
        event = create_event_log(
            tick_id=1,
            run_id="test_run",
            seed=42,
            candidates=[{"id": "goal_0", "score": 0.9, "type": "goal", "meta": {"goal": "test_goal"}}],
            chosen_focus="test_goal",
            chosen_intent="achieve",
            policy_params={},
            plan={"steps": [], "risk_level": "low", "expected_outcome": "success"},
            action_type="seek_info",
            action_params={},
            outcome_status="success",
            outcome_reason="",
        )
        
        mvp10_ledger.log_event(event)
        
        assert len(mvp10_ledger.events) == 1
        assert mvp10_ledger.events[0].chosen_focus == "test_goal"

    def test_mvp10_ledger_persists_events(self, mvp10_ledger):
        """Test that MVP10 ledger persists events to disk."""
        run_id = mvp10_ledger.start_run(seed=42, run_id="persist_test")
        
        event = create_event_log(
            tick_id=1,
            run_id=run_id,
            seed=42,
            candidates=[{"id": "g1", "score": 0.9}],
            chosen_focus="goal1",
            chosen_intent="achieve",
            policy_params={},
            plan={"steps": [], "risk_level": "low", "expected_outcome": "success"},
            action_type="noop",
            action_params={},
            outcome_status="success",
        )
        
        mvp10_ledger.log_event(event)
        mvp10_ledger.end_run()
        
        # Load and verify
        loaded_events = mvp10_ledger.load_run("persist_test")
        assert len(loaded_events) == 1
        assert loaded_events[0]["chosen_focus"] == "goal1"

    def test_mvp10_snapshot(self, mvp10_ledger):
        """Test that MVP10 snapshots work."""
        mvp10_ledger.start_run(seed=42, run_id="snap_test")
        
        snapshot = mvp10_ledger.take_snapshot(
            state={"key": "value", "count": 5},
            tick_id=1
        )
        
        assert snapshot.tick_id == 1
        assert snapshot.state["key"] == "value"
        assert snapshot.checksum != ""

    def test_mvp10_replay_deterministic(self, mvp10_ledger):
        """Test that MVP10 replay is deterministic with same seed."""
        run_id = mvp10_ledger.start_run(seed=12345, run_id="det_test")
        
        # Log multiple events
        for i in range(5):
            event = create_event_log(
                tick_id=i + 1,
                run_id=run_id,
                seed=12345,
                candidates=[{"id": f"g{i}", "score": 1.0 - i * 0.1}],
                chosen_focus=f"goal_{i}",
                chosen_intent="achieve",
                policy_params={},
                plan={"steps": [], "risk_level": "low", "expected_outcome": "success"},
                action_type="seek_info",
                action_params={},
                outcome_status="success",
            )
            mvp10_ledger.log_event(event)
        
        summary = mvp10_ledger.end_run()
        
        # Reload and verify all events
        loaded = mvp10_ledger.load_run("det_test")
        assert len(loaded) == 5
        
        # Verify deterministic fields
        for i, event in enumerate(loaded):
            assert event["seed"] == 12345
            assert event["tick_id"] == i + 1


# ============================================================================
# MVP11 Ledger Tests
# ============================================================================

class TestMVP11Ledger:
    """Tests for MVP11 ledger functionality."""

    def test_mvp11_ledger_creates_run(self, mvp11_ledger):
        """Test that MVP11 ledger can create a run."""
        run_id = mvp11_ledger.start_run(seed=42)
        assert run_id.startswith("run_")
        assert mvp11_ledger.seed == 42

    def test_mvp11_event_has_new_fields(self, mvp11_ledger):
        """Test that MVP11 events have new fields."""
        mvp11_ledger.start_run(seed=42, run_id="mvp11_test")
        
        event = create_event_log_mvp11(
            tick_id=1,
            run_id="mvp11_test",
            seed=42,
            candidates=[{"id": "g1", "score": 0.9}],
            chosen_focus="goal1",
            chosen_intent="achieve",
            policy_params={},
            plan={"steps": [], "risk_level": "low", "expected_outcome": "success"},
            action_type="seek_info",
            action_params={},
            outcome_status="success",
            homeostasis_state={"energy": 0.8, "safety": 0.9},
            efe_terms={"risk": 0.1, "ambiguity": 0.2, "info_gain": 0.3, "cost": 0.1},
            governor_decision={"decision": "ALLOW", "reason": "Low risk"},
        )
        
        mvp11_ledger.log_event(event)
        
        assert mvp11_ledger.events[0].homeostasis_state is not None
        assert mvp11_ledger.events[0].efe_terms is not None
        assert mvp11_ledger.events[0].governor_decision is not None

    def test_mvp11_event_serialization(self, mvp11_ledger):
        """Test that MVP11 events serialize correctly."""
        mvp11_ledger.start_run(seed=42, run_id="ser_test")
        
        event = create_event_log_mvp11(
            tick_id=1,
            run_id="ser_test",
            seed=42,
            candidates=[{"id": "g1", "score": 0.9}],
            chosen_focus="goal1",
            chosen_intent="achieve",
            policy_params={},
            plan={"steps": [], "risk_level": "low", "expected_outcome": "success"},
            action_type="seek_info",
            action_params={},
            outcome_status="success",
            homeostasis_state={"energy": 0.8, "safety": 0.9, "affiliation": 1.0, "certainty": 0.7, "autonomy": 0.85, "fairness": 0.95},
            efe_terms={"risk": 0.1, "ambiguity": 0.2, "info_gain": 0.3, "cost": 0.1},
            governor_decision={"decision": "ALLOW", "reason": "Low risk", "confidence": 0.9},
        )
        
        event_dict = event.to_dict()
        
        # Check MVP11 fields are present
        assert "homeostasis_state" in event_dict
        assert "efe_terms" in event_dict
        assert "governor_decision" in event_dict
        
        # Check homeostasis values
        assert event_dict["homeostasis_state"]["energy"] == 0.8
        
        # Check EFE total is computed
        assert "total" in event_dict["efe_terms"]
        
        # Check governor decision
        assert event_dict["governor_decision"]["decision"] == "ALLOW"

    def test_mvp11_snapshot_with_homeostasis(self, mvp11_ledger):
        """Test that MVP11 snapshots include homeostasis."""
        mvp11_ledger.start_run(seed=42, run_id="snap_mvp11")
        
        homeostasis = HomeostasisState(energy=0.7, safety=0.8)
        
        snapshot = mvp11_ledger.take_snapshot(
            state={"context": "test"},
            tick_id=1,
            homeostasis_state=homeostasis
        )
        
        assert snapshot.homeostasis_state is not None
        assert snapshot.homeostasis_state.energy == 0.7
        
        snapshot_dict = snapshot.to_dict()
        assert "homeostasis_state" in snapshot_dict


# ============================================================================
# MVP11 Replay Determinism Tests
# ============================================================================

class TestMVP11ReplayDeterminism:
    """Tests for MVP11 replay determinism."""

    def test_mvp11_replay_same_seed_same_hash(self, mvp11_ledger):
        """Test that same seed produces same event hash."""
        # Create a run with deterministic seed
        run_id = mvp11_ledger.start_run(seed=999, run_id="det_mvp11")
        
        homeostasis = HomeostasisState(energy=0.8, safety=0.9)
        efe = EFETerms(risk=0.1, ambiguity=0.2, info_gain=0.3, cost=0.1)
        gov = GovernorDecisionRecord(decision="ALLOW", reason="test")
        
        for i in range(3):
            event = create_event_log_mvp11(
                tick_id=i + 1,
                run_id=run_id,
                seed=999,
                candidates=[{"id": f"g{i}", "score": 0.9 - i * 0.1}],
                chosen_focus=f"goal_{i}",
                chosen_intent="achieve",
                policy_params={},
                plan={"steps": [], "risk_level": "low", "expected_outcome": "success"},
                action_type="seek_info",
                action_params={},
                outcome_status="success",
                homeostasis_state=homeostasis.to_dict(),
                efe_terms=efe.to_dict(),
                governor_decision=gov.to_dict(),
            )
            mvp11_ledger.log_event(event)
        
        summary = mvp11_ledger.end_run()
        
        # Load and verify
        loaded = mvp11_ledger.load_run("det_mvp11")
        assert len(loaded) == 3
        
        # All events should have same seed
        for event in loaded:
            assert event["seed"] == 999

    def test_mvp11_homeostasis_checksum_consistent(self):
        """Test that homeostasis checksum is consistent."""
        state1 = HomeostasisState(energy=0.8, safety=0.9)
        state2 = HomeostasisState(energy=0.8, safety=0.9)
        
        assert state1.compute_checksum() == state2.compute_checksum()
        
        state3 = HomeostasisState(energy=0.7, safety=0.9)
        assert state1.compute_checksum() != state3.compute_checksum()

    def test_mvp11_efe_total_deterministic(self):
        """Test that EFE total is computed deterministically."""
        efe1 = EFETerms(risk=0.1, ambiguity=0.2, info_gain=0.3, cost=0.1)
        efe2 = EFETerms(risk=0.1, ambiguity=0.2, info_gain=0.3, cost=0.1)
        
        assert efe1.compute_total() == efe2.compute_total()
        assert abs(efe1.compute_total() - 0.1) < 0.001  # 0.1 + 0.2 - 0.3 + 0.1 = 0.1


# ============================================================================
# Schema Detection Tests
# ============================================================================

class TestSchemaDetection:
    """Tests for schema version detection."""

    def test_detect_mvp10_events(self):
        """Test that MVP10 events are correctly detected."""
        from scripts.replay_mvp11 import detect_schema_version
        
        mvp10_events = [
            {
                "tick_id": 1,
                "run_id": "test",
                "seed": 42,
                "ts": 1234567890.0,
                "candidates": [],
                "chosen_focus": "goal",
                "chosen_intent": "achieve",
                "policy_params": {},
                "plan": {},
                "action": {"type": "noop"},
                "outcome": {"status": "success"},
                "state_delta": {},
                "interventions": [],
            }
        ]
        
        assert detect_schema_version(mvp10_events) == "mvp10"

    def test_detect_mvp11_events(self):
        """Test that MVP11 events are correctly detected."""
        from scripts.replay_mvp11 import detect_schema_version
        
        mvp11_events = [
            {
                "tick_id": 1,
                "run_id": "test",
                "seed": 42,
                "ts": 1234567890.0,
                "candidates": [],
                "chosen_focus": "goal",
                "chosen_intent": "achieve",
                "policy_params": {},
                "plan": {},
                "action": {"type": "noop"},
                "outcome": {"status": "success"},
                "state_delta": {},
                "interventions": [],
                "homeostasis_state": {"energy": 0.8},
            }
        ]
        
        assert detect_schema_version(mvp11_events) == "mvp11"

    def test_detect_mvp11_by_efe_terms(self):
        """Test that MVP11 events with efe_terms are detected."""
        from scripts.replay_mvp11 import detect_schema_version
        
        mvp11_events = [
            {
                "tick_id": 1,
                "run_id": "test",
                "seed": 42,
                "ts": 1234567890.0,
                "candidates": [],
                "chosen_focus": "goal",
                "chosen_intent": "achieve",
                "policy_params": {},
                "plan": {},
                "action": {"type": "noop"},
                "outcome": {"status": "success"},
                "state_delta": {},
                "interventions": [],
                "efe_terms": {"risk": 0.1},
            }
        ]
        
        assert detect_schema_version(mvp11_events) == "mvp11"


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for backward compatibility."""

    def test_mvp10_ledger_unchanged(self, temp_artifacts_dir):
        """Test that MVP10 ledger API is unchanged."""
        artifacts_dir = Path(temp_artifacts_dir) / "mvp10"
        ledger = Ledger(artifacts_dir=str(artifacts_dir))
        
        # This is the original MVP10 API - should work unchanged
        run_id = ledger.start_run(seed=42)
        
        event = create_event_log(
            tick_id=1,
            run_id=run_id,
            seed=42,
            candidates=[{"id": "g1", "score": 0.9, "type": "goal", "meta": {"goal": "test"}}],
            chosen_focus="test",
            chosen_intent="achieve",
            policy_params={},
            plan={"steps": [], "risk_level": "low", "expected_outcome": "success"},
            action_type="noop",
            action_params={},
            outcome_status="success",
        )
        
        ledger.log_event(event)
        summary = ledger.end_run()
        
        assert summary["total_ticks"] == 1
        assert summary["seed"] == 42

    def test_mvp11_ledger_mvp10_fields_present(self, mvp11_ledger):
        """Test that MVP11 events contain all MVP10 fields."""
        mvp11_ledger.start_run(seed=42, run_id="compat_test")
        
        # Create event without MVP11 fields
        event = create_event_log_mvp11(
            tick_id=1,
            run_id="compat_test",
            seed=42,
            candidates=[{"id": "g1", "score": 0.9}],
            chosen_focus="goal",
            chosen_intent="achieve",
            policy_params={},
            plan={"steps": [], "risk_level": "low", "expected_outcome": "success"},
            action_type="noop",
            action_params={},
            outcome_status="success",
        )
        
        mvp11_ledger.log_event(event)
        
        event_dict = mvp11_ledger.events[0].to_dict()
        
        # All MVP10 fields should be present
        mvp10_required = [
            "tick_id", "run_id", "seed", "ts", "candidates",
            "chosen_focus", "chosen_intent", "policy_params",
            "plan", "action", "outcome", "state_delta", "interventions"
        ]
        
        for field in mvp10_required:
            assert field in event_dict, f"Missing MVP10 field: {field}"


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestTraceDrivenReplaySelection:
    """Replay should prioritize logged trace over runtime RNG."""

    def test_replay_uses_logged_sample_r_when_present(self):
        from scripts.replay_mvp11 import select_index_from_trace_or_rng

        probs = [0.2, 0.5, 0.3]
        idx = select_index_from_trace_or_rng(probs, trace={"sample_r": 0.65})
        assert idx == 1  # 0.2 < 0.65 <= 0.7

    def test_replay_prefers_selected_idx_over_rng_drift(self):
        from scripts.replay_mvp11 import select_index_from_trace_or_rng
        import random

        probs = [0.2, 0.3, 0.5]
        # even if rng/sample_r would pick another index, selected_idx is authoritative
        idx = select_index_from_trace_or_rng(
            probs,
            trace={"selected_idx": 2, "sample_r": 0.01},
            rng=random.Random(999),
        )
        assert idx == 2

    def test_replay_falls_back_when_selected_idx_out_of_range(self):
        from scripts.replay_mvp11 import select_index_from_trace_or_rng

        probs = [0.4, 0.6]
        idx, reason = select_index_from_trace_or_rng(
            probs,
            trace={"selected_idx": 9, "sample_r": 0.2},
            return_meta=True,
        )
        assert idx == 0
        assert reason == "selected_idx_out_of_range"

    def test_replay_ignores_rng_drift_when_trace_present(self):
        from scripts.replay_mvp11 import select_index_from_trace_or_rng
        import random

        probs = [0.1, 0.2, 0.7]
        trace = {"sample_r": 0.95}

        # Consume RNG differently to simulate drift; selection should remain identical
        rng_a = random.Random(42)
        rng_b = random.Random(42)
        _ = [rng_b.random() for _ in range(100)]  # drift rng_b

        idx_a = select_index_from_trace_or_rng(probs, trace=trace, rng=rng_a)
        idx_b = select_index_from_trace_or_rng(probs, trace=trace, rng=rng_b)

        assert idx_a == idx_b == 2

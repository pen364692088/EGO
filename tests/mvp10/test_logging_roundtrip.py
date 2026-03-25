"""
T02 - Logging Roundtrip Tests

Tests for Event Log Writer + Snapshot Generator.
"""
import json
import os
import sys
from pathlib import Path

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from emotiond.science.ledger import (
    Ledger, EventLog, Candidate, Action, Outcome, StateDelta,
    Intervention, ValidationResult, StateSnapshot, create_event_log,
)


class TestLedgerBasics:
    """Basic ledger functionality tests."""

    def test_ledger_initialization(self, temp_artifacts_dir):
        """Test that ledger initializes correctly."""
        ledger = Ledger(artifacts_dir=temp_artifacts_dir)
        assert ledger.artifacts_dir == Path(temp_artifacts_dir)
        assert ledger.events == []
        assert ledger.snapshots == []

    def test_start_run(self, temp_artifacts_dir):
        """Test starting a new run."""
        ledger = Ledger(artifacts_dir=temp_artifacts_dir)
        run_id = ledger.start_run(seed=42)
        
        assert run_id.startswith("run_")
        assert ledger.run_id == run_id
        assert ledger.seed == 42
        assert ledger._file_handle is not None

    def test_end_run(self, temp_artifacts_dir):
        """Test ending a run."""
        ledger = Ledger(artifacts_dir=temp_artifacts_dir)
        ledger.start_run(seed=42)
        summary = ledger.end_run()
        
        assert "run_id" in summary
        assert "seed" in summary
        assert ledger._file_handle is None


class TestEventLogging:
    """Test event logging functionality."""

    def test_log_single_event(self, temp_artifacts_dir):
        """Test logging a single event."""
        ledger = Ledger(artifacts_dir=temp_artifacts_dir)
        ledger.start_run(seed=42)
        
        event = create_event_log(
            tick_id=1,
            run_id=ledger.run_id,
            seed=42,
            candidates=[{"id": "g1", "score": 1.0, "type": "goal"}],
            chosen_focus="test goal",
            chosen_intent="achieve",
            policy_params={},
            plan={"steps": [], "risk_level": "low", "expected_outcome": "test"},
            action_type="seek_info",
            action_params={"query": "test"},
            outcome_status="success",
            outcome_reason="test passed",
        )
        
        ledger.log_event(event)
        
        assert len(ledger.events) == 1
        assert ledger.events[0].tick_id == 1

    def test_log_multiple_events(self, temp_artifacts_dir):
        """Test logging multiple events."""
        ledger = Ledger(artifacts_dir=temp_artifacts_dir)
        ledger.start_run(seed=42)
        
        for i in range(5):
            event = create_event_log(
                tick_id=i,
                run_id=ledger.run_id,
                seed=42,
                candidates=[],
                chosen_focus=f"goal_{i}",
                chosen_intent="achieve",
                policy_params={},
                plan={"steps": [], "risk_level": "low", "expected_outcome": "test"},
                action_type="seek_info",
                action_params={},
                outcome_status="success",
            )
            ledger.log_event(event)
        
        assert len(ledger.events) == 5
        ledger.end_run()

    def test_event_to_dict(self, temp_artifacts_dir):
        """Test event serialization to dict."""
        event = EventLog(
            tick_id=1,
            run_id="run_test",
            seed=42,
            ts=1709515200.0,
            candidates=[Candidate(id="g1", score=1.0)],
            chosen_focus="test",
            chosen_intent="achieve",
            policy_params={},
            plan={"steps": []},
            action=Action(type="seek_info"),
            outcome=Outcome(status="success"),
            state_delta=StateDelta(),
        )
        
        d = event.to_dict()
        
        assert d["tick_id"] == 1
        assert d["run_id"] == "run_test"
        assert isinstance(d["candidates"], list)
        assert isinstance(d["action"], dict)


class TestSnapshotGeneration:
    """Test snapshot generation functionality."""

    def test_take_snapshot(self, temp_artifacts_dir):
        """Test taking a state snapshot."""
        ledger = Ledger(artifacts_dir=temp_artifacts_dir)
        ledger.start_run(seed=42)
        
        state = {
            "goals": [{"id": "g1", "status": "active"}],
            "context": {"key": "value"},
        }
        
        snapshot = ledger.take_snapshot(state, tick_id=5)
        
        assert snapshot.run_id == ledger.run_id
        assert snapshot.tick_id == 5
        assert snapshot.state == state
        assert snapshot.checksum != ""

    def test_snapshot_checksum(self, temp_artifacts_dir):
        """Test that snapshot checksum is deterministic."""
        state = {"key": "value", "number": 42}
        
        snap1 = StateSnapshot(
            snapshot_id="snap1",
            run_id="run1",
            tick_id=1,
            ts=1709515200.0,
            state=state,
        )
        snap2 = StateSnapshot(
            snapshot_id="snap2",
            run_id="run2",
            tick_id=2,
            ts=1709515200.0,
            state=state,
        )
        
        assert snap1.compute_checksum() == snap2.compute_checksum()

    def test_snapshot_checksum_changes(self, temp_artifacts_dir):
        """Test that different states produce different checksums."""
        snap1 = StateSnapshot(
            snapshot_id="snap1",
            run_id="run1",
            tick_id=1,
            ts=1709515200.0,
            state={"key": "value1"},
        )
        snap2 = StateSnapshot(
            snapshot_id="snap2",
            run_id="run2",
            tick_id=2,
            ts=1709515200.0,
            state={"key": "value2"},
        )
        
        assert snap1.compute_checksum() != snap2.compute_checksum()


class TestRoundtrip:
    """Test full roundtrip: write -> read -> compare."""

    def test_jsonl_roundtrip(self, temp_artifacts_dir):
        """Test that events can be written and read back."""
        ledger = Ledger(artifacts_dir=temp_artifacts_dir)
        run_id = ledger.start_run(seed=42)
        
        # Log events
        events_data = []
        for i in range(3):
            event = create_event_log(
                tick_id=i,
                run_id=run_id,
                seed=42,
                candidates=[{"id": f"g{i}", "score": 1.0}],
                chosen_focus=f"goal_{i}",
                chosen_intent="achieve",
                policy_params={"param": i},
                plan={"steps": [], "risk_level": "low", "expected_outcome": "test"},
                action_type="seek_info",
                action_params={},
                outcome_status="success",
            )
            ledger.log_event(event)
            events_data.append(event.to_dict())
        
        ledger.end_run()
        
        # Load events back
        loaded_events = ledger.load_run(run_id)
        
        assert len(loaded_events) == 3
        for i, loaded in enumerate(loaded_events):
            assert loaded["tick_id"] == i
            assert loaded["chosen_focus"] == f"goal_{i}"

    def test_snapshot_roundtrip(self, temp_artifacts_dir):
        """Test that snapshots can be written and read back."""
        ledger = Ledger(artifacts_dir=temp_artifacts_dir)
        ledger.start_run(seed=42)
        
        state = {"goals": ["g1"], "context": {"test": True}}
        snapshot = ledger.take_snapshot(state, tick_id=5)
        
        # Load snapshot back
        loaded = ledger.load_snapshot(ledger.run_id, tick_id=5)
        
        assert loaded is not None
        assert loaded["state"] == state
        assert loaded["tick_id"] == 5


class TestDataclasses:
    """Test dataclass functionality."""

    def test_candidate_creation(self):
        """Test Candidate dataclass."""
        c = Candidate(id="test", score=0.5, type="intent", meta={"key": "value"})
        assert c.id == "test"
        assert c.score == 0.5
        assert c.type == "intent"

    def test_action_creation(self):
        """Test Action dataclass."""
        a = Action(type="seek_info", params={"query": "test"}, target="env")
        assert a.type == "seek_info"
        assert a.params == {"query": "test"}

    def test_outcome_creation(self):
        """Test Outcome dataclass."""
        o = Outcome(status="success", reason="test passed", evidence={"key": "value"})
        assert o.status == "success"
        assert o.reason == "test passed"

    def test_state_delta_creation(self):
        """Test StateDelta dataclass."""
        sd = StateDelta(before={"a": 1}, after={"a": 2}, changed_keys=["a"])
        assert sd.before == {"a": 1}
        assert sd.after == {"a": 2}
        assert sd.changed_keys == ["a"]

    def test_intervention_creation(self):
        """Test Intervention dataclass."""
        i = Intervention(type="replan", reason="validation_failed", details={"count": 1})
        assert i.type == "replan"
        assert i.reason == "validation_failed"

    def test_validation_result_creation(self):
        """Test ValidationResult dataclass."""
        vr = ValidationResult(passed=False, violations=["constraint"], replan_count=1)
        assert vr.passed == False
        assert vr.violations == ["constraint"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

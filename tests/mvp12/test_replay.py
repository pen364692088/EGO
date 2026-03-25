"""
MVP12 Replay Verification Tests

Tests for deterministic replay and trace verification of developmental cycles.
"""

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from emotiond.developmental_core.cycle_engine import CycleEngine
from emotiond.developmental_core.hypothesis_generator import HypothesisGenerator
from emotiond.developmental_core.candidate_evaluator import CandidateEvaluator
from emotiond.developmental_core.cycle_memory import CycleMemory
from emotiond.developmental_core.models import (
    CycleContext,
    CycleResult,
    CycleTrigger,
    Candidate,
    CandidateType,
    InterpretationCandidate,
    ActionCandidate,
)
from emotiond.developmental_core.cycle_metrics import CycleMetricsCollector


class TestTraceHashDeterminism:
    """Tests for deterministic trace hash generation."""

    def test_same_seed_produces_same_trace_hash(self):
        """Identical seed and input must produce identical trace_hash."""
        seed = 12345
        state_snapshot = {"tension": 0.5, "energy": 0.8}

        # Create first context
        engine1 = CycleEngine(seed=seed)
        context1 = engine1.start_cycle(
            trigger=CycleTrigger.IDLE,
            state_snapshot=state_snapshot,
        )
        hash1 = context1.trace_hash

        # Create second context with same seed
        engine2 = CycleEngine(seed=seed)
        context2 = engine2.start_cycle(
            trigger=CycleTrigger.IDLE,
            state_snapshot=state_snapshot,
        )
        hash2 = context2.trace_hash

        assert hash1 == hash2, (
            f"Same seed should produce same trace_hash: {hash1} != {hash2}"
        )

    def test_different_seed_produces_different_trace_hash(self):
        """Different seeds should produce different trace_hashes."""
        state_snapshot = {"tension": 0.5}

        engine1 = CycleEngine(seed=111)
        context1 = engine1.start_cycle(
            trigger=CycleTrigger.IDLE,
            state_snapshot=state_snapshot,
        )

        engine2 = CycleEngine(seed=222)
        context2 = engine2.start_cycle(
            trigger=CycleTrigger.IDLE,
            state_snapshot=state_snapshot,
        )

        assert context1.trace_hash != context2.trace_hash, (
            "Different seeds should produce different trace_hashes"
        )

    def test_different_state_snapshot_produces_different_hash(self):
        """Different state snapshots should produce different hashes."""
        seed = 12345

        engine1 = CycleEngine(seed=seed)
        context1 = engine1.start_cycle(
            trigger=CycleTrigger.IDLE,
            state_snapshot={"tension": 0.5},
        )

        engine2 = CycleEngine(seed=seed)
        context2 = engine2.start_cycle(
            trigger=CycleTrigger.IDLE,
            state_snapshot={"tension": 0.9},
        )

        assert context1.trace_hash != context2.trace_hash, (
            "Different state snapshots should produce different hashes"
        )

    def test_trace_hash_is_deterministic_json(self):
        """Trace hash should be deterministic regardless of JSON ordering."""
        data1 = {"a": 1, "b": 2}
        data2 = {"b": 2, "a": 1}

        hash1 = hashlib.sha256(
            json.dumps(data1, sort_keys=True).encode()
        ).hexdigest()[:16]

        hash2 = hashlib.sha256(
            json.dumps(data2, sort_keys=True).encode()
        ).hexdigest()[:16]

        assert hash1 == hash2, "Hashes should be equal with sort_keys=True"


class TestCycleReplay:
    """Tests for cycle replay functionality."""

    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_cycle_can_be_stored_and_retrieved(self, temp_storage):
        """A cycle should be stored and retrievable with matching data."""
        memory = CycleMemory(storage_path=temp_storage)

        # Create and store a cycle
        engine = CycleEngine(seed=42)
        context = engine.start_cycle(
            trigger=CycleTrigger.IDLE,
            state_snapshot={"test": "data"},
        )

        # Generate candidates
        generator = HypothesisGenerator(seed=context.seed)
        candidates = generator.generate(context=context)

        # Complete and store
        result = engine.complete_cycle(context=context, candidates=candidates)
        memory.store_cycle(result)

        # Retrieve and verify
        stored = memory.get_cycle(context.cycle_id)
        assert stored is not None, "Cycle should be stored"
        assert stored["trace_hash"] == context.trace_hash, (
            "Trace hash should match"
        )
        assert stored["success"] is True, "Cycle should be successful"

    def test_cycle_replay_produces_same_candidates(self, temp_storage):
        """Replaying a cycle with same seed should produce same candidates."""
        seed = 54321
        state_snapshot = {"tension": 0.6, "energy": 0.7}

        # First run
        engine1 = CycleEngine(seed=seed)
        context1 = engine1.start_cycle(
            trigger=CycleTrigger.IDLE,
            state_snapshot=state_snapshot,
        )
        generator1 = HypothesisGenerator(seed=context1.seed)
        candidates1 = generator1.generate(context=context1)

        # Second run (replay) with same seed
        engine2 = CycleEngine(seed=seed)
        context2 = engine2.start_cycle(
            trigger=CycleTrigger.IDLE,
            state_snapshot=state_snapshot,
        )
        generator2 = HypothesisGenerator(seed=context2.seed)
        candidates2 = generator2.generate(context=context2)

        # Verify trace hashes match
        assert context1.trace_hash == context2.trace_hash, (
            "Trace hashes should match for replay"
        )

        # Verify same number of candidates
        assert len(candidates1) == len(candidates2), (
            f"Same seed should produce same number of candidates: "
            f"{len(candidates1)} != {len(candidates2)}"
        )

        # Verify candidate types match
        types1 = [c.candidate_type for c in candidates1]
        types2 = [c.candidate_type for c in candidates2]
        assert types1 == types2, "Candidate types should match"

    def test_cycle_memory_verify_replay(self, temp_storage):
        """CycleMemory should verify replay correctly."""
        memory = CycleMemory(storage_path=temp_storage)

        # Create and store a cycle
        engine = CycleEngine(seed=99)
        context = engine.start_cycle(trigger=CycleTrigger.IDLE)
        generator = HypothesisGenerator(seed=context.seed)
        candidates = generator.generate(context=context)
        result = engine.complete_cycle(context=context, candidates=candidates)
        memory.store_cycle(result)

        # Verify replay
        verification = memory.verify_replay(context.cycle_id)
        assert verification["verified"] is True, (
            f"Replay should verify: {verification}"
        )


class TestReplayConsistencyCalculation:
    """Tests for replay_consistency metric calculation."""

    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_empty_metrics_has_perfect_consistency(self, temp_storage):
        """No verifications should yield 1.0 consistency."""
        collector = CycleMetricsCollector(storage_path=temp_storage)
        metrics = collector.get_aggregate_metrics()
        assert metrics["replay_consistency"] == 1.0, (
            "Empty state should have 1.0 replay_consistency"
        )

    def test_all_verified_gives_perfect_consistency(self, temp_storage):
        """All successful verifications should yield 1.0 consistency."""
        collector = CycleMetricsCollector(storage_path=temp_storage)

        # Record several verified replays
        for i in range(5):
            collector.record_replay_verification(
                cycle_id=f"cycle_{i}",
                verified=True,
            )

        metrics = collector.get_aggregate_metrics()
        assert metrics["replay_consistency"] == 1.0, (
            "All verified should have 1.0 replay_consistency"
        )

    def test_mixed_verification_calculates_correctly(self, temp_storage):
        """Mixed verification results should calculate correctly."""
        collector = CycleMetricsCollector(storage_path=temp_storage)

        # Record 4 verified and 1 failed
        for i in range(4):
            collector.record_replay_verification(
                cycle_id=f"cycle_{i}",
                verified=True,
            )
        collector.record_replay_verification(
            cycle_id="cycle_4",
            verified=False,
            error="Trace hash mismatch",
        )

        metrics = collector.get_aggregate_metrics()
        assert metrics["replay_consistency"] == 0.8, (
            f"4/5 verified should yield 0.8, got {metrics['replay_consistency']}"
        )

    def test_all_failed_gives_zero_consistency(self, temp_storage):
        """All failed verifications should yield 0.0 consistency."""
        collector = CycleMetricsCollector(storage_path=temp_storage)

        for i in range(3):
            collector.record_replay_verification(
                cycle_id=f"cycle_{i}",
                verified=False,
                error="Verification failed",
            )

        metrics = collector.get_aggregate_metrics()
        assert metrics["replay_consistency"] == 0.0, (
            "All failed should have 0.0 replay_consistency"
        )


class TestCandidateDeterminism:
    """Tests for deterministic candidate generation."""

    def test_candidate_hash_is_deterministic(self):
        """Candidate hash should be deterministic."""
        candidate = InterpretationCandidate(
            origin_cycle="test_cycle",
            confidence=0.75,
            trace_reference="abc123",
            interpretation="Test interpretation",
            evidence_refs=["ref1"],
            alternatives=["alt1", "alt2"],
        )

        hash1 = candidate.compute_hash()
        hash2 = candidate.compute_hash()

        assert hash1 == hash2, "Same candidate should produce same hash"

    def test_different_candidates_have_different_hashes(self):
        """Different candidates should have different hashes."""
        c1 = InterpretationCandidate(
            interpretation="First interpretation",
            confidence=0.5,
        )
        c2 = InterpretationCandidate(
            interpretation="Second interpretation",
            confidence=0.5,
        )

        assert c1.compute_hash() != c2.compute_hash(), (
            "Different interpretations should have different hashes"
        )

    def test_id_and_timestamp_excluded_from_hash(self):
        """ID and timestamp should not affect hash."""
        c1 = InterpretationCandidate(
            id="unique-id-1",
            timestamp="2024-01-01T00:00:00",
            interpretation="Same",
            confidence=0.5,
        )
        c2 = InterpretationCandidate(
            id="unique-id-2",
            timestamp="2024-12-31T23:59:59",
            interpretation="Same",
            confidence=0.5,
        )

        assert c1.compute_hash() == c2.compute_hash(), (
            "Different ID/timestamp should not affect hash"
        )


class TestSandboxConstraints:
    """Tests for sandbox constraint enforcement."""

    def test_developmental_core_cannot_execute_actions(self):
        """Developmental core should only generate candidates, not execute."""
        engine = CycleEngine(seed=42)
        context = engine.start_cycle(trigger=CycleTrigger.IDLE)
        generator = HypothesisGenerator(seed=context.seed)
        candidates = generator.generate(context=context)

        # All candidates should be proposals only
        for candidate in candidates:
            assert hasattr(candidate, "origin_cycle"), (
                "Candidate must have origin_cycle"
            )
            assert candidate.origin_cycle == context.cycle_id, (
                "Candidate must reference source cycle"
            )

    def test_candidates_are_sandboxed(self):
        """All candidates must be marked as sandboxed proposals."""
        engine = CycleEngine(seed=42)
        context = engine.start_cycle(trigger=CycleTrigger.IDLE)
        generator = HypothesisGenerator(seed=context.seed)
        candidates = generator.generate(context=context)

        for candidate in candidates:
            # Candidates should have trace_reference for audit
            assert candidate.trace_reference, (
                "Candidate must have trace_reference"
            )
            # Candidates should have confidence (not final decision)
            assert 0.0 <= candidate.confidence <= 1.0, (
                "Confidence must be between 0 and 1"
            )

    def test_action_candidate_has_risk_assessment(self):
        """Action candidates must include risk assessment."""
        # Create an action candidate manually
        action = ActionCandidate(
            origin_cycle="test",
            action_type="observe",
            target="internal_state",
            expected_outcome="Gather information",
            risk_assessment={"disruption": 0.1, "resource_cost": 0.05},
        )

        assert action.risk_assessment is not None, (
            "Action candidate must have risk_assessment"
        )
        assert isinstance(action.risk_assessment, dict), (
            "Risk assessment must be a dict"
        )


class TestMetricsPersistence:
    """Tests for metrics file persistence."""

    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_metrics_written_to_file(self, temp_storage):
        """Metrics should be written to sandbox_metrics.json."""
        collector = CycleMetricsCollector(storage_path=temp_storage)

        # Record some cycles
        for i in range(3):
            collector.record_cycle(
                cycle_id=f"cycle_{i}",
                success=True,
                trigger="idle",
                candidates_generated=5,
                candidates_approved=3,
                trace_hash=f"hash_{i}",
            )

        # Check file exists
        metrics_file = Path(temp_storage) / "sandbox_metrics.json"
        assert metrics_file.exists(), "Metrics file should be created"

        # Verify content
        with open(metrics_file, "r") as f:
            data = json.load(f)

        assert data["total_cycles"] == 3, "Total cycles should be 3"
        assert data["successful_cycles"] == 3, "All should be successful"
        assert data["cycle_success_rate"] == 1.0, "Success rate should be 1.0"

    def test_metrics_schema_matches_spec(self, temp_storage):
        """Output schema must match specification."""
        collector = CycleMetricsCollector(storage_path=temp_storage)
        metrics = collector.get_aggregate_metrics()

        # Required fields from spec
        required_fields = [
            "total_cycles",
            "successful_cycles",
            "failed_cycles",
            "cycle_success_rate",
            "replay_consistency",
            "candidate_pool_size",
            "avg_candidates_per_cycle",
            "sandbox_violations",
        ]

        for field in required_fields:
            assert field in metrics, f"Missing required field: {field}"

        # Verify types
        assert isinstance(metrics["total_cycles"], int)
        assert isinstance(metrics["successful_cycles"], int)
        assert isinstance(metrics["failed_cycles"], int)
        assert isinstance(metrics["cycle_success_rate"], float)
        assert isinstance(metrics["replay_consistency"], float)
        assert isinstance(metrics["candidate_pool_size"], int)
        assert isinstance(metrics["avg_candidates_per_cycle"], float)
        assert isinstance(metrics["sandbox_violations"], int)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

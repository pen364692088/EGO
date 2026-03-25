"""
Tests for MVP12 Developmental Core Sandbox
"""

import pytest
import json
from datetime import datetime

from emotiond.developmental_core import (
    CycleEngine,
    CycleMemory,
    HypothesisGenerator,
    CandidateEvaluator,
    CandidateType,
    CycleTrigger,
    InterpretationCandidate,
    ActionCandidate,
    ExplanationCandidate,
    SelfModelHypothesis,
    CycleContext,
    CycleResult,
)


class TestModels:
    """Test candidate models."""

    def test_candidate_has_required_fields(self):
        """Candidate must have id, timestamp, origin_cycle, confidence, trace_reference."""
        candidate = InterpretationCandidate(
            origin_cycle="test-cycle-1",
            confidence=0.75,
            trace_reference="abc123",
        )
        assert candidate.id is not None
        assert candidate.timestamp is not None
        assert candidate.origin_cycle == "test-cycle-1"
        assert candidate.confidence == 0.75
        assert candidate.trace_reference == "abc123"

    def test_candidate_compute_hash(self):
        """Candidate hash must be deterministic."""
        c1 = ActionCandidate(
            origin_cycle="test",
            confidence=0.5,
            action_type="observe",
        )
        c2 = ActionCandidate(
            origin_cycle="test",
            confidence=0.5,
            action_type="observe",
        )
        # Same content should produce same hash (excluding id/timestamp)
        assert c1.compute_hash() == c2.compute_hash()

    def test_cycle_context_trace_hash(self):
        """CycleContext must compute trace_hash."""
        ctx = CycleContext(
            seed=12345,
            trigger=CycleTrigger.IDLE,
        )
        assert ctx.trace_hash is not None
        assert len(ctx.trace_hash) == 16

    def test_cycle_result_to_dict(self):
        """CycleResult must serialize to dict."""
        ctx = CycleContext(seed=1, trigger=CycleTrigger.IDLE)
        result = CycleResult(context=ctx, candidates=[])
        data = result.to_dict()
        assert "cycle_id" in data
        assert "seed" in data
        assert "trigger" in data
        assert "trace_hash" in data


class TestCycleEngine:
    """Test cycle engine."""

    def test_engine_initialization(self):
        """Engine must initialize with deterministic seed."""
        engine = CycleEngine(seed=42)
        assert engine.seed == 42
        assert engine.get_cycle_count() == 0

    def test_check_triggers_idle(self):
        """Engine must detect idle trigger."""
        engine = CycleEngine(idle_threshold=30.0)
        triggers = engine.check_triggers(idle_time=60.0)
        assert CycleTrigger.IDLE in triggers

    def test_check_triggers_tension(self):
        """Engine must detect tension trigger."""
        engine = CycleEngine(tension_threshold=0.5)
        tensions = [{"intensity": 0.8}]
        triggers = engine.check_triggers(unresolved_tensions=tensions)
        assert CycleTrigger.UNRESOLVED_TENSION in triggers

    def test_start_cycle(self):
        """Engine must start a cycle with context."""
        engine = CycleEngine(seed=42)
        ctx = engine.start_cycle(CycleTrigger.IDLE)
        assert ctx.cycle_id is not None
        assert ctx.trigger == CycleTrigger.IDLE
        assert engine.get_cycle_count() == 1

    def test_complete_cycle(self):
        """Engine must complete a cycle with candidates."""
        engine = CycleEngine(seed=42)
        ctx = engine.start_cycle(CycleTrigger.IDLE)
        candidates = [InterpretationCandidate(origin_cycle=ctx.cycle_id)]

        result = engine.complete_cycle(ctx, candidates)

        assert result.success is True
        assert len(result.candidates) == 1
        assert len(engine.get_pending_cycles()) == 0

    def test_cycle_determinism(self):
        """Cycles must be deterministic with same seed."""
        engine1 = CycleEngine(seed=12345)
        engine2 = CycleEngine(seed=12345)

        ctx1 = engine1.start_cycle(CycleTrigger.IDLE)
        ctx2 = engine2.start_cycle(CycleTrigger.IDLE)

        assert ctx1.seed == ctx2.seed


class TestHypothesisGenerator:
    """Test hypothesis generator."""

    def test_generate_idle_candidates(self):
        """Generator must produce candidates for idle trigger."""
        gen = HypothesisGenerator(seed=42)
        ctx = CycleContext(seed=1, trigger=CycleTrigger.IDLE)

        candidates = gen.generate(ctx)

        assert len(candidates) > 0
        for c in candidates:
            assert c.origin_cycle == ctx.cycle_id
            assert c.trace_reference == ctx.trace_hash

    def test_generate_tension_candidates(self):
        """Generator must produce candidates for tension trigger."""
        gen = HypothesisGenerator(seed=42)
        ctx = CycleContext(seed=1, trigger=CycleTrigger.UNRESOLVED_TENSION)

        candidates = gen.generate(ctx)

        assert len(candidates) > 0
        # Should include explanation and action candidates
        types = {c.candidate_type for c in candidates}
        assert CandidateType.EXPLANATION in types or CandidateType.ACTION in types

    def test_max_candidates_limit(self):
        """Generator must respect max_candidates limit."""
        gen = HypothesisGenerator(seed=42)
        ctx = CycleContext(seed=1, trigger=CycleTrigger.IDLE)

        candidates = gen.generate(ctx, max_candidates=3)

        assert len(candidates) <= 3


class TestCandidateEvaluator:
    """Test candidate evaluator."""

    def test_evaluate_candidate(self):
        """Evaluator must score candidates."""
        eval = CandidateEvaluator()
        candidate = ActionCandidate(
            origin_cycle="test",
            confidence=0.7,
            action_type="observe",
        )

        result = eval.evaluate(candidate)

        assert result.score >= 0
        assert result.score <= 1
        assert len(result.reasons) > 0

    def test_high_confidence_higher_score(self):
        """Higher confidence should produce higher score."""
        eval = CandidateEvaluator()

        c1 = ActionCandidate(origin_cycle="test", confidence=0.5, action_type="test")
        c2 = ActionCandidate(origin_cycle="test", confidence=0.9, action_type="test")

        r1 = eval.evaluate(c1)
        r2 = eval.evaluate(c2)

        assert r2.score > r1.score

    def test_batch_evaluation_sorted(self):
        """Batch evaluation must return sorted results."""
        eval = CandidateEvaluator()
        candidates = [
            ActionCandidate(origin_cycle="test", confidence=0.3, action_type="a"),
            ActionCandidate(origin_cycle="test", confidence=0.8, action_type="b"),
            ActionCandidate(origin_cycle="test", confidence=0.5, action_type="c"),
        ]

        results = eval.evaluate_batch(candidates)

        assert len(results) == 3
        # Should be sorted by score descending
        assert results[0].score >= results[1].score >= results[2].score


class TestCycleMemory:
    """Test cycle memory."""

    def test_store_cycle(self, tmp_path):
        """Memory must store cycle results."""
        memory = CycleMemory(storage_path=str(tmp_path))
        ctx = CycleContext(seed=1, trigger=CycleTrigger.IDLE)
        result = CycleResult(context=ctx, candidates=[])

        memory.store_cycle(result)

        assert memory.get_cycle_count() == 1
        assert memory.get_cycle(ctx.cycle_id) is not None

    def test_candidate_pool(self, tmp_path):
        """Memory must manage candidate pool."""
        memory = CycleMemory(storage_path=str(tmp_path))
        candidate = ActionCandidate(
            origin_cycle="test",
            confidence=0.8,
            action_type="test",
        )

        memory.add_to_pool(candidate, score=0.75)

        assert memory.get_pool_size() == 1
        pending = memory.get_pending_candidates()
        assert len(pending) == 1

    def test_replay_verification(self, tmp_path):
        """Memory must verify replay integrity."""
        memory = CycleMemory(storage_path=str(tmp_path))
        ctx = CycleContext(seed=1, trigger=CycleTrigger.IDLE)
        result = CycleResult(context=ctx, candidates=[])

        memory.store_cycle(result)

        verification = memory.verify_replay(ctx.cycle_id)
        assert verification["verified"] is True

    def test_persistence(self, tmp_path):
        """Memory must persist across instances."""
        memory1 = CycleMemory(storage_path=str(tmp_path))
        ctx = CycleContext(seed=1, trigger=CycleTrigger.IDLE)
        result = CycleResult(context=ctx, candidates=[])
        memory1.store_cycle(result)

        # Create new instance with same path
        memory2 = CycleMemory(storage_path=str(tmp_path))

        assert memory2.get_cycle_count() == 1
        assert memory2.get_cycle(ctx.cycle_id) is not None

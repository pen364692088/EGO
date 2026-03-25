"""
MVP12 Hypothesis Generator

Generates candidate hypotheses from cycle context.
All outputs are sandboxed candidates that must go through evaluation.
"""

from __future__ import annotations

import hashlib
import json
import random
from typing import Any, Dict, List, Optional

from .models import (
    Candidate,
    InterpretationCandidate,
    ActionCandidate,
    ExplanationCandidate,
    SelfModelHypothesis,
    CycleContext,
    CycleTrigger,
)


class HypothesisGenerator:
    """
    Generates candidate hypotheses from developmental cycle context.

    This is a sandboxed operation - outputs are proposals only and
    must go through Governor v2 for approval.
    """

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def generate(
        self,
        context: CycleContext,
        state_snapshot: Optional[Dict[str, Any]] = None,
        max_candidates: int = 5,
    ) -> List[Candidate]:
        """Generate candidates based on cycle context and state."""
        candidates = []
        snapshot = state_snapshot or context.state_snapshot

        # Generate based on trigger type
        if context.trigger == CycleTrigger.IDLE:
            candidates.extend(self._generate_idle_candidates(context, snapshot))
        elif context.trigger == CycleTrigger.UNRESOLVED_TENSION:
            candidates.extend(self._generate_tension_candidates(context, snapshot))
        elif context.trigger == CycleTrigger.LONG_TERM_GOAL:
            candidates.extend(self._generate_goal_candidates(context, snapshot))
        elif context.trigger == CycleTrigger.REPLAY_EVENT:
            candidates.extend(self._generate_replay_candidates(context, snapshot))

        # Sort by confidence and limit
        candidates.sort(key=lambda c: c.confidence, reverse=True)
        return candidates[:max_candidates]

    def _generate_idle_candidates(
        self,
        context: CycleContext,
        snapshot: Dict[str, Any],
    ) -> List[Candidate]:
        """Generate candidates during idle cycles."""
        candidates = []

        # Self-reflection hypothesis
        candidates.append(SelfModelHypothesis(
            origin_cycle=context.cycle_id,
            confidence=0.3 + self.rng.random() * 0.2,
            trace_reference=context.trace_hash,
            hypothesis="Current state is stable, no immediate action required",
            test_predictions=["State remains stable for next cycle"],
            disconfirmation_criteria=["Significant state change detected"],
        ))

        # Exploration interpretation
        candidates.append(InterpretationCandidate(
            origin_cycle=context.cycle_id,
            confidence=0.4 + self.rng.random() * 0.2,
            trace_reference=context.trace_hash,
            interpretation="Idle period may indicate opportunity for reflection",
            evidence_refs=[],
            alternatives=["System is waiting for input", "Energy conservation mode"],
        ))

        return candidates

    def _generate_tension_candidates(
        self,
        context: CycleContext,
        snapshot: Dict[str, Any],
    ) -> List[Candidate]:
        """Generate candidates for unresolved tensions."""
        candidates = []

        # Tension explanation
        candidates.append(ExplanationCandidate(
            origin_cycle=context.cycle_id,
            confidence=0.5 + self.rng.random() * 0.3,
            trace_reference=context.trace_hash,
            explanation="Unresolved tension detected in system state",
            supporting_facts=["Tension exceeds threshold"],
            counter_evidence=[],
        ))

        # Resolution action
        candidates.append(ActionCandidate(
            origin_cycle=context.cycle_id,
            confidence=0.4 + self.rng.random() * 0.2,
            trace_reference=context.trace_hash,
            action_type="observe",
            target="internal_state",
            expected_outcome="Gather more information about tension source",
            risk_assessment={"disruption": 0.1},
        ))

        return candidates

    def _generate_goal_candidates(
        self,
        context: CycleContext,
        snapshot: Dict[str, Any],
    ) -> List[Candidate]:
        """Generate candidates for long-term goal pressure."""
        candidates = []

        # Goal pursuit action
        candidates.append(ActionCandidate(
            origin_cycle=context.cycle_id,
            confidence=0.6 + self.rng.random() * 0.2,
            trace_reference=context.trace_hash,
            action_type="approach",
            target="long_term_goal",
            expected_outcome="Progress toward goal",
            risk_assessment={"resource_cost": 0.2, "disruption": 0.1},
        ))

        return candidates

    def _generate_replay_candidates(
        self,
        context: CycleContext,
        snapshot: Dict[str, Any],
    ) -> List[Candidate]:
        """Generate candidates from replay events."""
        candidates = []

        # Replay interpretation
        candidates.append(InterpretationCandidate(
            origin_cycle=context.cycle_id,
            confidence=0.5,
            trace_reference=context.trace_hash,
            interpretation="Replaying past cycle for verification",
            evidence_refs=[],
            alternatives=[],
        ))

        return candidates

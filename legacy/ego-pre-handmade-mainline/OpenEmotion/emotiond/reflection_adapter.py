"""
MVP15 bounded reflection mainline adapter.

Purpose:
- expose a governed, replayable reflection/counterfactual summary to the
  current plan/decision mainline
- keep proposal discipline explicit
- avoid granting direct behavioral authority to reflection outputs
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from emotiond.hot_self_model import get_hot_self_model
from emotiond.reflection_engine import get_reflection_engine
from emotiond.self_counterfactual import get_counterfactual_model


ENABLE_MVP15_MAINLINE_GUIDANCE = (
    os.environ.get("ENABLE_MVP15_MAINLINE_GUIDANCE", "true").lower() == "true"
)


class ReflectionAdapter:
    """Bounded consumer surface for MVP15 formal owners."""

    _instance: Optional["ReflectionAdapter"] = None

    def __init__(self, enable_guidance: bool = True):
        self.enable_guidance = enable_guidance and ENABLE_MVP15_MAINLINE_GUIDANCE
        self._engine = get_reflection_engine() if self.enable_guidance else None
        self._hot = get_hot_self_model() if self.enable_guidance else None
        self._counterfactual = (
            get_counterfactual_model(hot_self_model=self._hot)
            if self.enable_guidance
            else None
        )

    @classmethod
    def get_instance(cls, enable_guidance: bool = True) -> "ReflectionAdapter":
        if cls._instance is None:
            cls._instance = cls(enable_guidance=enable_guidance)
        return cls._instance

    def build_guidance(
        self,
        *,
        target: str,
        target_id: str,
        state: Any,
        relationship: Dict[str, float],
        source: str,
    ) -> Optional[Dict[str, Any]]:
        if not self.enable_guidance or not self._engine or not self._counterfactual:
            return None

        runtime_state = {
            "bodily": {
                "energy": float(getattr(state, "energy", 0.7)),
                "social_safety": float(getattr(state, "social_safety", 0.6)),
            },
            "cognitive": {
                "uncertainty": float(getattr(state, "uncertainty", 0.5)),
                "confidence": max(
                    0.0,
                    min(1.0, 1.0 - float(getattr(state, "uncertainty", 0.5))),
                ),
            },
            "hot": {
                "control_estimate": float(getattr(self._hot.state, "control_estimate", 0.5)),
                "conflict_level": float(getattr(self._hot.state, "conflict_level", 0.0)),
            },
            "relational": {
                "bond": float(relationship.get("bond", 0.5)),
                "trust": float(relationship.get("trust", 0.5)),
            },
            "homeostasis": {
                "safety": float(getattr(state, "social_safety", 0.6)),
                "certainty": max(
                    0.0,
                    min(1.0, 1.0 - float(getattr(state, "uncertainty", 0.5))),
                ),
            },
        }

        strategy = self._counterfactual.select_strategy(runtime_state)
        recent_jobs = self._engine.state.history.get_recent_jobs(1)
        latest_job = recent_jobs[-1] if recent_jobs else None
        pending_proposals = self._engine.state.get_pending_proposals()

        return {
            "schema_version": "mvp15.mainline_guidance.v1",
            "source": source,
            "target": target,
            "target_id": target_id,
            "proposal_discipline": "proposal_only",
            "writeback_surface": "plan_and_decision_explanation_only",
            "behavioral_authority": "none",
            "reflection": {
                "summary": self._engine.state.get_summary(),
                "latest_job": (
                    {
                        "job_id": latest_job.job_id,
                        "reflection_type": latest_job.reflection_type.value,
                        "status": latest_job.status,
                        "confidence": latest_job.confidence,
                        "proposal_count": len(latest_job.proposals),
                    }
                    if latest_job is not None
                    else None
                ),
                "pending_proposals": len(pending_proposals),
            },
            "counterfactual": {
                "strategy_source": strategy.get("source", "adaptive"),
                "mode": strategy.get("mode", "normal"),
                "risk_tolerance": strategy.get("risk_tolerance"),
                "info_seeking_weight": strategy.get("info_seeking_weight"),
                "preferred_actions": strategy.get("preferred_actions", []),
                "avoided_actions": strategy.get("avoided_actions", []),
                "matched_counterfactual": bool(strategy.get("match")),
            },
        }


def get_reflection_adapter(enable_guidance: bool = True) -> ReflectionAdapter:
    return ReflectionAdapter.get_instance(enable_guidance=enable_guidance)


def reset_reflection_adapter() -> None:
    ReflectionAdapter._instance = None

"""
MVP15: Reflective Self / Counterfactual Self

Structured self-reflection and counterfactual evaluation.
"""
from .schema import (
    ReflectionState,
    ReflectionJob,
    ReflectionType,
    CounterfactualRun,
    DiagnosisRecord,
    ReflectionProposal,
)
from .engine import ReflectionEngine, get_reflection_engine, reset_reflection_engine

__all__ = [
    "ReflectionState",
    "ReflectionJob",
    "ReflectionType",
    "CounterfactualRun",
    "DiagnosisRecord",
    "ReflectionProposal",
    "ReflectionEngine",
    "get_reflection_engine",
    "reset_reflection_engine",
]

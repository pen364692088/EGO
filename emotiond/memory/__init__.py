"""MVP-10 Memory Module - Episodic, Narrative, and Commitments memory systems.

This package provides the new MVP-10 memory components:
- EpisodicEvent, EpisodicMemory - Event storage and retrieval
- NarrativeEntry, NarrativeMemory - Versioned narratives with evidence
- Commitment, CommitmentsLedger - Commitment tracking

For backward compatibility, the legacy MemorySystem is also available.
"""
from emotiond.memory.episodic import EpisodicEvent, EpisodicMemory
from emotiond.memory.narrative import NarrativeEntry, NarrativeMemory
from emotiond.memory.commitments import Commitment, CommitmentsLedger

# Import legacy memory system for backward compatibility
from emotiond.memory_legacy import (
    MemorySystem,
    memory_system,
    initialize_memory_system,
)

__all__ = [
    # MVP-10 components
    "EpisodicEvent",
    "EpisodicMemory",
    "NarrativeEntry",
    "NarrativeMemory",
    "Commitment",
    "CommitmentsLedger",
    # Legacy compatibility
    "MemorySystem",
    "memory_system",
    "initialize_memory_system",
]

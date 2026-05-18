"""
Quality Signal Provenance.

Complete traceability for quality signal computation.
Capability Owner: OpenEmotion

v6g: Quality Signal Provenance + Promotion Review

Ensures quality signal evidence chain is complete:
- signal_value
- source
- sample_count_used
- computation_method
- explanation

All must be consistent for promotion decisions.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class SignalSource(str, Enum):
    """Source of quality signal computation."""
    SHADOW_COMPARE = "shadow_compare"
    DOWNSTREAM_PROXY = "downstream_proxy"
    OFFLINE_REPLAY = "offline_replay"
    PLACEHOLDER = "placeholder"


class ComputationMethod(str, Enum):
    """Method used for signal computation."""
    TOPK_SHADOW_COMPARE_WIN_RATE = "topk_shadow_compare_win_rate"
    TOPK_OVERlap_RATE = "topk_overlap_rate"
    ACCEPTANCE_RATE_WEIGHTED = "acceptance_rate_weighted"
    HIT_RATE_GAIN = "hit_rate_gain"
    PLACEHOLDER = "placeholder"


@dataclass
class QualitySignalProvenance:
    """Complete provenance for a quality signal.
    
    MANDATORY: All fields must be consistent.
    - If sample_count_used > 0, explanation must match
    - If source = shadow_compare, baseline/candidate providers must be set
    - If interpretable = true, all provenance fields must be present
    """
    signal_value: float
    source: SignalSource
    interpretable: bool
    confidence: float
    
    # Provenance fields (mandatory for interpretable signals)
    sample_count_used: int = 0
    sample_batch_ref: str = ""
    computation_method: ComputationMethod = ComputationMethod.PLACEHOLDER
    baseline_provider: str = ""
    candidate_provider: str = ""
    raw_compare_count: int = 0
    
    # Explanation (must be consistent with sample_count_used)
    explanation: str = ""
    
    # Timestamps
    computed_at: float = field(default_factory=time.time)
    sample_time_range: Optional[Dict[str, float]] = None
    
    # Raw data references
    sample_ids: List[str] = field(default_factory=list)
    
    def validate_consistency(self) -> List[str]:
        """Validate that provenance is consistent.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Rule 1: interpretable + sample_count_used = 0 is invalid
        if self.interpretable and self.sample_count_used == 0:
            errors.append(
                f"Signal marked interpretable but sample_count_used=0"
            )
        
        # Rule 2: explanation must match sample_count_used
        if self.sample_count_used > 0:
            expected_pattern = f"{self.sample_count_used}"
            if expected_pattern not in self.explanation:
                errors.append(
                    f"Explanation '{self.explanation}' inconsistent with sample_count_used={self.sample_count_used}"
                )
        
        # Rule 3: source=shadow_compare requires providers
        if self.source == SignalSource.SHADOW_COMPARE:
            if not self.baseline_provider or not self.candidate_provider:
                errors.append(
                    f"shadow_compare requires baseline_provider and candidate_provider"
                )
        
        # Rule 4: signal_value > 0 requires computation_method
        if self.signal_value > 0 and self.computation_method == ComputationMethod.PLACEHOLDER:
            errors.append(
                f"signal_value > 0 requires non-placeholder computation_method"
            )
        
        # Rule 5: raw_compare_count should match sample_count_used
        if self.raw_compare_count > 0 and self.raw_compare_count != self.sample_count_used:
            errors.append(
                f"raw_compare_count ({self.raw_compare_count}) != sample_count_used ({self.sample_count_used})"
            )
        
        return errors
    
    def is_valid_for_promotion(self) -> bool:
        """Check if signal is valid for promotion decision."""
        if not self.interpretable:
            return False
        
        if self.sample_count_used == 0:
            return False
        
        errors = self.validate_consistency()
        return len(errors) == 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_value": round(self.signal_value, 4),
            "source": self.source.value,
            "interpretable": self.interpretable,
            "confidence": round(self.confidence, 4),
            "sample_count_used": self.sample_count_used,
            "sample_batch_ref": self.sample_batch_ref,
            "computation_method": self.computation_method.value,
            "baseline_provider": self.baseline_provider,
            "candidate_provider": self.candidate_provider,
            "raw_compare_count": self.raw_compare_count,
            "explanation": self.explanation,
            "computed_at": self.computed_at,
            "sample_time_range": self.sample_time_range,
            "sample_ids": self.sample_ids[:10] if self.sample_ids else [],  # First 10 only
            "validation_errors": self.validate_consistency(),
            "valid_for_promotion": self.is_valid_for_promotion(),
        }


class QualitySignalProvenanceBuilder:
    """Builder for quality signal provenance.
    
    Ensures all required fields are set before creating provenance.
    """
    
    def __init__(self):
        self._signal_value: float = 0.0
        self._source: SignalSource = SignalSource.PLACEHOLDER
        self._interpretable: bool = False
        self._confidence: float = 0.0
        self._sample_count_used: int = 0
        self._sample_batch_ref: str = ""
        self._computation_method: ComputationMethod = ComputationMethod.PLACEHOLDER
        self._baseline_provider: str = ""
        self._candidate_provider: str = ""
        self._raw_compare_count: int = 0
        self._explanation: str = ""
        self._sample_ids: List[str] = []
    
    def with_shadow_compare(
        self,
        signal_value: float,
        sample_count: int,
        baseline_provider: str = "tfidf",
        candidate_provider: str = "ollama",
        batch_ref: str = "",
        sample_ids: Optional[List[str]] = None,
    ) -> "QualitySignalProvenanceBuilder":
        """Build from shadow comparison.
        
        Args:
            signal_value: Computed signal value
            sample_count: Number of samples used
            baseline_provider: Baseline provider (default: tfidf)
            candidate_provider: Candidate provider (default: ollama)
            batch_ref: Batch reference
            sample_ids: List of sample IDs
        """
        self._signal_value = signal_value
        self._source = SignalSource.SHADOW_COMPARE
        self._interpretable = True
        self._confidence = min(0.9, 0.5 + sample_count * 0.01)
        self._sample_count_used = sample_count
        self._raw_compare_count = sample_count
        self._baseline_provider = baseline_provider
        self._candidate_provider = candidate_provider
        self._computation_method = ComputationMethod.TOPK_SHADOW_COMPARE_WIN_RATE
        self._sample_batch_ref = batch_ref
        self._sample_ids = sample_ids or []
        self._explanation = f"Computed from {sample_count} shadow-compare samples (baseline={baseline_provider}, candidate={candidate_provider})"
        return self
    
    def with_downstream_proxy(
        self,
        signal_value: float,
        sample_count: int,
        acceptance_rate: float,
        rerank_consistency: float,
        batch_ref: str = "",
    ) -> "QualitySignalProvenanceBuilder":
        """Build from downstream proxy."""
        self._signal_value = signal_value
        self._source = SignalSource.DOWNSTREAM_PROXY
        self._interpretable = True
        self._confidence = min(0.8, 0.4 + sample_count * 0.01)
        self._sample_count_used = sample_count
        self._computation_method = ComputationMethod.ACCEPTANCE_RATE_WEIGHTED
        self._sample_batch_ref = batch_ref
        self._explanation = f"Computed from {sample_count} downstream proxy samples (acceptance={acceptance_rate:.1%}, rerank={rerank_consistency:.1%})"
        return self
    
    def with_offline_replay(
        self,
        signal_value: float,
        sample_count: int,
        hit_at_1: float,
        hit_at_3: float,
        batch_ref: str = "",
    ) -> "QualitySignalProvenanceBuilder":
        """Build from offline replay."""
        self._signal_value = signal_value
        self._source = SignalSource.OFFLINE_REPLAY
        self._interpretable = True
        self._confidence = min(0.95, 0.6 + sample_count * 0.01)
        self._sample_count_used = sample_count
        self._raw_compare_count = sample_count
        self._computation_method = ComputationMethod.HIT_RATE_GAIN
        self._sample_batch_ref = batch_ref
        self._explanation = f"Computed from {sample_count} offline replay samples (hit@1={hit_at_1:.1%}, hit@3={hit_at_3:.1%})"
        return self
    
    def with_placeholder(
        self,
        reason: str,
    ) -> "QualitySignalProvenanceBuilder":
        """Build placeholder signal (not interpretable)."""
        self._signal_value = 0.0
        self._source = SignalSource.PLACEHOLDER
        self._interpretable = False
        self._confidence = 0.0
        self._sample_count_used = 0
        self._computation_method = ComputationMethod.PLACEHOLDER
        self._explanation = f"Placeholder: {reason}"
        return self
    
    def build(self) -> QualitySignalProvenance:
        """Build the provenance object."""
        return QualitySignalProvenance(
            signal_value=self._signal_value,
            source=self._source,
            interpretable=self._interpretable,
            confidence=self._confidence,
            sample_count_used=self._sample_count_used,
            sample_batch_ref=self._sample_batch_ref,
            computation_method=self._computation_method,
            baseline_provider=self._baseline_provider,
            candidate_provider=self._candidate_provider,
            raw_compare_count=self._raw_compare_count,
            explanation=self._explanation,
            sample_ids=self._sample_ids,
        )


def compute_shadow_compare_provenance(
    ollama_top_k_results: List[List[Any]],
    tfidf_top_k_results: List[List[Any]],
    k: int = 5,
    batch_ref: str = "",
    sample_ids: Optional[List[str]] = None,
) -> QualitySignalProvenance:
    """Compute quality signal with full provenance from shadow comparison.
    
    Args:
        ollama_top_k_results: List of top-k results from Ollama (one per sample)
        tfidf_top_k_results: List of top-k results from TF-IDF (one per sample)
        k: Number of results to compare
        batch_ref: Batch reference
        sample_ids: List of sample IDs
        
    Returns:
        QualitySignalProvenance with complete traceability
    """
    sample_count = len(ollama_top_k_results)
    
    if sample_count == 0:
        return QualitySignalProvenanceBuilder().with_placeholder(
            "No shadow comparison samples available"
        ).build()
    
    # Compute average overlap and signal
    total_signal = 0.0
    for ollama_top_k, tfidf_top_k in zip(ollama_top_k_results, tfidf_top_k_results):
        if not ollama_top_k or not tfidf_top_k:
            continue
        
        ollama_set = set(str(x) for x in ollama_top_k[:k])
        tfidf_set = set(str(x) for x in tfidf_top_k[:k])
        
        overlap = len(ollama_set & tfidf_set)
        overlap_rate = overlap / min(k, len(ollama_set), len(tfidf_set))
        
        # Signal = 1 - overlap (lower overlap = more value from Ollama)
        total_signal += (1.0 - overlap_rate)
    
    avg_signal = total_signal / sample_count if sample_count > 0 else 0.0
    
    return QualitySignalProvenanceBuilder().with_shadow_compare(
        signal_value=avg_signal,
        sample_count=sample_count,
        baseline_provider="tfidf",
        candidate_provider="ollama",
        batch_ref=batch_ref,
        sample_ids=sample_ids,
    ).build()

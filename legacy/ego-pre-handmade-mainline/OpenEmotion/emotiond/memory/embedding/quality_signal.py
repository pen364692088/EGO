"""
Quality Signal Calculator.

Computes quality gain signals for retrieval mode decisions.
Capability Owner: OpenEmotion

v6f: Candidate Scenario Pilot + Quality Signal Calibration

Quality Signal Sources:
1. shadow_compare: Compare Ollama vs TF-IDF top-k overlap
2. downstream_proxy: Use acceptance/rerank consistency as proxy
3. offline_replay: Labeled sample evaluation
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class QualitySignalSource(str, Enum):
    """Source of quality signal."""
    SHADOW_COMPARE = "shadow_compare"
    DOWNSTREAM_PROXY = "downstream_proxy"
    OFFLINE_REPLAY = "offline_replay"
    PLACEHOLDER = "placeholder"  # Not computed, default value
    UNKNOWN = "unknown"


@dataclass
class QualitySignalResult:
    """Result of quality signal computation."""
    signal_value: float
    source: QualitySignalSource
    interpretable: bool  # Can this signal be used for decisions?
    confidence: float  # 0.0 - 1.0
    explanation: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_value": round(self.signal_value, 4),
            "source": self.source.value,
            "interpretable": self.interpretable,
            "confidence": round(self.confidence, 4),
            "explanation": self.explanation,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class QualitySignalCalculator:
    """Calculates quality gain signals.
    
    Capability Owner: OpenEmotion
    
    Provides multiple methods to compute quality signals:
    - Shadow comparison: Direct comparison between providers
    - Downstream proxy: Indirect quality indicators
    - Offline replay: Ground truth evaluation
    """
    
    # v6a baseline results (for reference)
    V6A_BASELINE = {
        "tfidf_hit_at_1": 0.4,
        "ollama_hit_at_1": 0.6,
        "tfidf_hit_at_3": 0.8,
        "ollama_hit_at_3": 1.0,
        "quality_gain": 0.2,  # 20% improvement
    }
    
    def __init__(self):
        self.shadow_comparisons: List[Dict[str, Any]] = []
        self.downstream_proxies: List[Dict[str, Any]] = []
    
    def compute_shadow_compare_signal(
        self,
        ollama_top_k: List[Any],
        tfidf_top_k: List[Any],
        k: int = 5,
    ) -> QualitySignalResult:
        """Compute quality signal from shadow comparison.
        
        Compares top-k results from Ollama vs TF-IDF.
        Higher overlap = signal is less valuable.
        Lower overlap = Ollama provides different (potentially better) results.
        
        Args:
            ollama_top_k: Top-k results from Ollama
            tfidf_top_k: Top-k results from TF-IDF
            k: Number of results to compare
            
        Returns:
            QualitySignalResult with computed signal
        """
        if not ollama_top_k or not tfidf_top_k:
            return QualitySignalResult(
                signal_value=0.0,
                source=QualitySignalSource.SHADOW_COMPARE,
                interpretable=False,
                confidence=0.0,
                explanation="No results to compare",
                details={"error": "empty_results"},
            )
        
        # Compute overlap
        ollama_set = set(str(x) for x in ollama_top_k[:k])
        tfidf_set = set(str(x) for x in tfidf_top_k[:k])
        
        overlap = len(ollama_set & tfidf_set)
        overlap_rate = overlap / min(k, len(ollama_set), len(tfidf_set))
        
        # Quality signal: lower overlap = more value from Ollama
        # But we need a positive signal to indicate improvement
        # Use inverse of overlap as proxy for "new value added"
        signal_value = 1.0 - overlap_rate
        
        # Record comparison
        comparison = {
            "timestamp": time.time(),
            "overlap": overlap,
            "overlap_rate": overlap_rate,
            "signal_value": signal_value,
        }
        self.shadow_comparisons.append(comparison)
        
        return QualitySignalResult(
            signal_value=signal_value,
            source=QualitySignalSource.SHADOW_COMPARE,
            interpretable=True,
            confidence=0.7,  # Shadow compare is moderately confident
            explanation=f"Shadow compare: {overlap}/{k} overlap ({overlap_rate:.1%}), signal={signal_value:.4f}",
            details={
                "overlap": overlap,
                "overlap_rate": overlap_rate,
                "k": k,
            },
        )
    
    def compute_downstream_proxy_signal(
        self,
        acceptance_rate: float,
        rerank_consistency: float,
        feedback_positive_rate: Optional[float] = None,
    ) -> QualitySignalResult:
        """Compute quality signal from downstream proxies.
        
        Uses indirect indicators:
        - Acceptance rate: How often results are accepted/used
        - Rerank consistency: Agreement with reranker
        - Feedback positive rate: User feedback (if available)
        
        Args:
            acceptance_rate: Rate at which results are accepted (0.0-1.0)
            rerank_consistency: Agreement with reranker (0.0-1.0)
            feedback_positive_rate: Positive feedback rate (optional)
            
        Returns:
            QualitySignalResult with computed signal
        """
        # Weighted combination
        weights = {
            "acceptance": 0.4,
            "rerank": 0.4,
            "feedback": 0.2,
        }
        
        signal_value = (
            acceptance_rate * weights["acceptance"] +
            rerank_consistency * weights["rerank"] +
            (feedback_positive_rate or 0.5) * weights["feedback"]
        )
        
        # Adjust: signal should represent improvement over baseline
        # Use v6a baseline as reference
        baseline_signal = self.V6A_BASELINE["quality_gain"]
        adjusted_signal = signal_value - baseline_signal * 0.5  # Conservative adjustment
        
        # Record proxy
        proxy = {
            "timestamp": time.time(),
            "acceptance_rate": acceptance_rate,
            "rerank_consistency": rerank_consistency,
            "feedback_positive_rate": feedback_positive_rate,
            "signal_value": adjusted_signal,
        }
        self.downstream_proxies.append(proxy)
        
        confidence = 0.6 if feedback_positive_rate is None else 0.8
        
        return QualitySignalResult(
            signal_value=max(0.0, adjusted_signal),
            source=QualitySignalSource.DOWNSTREAM_PROXY,
            interpretable=True,
            confidence=confidence,
            explanation=f"Downstream proxy: acceptance={acceptance_rate:.1%}, rerank={rerank_consistency:.1%}",
            details={
                "acceptance_rate": acceptance_rate,
                "rerank_consistency": rerank_consistency,
                "feedback_positive_rate": feedback_positive_rate,
            },
        )
    
    def compute_offline_replay_signal(
        self,
        hit_at_1: float,
        hit_at_3: float,
        baseline_hit_at_1: float = 0.4,
        baseline_hit_at_3: float = 0.8,
    ) -> QualitySignalResult:
        """Compute quality signal from offline replay.
        
        Uses labeled samples to compute actual retrieval quality.
        
        Args:
            hit_at_1: Hit@1 rate on labeled samples
            hit_at_3: Hit@3 rate on labeled samples
            baseline_hit_at_1: Baseline Hit@1 (default: TF-IDF from v6a)
            baseline_hit_at_3: Baseline Hit@3 (default: TF-IDF from v6a)
            
        Returns:
            QualitySignalResult with computed signal
        """
        # Quality gain = improvement over baseline
        hit_1_gain = hit_at_1 - baseline_hit_at_1
        hit_3_gain = hit_at_3 - baseline_hit_at_3
        
        # Combined signal (weighted average)
        signal_value = (hit_1_gain + hit_3_gain) / 2
        
        # Confidence based on how much we improved
        confidence = min(1.0, abs(signal_value) * 5)  # Scale up confidence
        
        return QualitySignalResult(
            signal_value=signal_value,
            source=QualitySignalSource.OFFLINE_REPLAY,
            interpretable=True,
            confidence=confidence,
            explanation=f"Offline replay: hit@1={hit_at_1:.1%} (gain={hit_1_gain:+.1%}), hit@3={hit_at_3:.1%} (gain={hit_3_gain:+.1%})",
            details={
                "hit_at_1": hit_at_1,
                "hit_at_3": hit_at_3,
                "baseline_hit_at_1": baseline_hit_at_1,
                "baseline_hit_at_3": baseline_hit_at_3,
                "hit_1_gain": hit_1_gain,
                "hit_3_gain": hit_3_gain,
            },
        )
    
    def compute_placeholder_signal(
        self,
        default_value: float = 0.0,
        reason: str = "Signal not computed",
    ) -> QualitySignalResult:
        """Return placeholder signal when computation is not possible.
        
        IMPORTANT: Placeholder signals are NOT interpretable
        and should not be used for promotion decisions.
        
        Args:
            default_value: Default signal value
            reason: Why signal could not be computed
            
        Returns:
            QualitySignalResult marked as not interpretable
        """
        return QualitySignalResult(
            signal_value=default_value,
            source=QualitySignalSource.PLACEHOLDER,
            interpretable=False,
            confidence=0.0,
            explanation=f"Placeholder signal: {reason}",
            details={"reason": reason},
        )
    
    def get_aggregate_signal(self) -> QualitySignalResult:
        """Get aggregate quality signal from all sources."""
        signals = []
        
        # Aggregate shadow comparisons
        if self.shadow_comparisons:
            avg_signal = sum(s["signal_value"] for s in self.shadow_comparisons) / len(self.shadow_comparisons)
            signals.append(("shadow", avg_signal, len(self.shadow_comparisons)))
        
        # Aggregate downstream proxies
        if self.downstream_proxies:
            avg_signal = sum(s["signal_value"] for s in self.downstream_proxies) / len(self.downstream_proxies)
            signals.append(("proxy", avg_signal, len(self.downstream_proxies)))
        
        if not signals:
            return self.compute_placeholder_signal(reason="No signal samples collected")
        
        # Weighted average by sample count
        total_weight = sum(count for _, _, count in signals)
        weighted_signal = sum(
            signal * count / total_weight
            for _, signal, count in signals
        )
        
        # Determine best source
        best_source = max(signals, key=lambda x: x[2])[0]
        source_map = {
            "shadow": QualitySignalSource.SHADOW_COMPARE,
            "proxy": QualitySignalSource.DOWNSTREAM_PROXY,
        }
        
        return QualitySignalResult(
            signal_value=weighted_signal,
            source=source_map.get(best_source, QualitySignalSource.UNKNOWN),
            interpretable=True,
            confidence=min(0.9, 0.5 + total_weight * 0.01),  # Confidence grows with samples
            explanation=f"Aggregate signal from {len(signals)} sources, {total_weight} samples",
            details={
                "sources": {s[0]: {"signal": s[1], "count": s[2]} for s in signals},
            },
        )
    
    def explain_quality_signal(self, result: QualitySignalResult) -> str:
        """Generate human-readable explanation of quality signal.
        
        Args:
            result: QualitySignalResult to explain
            
        Returns:
            Explanation string
        """
        if not result.interpretable:
            return f"⚠️ Quality signal ({result.signal_value:.4f}) is NOT interpretable: {result.explanation}"
        
        if result.signal_value > 0.1:
            assessment = "✅ Strong positive signal"
        elif result.signal_value > 0:
            assessment = "✅ Positive signal"
        elif result.signal_value == 0:
            assessment = "⚖️ Neutral signal"
        else:
            assessment = "⚠️ Negative signal"
        
        return (
            f"{assessment} ({result.signal_value:.4f})\n"
            f"Source: {result.source.value}\n"
            f"Confidence: {result.confidence:.0%}\n"
            f"Details: {result.explanation}"
        )


def compute_quality_gain_signal(
    source: str = "placeholder",
    **kwargs,
) -> QualitySignalResult:
    """Convenience function to compute quality signal.
    
    Args:
        source: Signal source ("shadow", "proxy", "offline", "placeholder")
        **kwargs: Source-specific parameters
        
    Returns:
        QualitySignalResult
    """
    calculator = QualitySignalCalculator()
    
    if source == "shadow":
        return calculator.compute_shadow_compare_signal(
            ollama_top_k=kwargs.get("ollama_top_k", []),
            tfidf_top_k=kwargs.get("tfidf_top_k", []),
            k=kwargs.get("k", 5),
        )
    elif source == "proxy":
        return calculator.compute_downstream_proxy_signal(
            acceptance_rate=kwargs.get("acceptance_rate", 0.5),
            rerank_consistency=kwargs.get("rerank_consistency", 0.5),
            feedback_positive_rate=kwargs.get("feedback_positive_rate"),
        )
    elif source == "offline":
        return calculator.compute_offline_replay_signal(
            hit_at_1=kwargs.get("hit_at_1", 0.5),
            hit_at_3=kwargs.get("hit_at_3", 0.7),
        )
    else:
        return calculator.compute_placeholder_signal(
            default_value=kwargs.get("default_value", 0.0),
            reason=kwargs.get("reason", "Signal not computed"),
        )

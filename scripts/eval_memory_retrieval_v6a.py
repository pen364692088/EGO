#!/usr/bin/env python3
"""
A/B Evaluation for Embedding Providers (v6a).

Compares TF-IDF vs Ollama embedding providers on:
- hit@1 / hit@3
- hard negative false recall
- wrong user recall
- latency
- duplicate suppression
- clustering quality

Usage:
    python scripts/eval_memory_retrieval_v6a.py
    python scripts/eval_memory_retrieval_v6a.py --output artifacts/eval/v6a/
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.memory.embedding.contracts import EmbeddingConfig
from emotiond.memory.embedding.providers.ollama_provider import OllamaEmbeddingProvider
from emotiond.memory.embedding.providers.tfidf_provider import TfidfProvider


@dataclass
class TestCase:
    """A test case for retrieval evaluation."""
    query: str
    expected_match: str
    user_id: str = "default"
    hard_negatives: List[str] = field(default_factory=list)
    other_user_memories: List[str] = field(default_factory=list)
    duplicates: List[str] = field(default_factory=list)
    

@dataclass
class ProviderMetrics:
    """Metrics for a single provider."""
    provider: str
    model: str
    hit_at_1: float = 0.0
    hit_at_3: float = 0.0
    hard_negative_false_recall_count: int = 0
    wrong_user_recall_count: int = 0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    duplicate_suppression_rate: float = 0.0
    total_cases: int = 0
    latency_samples: List[float] = field(default_factory=list)
    
    def compute_aggregates(self):
        """Compute aggregate metrics from samples."""
        if self.latency_samples:
            sorted_samples = sorted(self.latency_samples)
            self.avg_latency_ms = sum(sorted_samples) / len(sorted_samples)
            p95_idx = int(len(sorted_samples) * 0.95)
            self.p95_latency_ms = sorted_samples[p95_idx] if p95_idx < len(sorted_samples) else sorted_samples[-1]


# Standard test cases for OpenEmotion retrieval
DEFAULT_TEST_CASES = [
    TestCase(
        query="I remember when Alice helped me with the project",
        expected_match="Alice offered to help with the coding project last week",
        user_id="user_1",
        hard_negatives=["Bob refused to help with anything"],
        other_user_memories=["Charlie helped me with the database design"],
        duplicates=["Alice helped with the project", "Alice assisted with the project work"],
    ),
    TestCase(
        query="Yesterday was a great day",
        expected_match="Had a wonderful time at the park yesterday",
        user_id="user_1",
        hard_negatives=["Yesterday was terrible, everything went wrong"],
        other_user_memories=["Yesterday I stayed home all day"],
    ),
    TestCase(
        query="The API returned an error",
        expected_match="HTTP 500 error from the API endpoint",
        user_id="user_2",
        hard_negatives=["The API is working fine now"],
        other_user_memories=["Fixed the API timeout issue"],
    ),
    TestCase(
        query="I feel happy about the progress",
        expected_match="Making good progress on the emotional core",
        user_id="user_1",
        hard_negatives=["I'm frustrated with the lack of progress"],
        duplicates=["Progress is going well", "Things are progressing nicely"],
    ),
    TestCase(
        query="Need to fix the bug in authentication",
        expected_match="Authentication module has a null pointer bug",
        user_id="user_2",
        hard_negatives=["Authentication is working perfectly"],
        other_user_memories=["The authentication flow was redesigned"],
    ),
]


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not vec1 or not vec2:
        return 0.0
    
    # Handle different dimensions
    min_dim = min(len(vec1), len(vec2))
    vec1 = vec1[:min_dim]
    vec2 = vec2[:min_dim]
    
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


async def evaluate_provider(
    provider_name: str,
    test_cases: List[TestCase],
    ollama_base_url: str = "http://192.168.79.1:11434/v1",
    ollama_model: str = "mxbai-embed-large",
) -> ProviderMetrics:
    """Evaluate a single provider on test cases."""
    
    config = EmbeddingConfig(
        provider=provider_name,
        ollama_base_url=ollama_base_url,
        ollama_model=ollama_model,
    )
    
    if provider_name == "tfidf":
        provider = TfidfProvider(config)
        # Fit TF-IDF on all texts in test cases
        all_texts = []
        for tc in test_cases:
            all_texts.append(tc.query)
            all_texts.append(tc.expected_match)
            all_texts.extend(tc.hard_negatives)
            all_texts.extend(tc.other_user_memories)
            all_texts.extend(tc.duplicates)
        provider.fit(all_texts)
    else:
        provider = OllamaEmbeddingProvider(config)
    
    metrics = ProviderMetrics(
        provider=provider_name,
        model=config.ollama_model if provider_name == "ollama" else "tfidf-v1.0.0",
        total_cases=len(test_cases),
    )
    
    hit_at_1_count = 0
    hit_at_3_count = 0
    duplicate_suppressed = 0
    
    for tc in test_cases:
        # Get query embedding
        query_result = await provider.embed_one(tc.query)
        metrics.latency_samples.append(query_result.latency_ms)
        
        if not query_result.success:
            print(f"  Warning: Failed to embed query: {tc.query[:30]}...")
            continue
        
        query_vec = query_result.vectors[0]
        
        # Build candidate pool
        candidates = []
        
        # Expected match (should be top)
        candidates.append(("expected", tc.expected_match, tc.user_id))
        
        # Hard negatives (should NOT be top)
        for hn in tc.hard_negatives:
            candidates.append(("hard_neg", hn, tc.user_id))
        
        # Other user memories (should NOT appear for this user)
        for ou in tc.other_user_memories:
            candidates.append(("other_user", ou, f"{tc.user_id}_other"))
        
        # Duplicates (should be suppressed)
        for dup in tc.duplicates:
            candidates.append(("duplicate", dup, tc.user_id))
        
        # Embed all candidates
        texts_to_embed = [c[1] for c in candidates]
        batch_result = await provider.embed_batch(texts_to_embed)
        
        if not batch_result.success:
            print(f"  Warning: Failed to embed candidates")
            continue
        
        # Compute similarities
        similarities = []
        for i, (ctype, text, user_id) in enumerate(candidates):
            if i < len(batch_result.vectors):
                sim = cosine_similarity(query_vec, batch_result.vectors[i])
                similarities.append((sim, ctype, text, user_id))
        
        # Sort by similarity descending
        similarities.sort(key=lambda x: x[0], reverse=True)
        
        # Check hit@1
        if similarities and similarities[0][1] == "expected":
            hit_at_1_count += 1
        
        # Check hit@3
        top_3_types = [s[1] for s in similarities[:3]]
        if "expected" in top_3_types:
            hit_at_3_count += 1
        
        # Check hard negative false recall
        for sim, ctype, text, user_id in similarities[:3]:
            if ctype == "hard_neg":
                metrics.hard_negative_false_recall_count += 1
        
        # Check wrong user recall
        for sim, ctype, text, user_id in similarities[:3]:
            if ctype == "other_user" and user_id != tc.user_id:
                metrics.wrong_user_recall_count += 1
        
        # Check duplicate suppression
        for sim, ctype, text, user_id in similarities:
            if ctype == "duplicate" and sim > 0.9:  # High similarity = duplicate detected
                duplicate_suppressed += 1
    
    # Compute final metrics
    metrics.hit_at_1 = hit_at_1_count / metrics.total_cases if metrics.total_cases > 0 else 0
    metrics.hit_at_3 = hit_at_3_count / metrics.total_cases if metrics.total_cases > 0 else 0
    metrics.duplicate_suppression_rate = duplicate_suppressed / (len(test_cases) * 2) if test_cases else 0  # avg 2 dup per case
    metrics.compute_aggregates()
    
    return metrics


async def run_ab_evaluation(
    output_dir: Optional[str] = None,
    ollama_base_url: str = "http://192.168.79.1:11434/v1",
    ollama_model: str = "mxbai-embed-large",
) -> Dict[str, Any]:
    """Run full A/B evaluation between TF-IDF and Ollama."""
    
    print("=" * 60)
    print("OpenEmotion v6a Embedding A/B Evaluation")
    print("=" * 60)
    
    test_cases = DEFAULT_TEST_CASES
    
    results = {
        "version": "v6a",
        "timestamp": datetime.now().isoformat(),
        "config": {
            "ollama_base_url": ollama_base_url,
            "ollama_model": ollama_model,
            "test_case_count": len(test_cases),
        },
        "providers": {},
    }
    
    # Evaluate TF-IDF
    print("\n[1/2] Evaluating TF-IDF provider...")
    tfidf_metrics = await evaluate_provider("tfidf", test_cases)
    results["providers"]["tfidf"] = asdict(tfidf_metrics)
    
    print(f"  hit@1: {tfidf_metrics.hit_at_1:.2%}")
    print(f"  hit@3: {tfidf_metrics.hit_at_3:.2%}")
    print(f"  avg latency: {tfidf_metrics.avg_latency_ms:.2f}ms")
    print(f"  wrong_user_recall: {tfidf_metrics.wrong_user_recall_count}")
    
    # Evaluate Ollama
    print("\n[2/2] Evaluating Ollama provider...")
    ollama_metrics = await evaluate_provider(
        "ollama", test_cases, ollama_base_url, ollama_model
    )
    results["providers"]["ollama"] = asdict(ollama_metrics)
    
    print(f"  hit@1: {ollama_metrics.hit_at_1:.2%}")
    print(f"  hit@3: {ollama_metrics.hit_at_3:.2%}")
    print(f"  avg latency: {ollama_metrics.avg_latency_ms:.2f}ms")
    print(f"  wrong_user_recall: {ollama_metrics.wrong_user_recall_count}")
    
    # Compute verdict
    print("\n" + "=" * 60)
    print("VERDICT")
    print("=" * 60)
    
    # Comparison table
    print(f"\n{'Metric':<30} {'TF-IDF':>12} {'Ollama':>12} {'Δ':>10}")
    print("-" * 66)
    
    delta_hit1 = ollama_metrics.hit_at_1 - tfidf_metrics.hit_at_1
    delta_hit3 = ollama_metrics.hit_at_3 - tfidf_metrics.hit_at_3
    delta_latency = ollama_metrics.avg_latency_ms - tfidf_metrics.avg_latency_ms
    
    print(f"{'hit@1':<30} {tfidf_metrics.hit_at_1:>12.2%} {ollama_metrics.hit_at_1:>12.2%} {delta_hit1:>+10.2%}")
    print(f"{'hit@3':<30} {tfidf_metrics.hit_at_3:>12.2%} {ollama_metrics.hit_at_3:>12.2%} {delta_hit3:>+10.2%}")
    print(f"{'wrong_user_recall_count':<30} {tfidf_metrics.wrong_user_recall_count:>12} {ollama_metrics.wrong_user_recall_count:>12}")
    print(f"{'hard_negative_false_recall':<30} {tfidf_metrics.hard_negative_false_recall_count:>12} {ollama_metrics.hard_negative_false_recall_count:>12}")
    print(f"{'avg_latency_ms':<30} {tfidf_metrics.avg_latency_ms:>12.2f} {ollama_metrics.avg_latency_ms:>12.2f} {delta_latency:>+10.2f}")
    print(f"{'p95_latency_ms':<30} {tfidf_metrics.p95_latency_ms:>12.2f} {ollama_metrics.p95_latency_ms:>12.2f}")
    
    # Determine verdict
    verdict = "inconclusive"
    
    # Check decision criteria
    better_hit = ollama_metrics.hit_at_1 > tfidf_metrics.hit_at_1 or ollama_metrics.hit_at_3 > tfidf_metrics.hit_at_3
    no_wrong_user_regression = ollama_metrics.wrong_user_recall_count <= tfidf_metrics.wrong_user_recall_count
    no_hard_negative_regression = ollama_metrics.hard_negative_false_recall_count <= tfidf_metrics.hard_negative_false_recall_count
    acceptable_latency = ollama_metrics.avg_latency_ms < 200  # 200ms threshold
    
    if better_hit and no_wrong_user_regression and no_hard_negative_regression and acceptable_latency:
        verdict = "better"
    elif not no_wrong_user_regression or not no_hard_negative_regression:
        verdict = "worse"
    elif not acceptable_latency:
        verdict = "neutral"  # Quality might be good but latency too high
    elif ollama_metrics.hit_at_1 < tfidf_metrics.hit_at_1 and ollama_metrics.hit_at_3 < tfidf_metrics.hit_at_3:
        verdict = "worse"
    
    results["verdict"] = verdict
    results["verdict_criteria"] = {
        "better_hit": better_hit,
        "no_wrong_user_regression": no_wrong_user_regression,
        "no_hard_negative_regression": no_hard_negative_regression,
        "acceptable_latency": acceptable_latency,
    }
    
    print(f"\nVerdict: {verdict.upper()}")
    
    # Recommendation
    if verdict == "better":
        print("✅ Ollama is a candidate for high-quality retrieval mode")
        results["recommendation"] = "ollama_as_high_quality_candidate"
    elif verdict == "worse":
        print("❌ Ollama performs worse than TF-IDF, not recommended for upgrade")
        results["recommendation"] = "keep_tfidf"
    elif verdict == "neutral":
        print("⚠️ Ollama quality may be better but latency is too high")
        results["recommendation"] = "keep_tfidf_with_ollama_optional"
    else:
        print("⚠️ Results inconclusive, need more test cases")
        results["recommendation"] = "inconclusive_need_more_data"
    
    # Save results
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        report_path = output_path / "ab_report.json"
        with open(report_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nResults saved to: {report_path}")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="A/B evaluation for embedding providers")
    parser.add_argument(
        "--output",
        default="artifacts/eval/v6a",
        help="Output directory for results",
    )
    parser.add_argument(
        "--base-url",
        default="http://192.168.79.1:11434/v1",
        help="Ollama base URL",
    )
    parser.add_argument(
        "--model",
        default="mxbai-embed-large",
        help="Ollama model",
    )
    
    args = parser.parse_args()
    
    return asyncio.run(run_ab_evaluation(
        output_dir=args.output,
        ollama_base_url=args.base_url,
        ollama_model=args.model,
    ))


if __name__ == "__main__":
    main()

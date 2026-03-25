#!/usr/bin/env python3
"""
Smoke test for Ollama embedding provider.

Tests:
1. Healthcheck - can we reach Ollama?
2. Single embedding - can we embed one text?
3. Batch embedding - can we embed multiple texts?
4. Vector dimension - what's the actual dimension?

Usage:
    python scripts/smoke_ollama_embedding.py
    python scripts/smoke_ollama_embedding.py --base-url http://192.168.79.1:11434/v1
    python scripts/smoke_ollama_embedding.py --model mxbai-embed-large
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.memory.embedding.contracts import EmbeddingConfig
from emotiond.memory.embedding.providers.ollama_provider import OllamaEmbeddingProvider
from emotiond.memory.embedding.providers.tfidf_provider import TfidfProvider


async def smoke_ollama(base_url: str, model: str) -> dict:
    """Run smoke tests on Ollama provider."""
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "provider": "ollama",
        "base_url": base_url,
        "model": model,
        "tests": {},
    }
    
    config = EmbeddingConfig(
        provider="ollama",
        ollama_base_url=base_url,
        ollama_model=model,
        timeout_ms=15000,
    )
    provider = OllamaEmbeddingProvider(config)
    
    # Test 1: Healthcheck
    print("\n[1/4] Healthcheck...")
    health = await provider.healthcheck()
    results["tests"]["healthcheck"] = {
        "passed": health.healthy,
        "latency_ms": round(health.latency_ms, 2),
        "error": health.error,
    }
    
    if not health.healthy:
        print(f"  ❌ FAILED: {health.error}")
        results["overall_status"] = "FAILED"
        return results
    
    print(f"  ✅ PASSED (latency: {health.latency_ms:.2f}ms)")
    
    # Test 2: Single embedding
    print("\n[2/4] Single embedding...")
    test_text = "The quick brown fox jumps over the lazy dog."
    result = await provider.embed_one(test_text)
    
    results["tests"]["single_embedding"] = {
        "passed": result.success,
        "latency_ms": round(result.latency_ms, 2),
        "vector_dim": result.vector_dim,
        "error": result.error,
    }
    
    if not result.success:
        print(f"  ❌ FAILED: {result.error}")
        results["overall_status"] = "FAILED"
        return results
    
    print(f"  ✅ PASSED (dim: {result.vector_dim}, latency: {result.latency_ms:.2f}ms)")
    
    # Test 3: Batch embedding
    print("\n[3/4] Batch embedding...")
    test_texts = [
        "Hello world",
        "OpenEmotion is an emotional core daemon",
        "Embeddings are useful for semantic search",
    ]
    batch_result = await provider.embed_batch(test_texts)
    
    results["tests"]["batch_embedding"] = {
        "passed": batch_result.success,
        "latency_ms": round(batch_result.latency_ms, 2),
        "batch_size": len(test_texts),
        "vectors_count": len(batch_result.vectors),
        "vector_dim": batch_result.vector_dim,
        "error": batch_result.error,
    }
    
    if not batch_result.success:
        print(f"  ❌ FAILED: {batch_result.error}")
        results["overall_status"] = "FAILED"
        return results
    
    print(f"  ✅ PASSED ({len(batch_result.vectors)} vectors, latency: {batch_result.latency_ms:.2f}ms)")
    
    # Test 4: Metadata
    print("\n[4/4] Provider metadata...")
    metadata = provider.get_metadata()
    
    results["tests"]["metadata"] = {
        "passed": True,
        "provider": metadata.provider,
        "model": metadata.model,
        "vector_dim": metadata.vector_dim,
        "max_batch_size": metadata.max_batch_size,
    }
    
    print(f"  ✅ PASSED")
    print(f"     Provider: {metadata.provider}")
    print(f"     Model: {metadata.model}")
    print(f"     Vector dim: {metadata.vector_dim}")
    print(f"     Max batch: {metadata.max_batch_size}")
    
    results["overall_status"] = "PASSED"
    return results


async def smoke_tfidf() -> dict:
    """Run smoke tests on TF-IDF provider."""
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "provider": "tfidf",
        "tests": {},
    }
    
    config = EmbeddingConfig(provider="tfidf")
    provider = TfidfProvider(config)
    
    # Fit on some sample documents
    sample_docs = [
        "The quick brown fox",
        "A lazy dog sleeps",
        "OpenEmotion is great",
    ]
    provider.fit(sample_docs)
    
    # Test 1: Healthcheck
    print("\n[TF-IDF] Healthcheck...")
    health = await provider.healthcheck()
    results["tests"]["healthcheck"] = {
        "passed": health.healthy,
        "latency_ms": round(health.latency_ms, 2),
    }
    print(f"  ✅ PASSED")
    
    # Test 2: Single embedding
    print("\n[TF-IDF] Single embedding...")
    result = await provider.embed_one("The fox is quick")
    
    results["tests"]["single_embedding"] = {
        "passed": result.success,
        "latency_ms": round(result.latency_ms, 2),
        "vector_dim": result.vector_dim,
    }
    
    if result.success:
        print(f"  ✅ PASSED (dim: {result.vector_dim}, latency: {result.latency_ms:.2f}ms)")
    else:
        print(f"  ❌ FAILED: {result.error}")
        results["overall_status"] = "FAILED"
        return results
    
    # Test 3: Batch embedding
    print("\n[TF-IDF] Batch embedding...")
    batch_result = await provider.embed_batch(["Hello", "World"])
    
    results["tests"]["batch_embedding"] = {
        "passed": batch_result.success,
        "vectors_count": len(batch_result.vectors),
    }
    print(f"  ✅ PASSED ({len(batch_result.vectors)} vectors)")
    
    results["overall_status"] = "PASSED"
    return results


def main():
    parser = argparse.ArgumentParser(description="Smoke test for embedding providers")
    parser.add_argument(
        "--base-url",
        default="http://192.168.79.1:11434/v1",
        help="Ollama base URL (default: http://192.168.79.1:11434/v1)",
    )
    parser.add_argument(
        "--model",
        default="mxbai-embed-large",
        help="Ollama model name (default: mxbai-embed-large)",
    )
    parser.add_argument(
        "--tfidf",
        action="store_true",
        help="Also test TF-IDF provider",
    )
    parser.add_argument(
        "--output",
        help="Output file for results (JSON)",
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("OpenEmotion Embedding Smoke Test")
    print("=" * 60)
    
    all_results = {
        "run_timestamp": datetime.utcnow().isoformat(),
        "providers": {},
    }
    
    # Run Ollama smoke test
    print(f"\n>>> Testing Ollama provider: {args.base_url}")
    ollama_results = asyncio.run(smoke_ollama(args.base_url, args.model))
    all_results["providers"]["ollama"] = ollama_results
    
    # Run TF-IDF if requested
    if args.tfidf:
        print("\n>>> Testing TF-IDF provider")
        tfidf_results = asyncio.run(smoke_tfidf())
        all_results["providers"]["tfidf"] = tfidf_results
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    ollama_status = ollama_results.get("overall_status", "UNKNOWN")
    print(f"Ollama:  {'✅ PASSED' if ollama_status == 'PASSED' else '❌ ' + ollama_status}")
    
    if args.tfidf:
        tfidf_status = all_results["providers"]["tfidf"].get("overall_status", "UNKNOWN")
        print(f"TF-IDF:  {'✅ PASSED' if tfidf_status == 'PASSED' else '❌ ' + tfidf_status}")
    
    # Output to file if requested
    if args.output:
        with open(args.output, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"\nResults written to: {args.output}")
    
    # Return exit code
    return 0 if ollama_status == "PASSED" else 1


if __name__ == "__main__":
    sys.exit(main())

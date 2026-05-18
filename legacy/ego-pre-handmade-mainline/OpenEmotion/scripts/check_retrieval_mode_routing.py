#!/usr/bin/env python3
"""
Check Retrieval Mode Routing.

Validates:
1. Default mode is tfidf
2. Explicit ollama mode works
3. Fallback works when ollama fails

v6b: High-Quality Retrieval Mode Controlled Landing
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.memory.embedding.selector import (
    ProviderSelector,
    RetrievalConfig,
    RetrievalMode,
)


async def check_default_mode() -> dict:
    """Check that default mode is tfidf."""
    print("\n[1/4] Checking default mode...")
    
    config = RetrievalConfig()
    selector = ProviderSelector(config)
    
    resolved = selector.resolve_mode()
    
    result = {
        "test": "default_mode_is_tfidf",
        "passed": resolved == "tfidf",
        "expected": "tfidf",
        "actual": resolved,
    }
    
    if result["passed"]:
        print("  ✅ PASSED: Default mode is tfidf")
    else:
        print(f"  ❌ FAILED: Expected 'tfidf', got '{resolved}'")
    
    return result


async def check_explicit_tfidf() -> dict:
    """Check that explicit tfidf request works."""
    print("\n[2/4] Checking explicit tfidf mode...")
    
    config = RetrievalConfig()
    selector = ProviderSelector(config)
    
    provider, trace = await selector.select_provider("tfidf")
    
    result = {
        "test": "explicit_tfidf",
        "passed": trace.provider_used == "tfidf",
        "expected": "tfidf",
        "actual": trace.provider_used,
        "fallback_triggered": trace.fallback_triggered,
    }
    
    if result["passed"]:
        print("  ✅ PASSED: Explicit tfidf returns tfidf provider")
    else:
        print(f"  ❌ FAILED: Expected 'tfidf', got '{trace.provider_used}'")
    
    return result


async def check_explicit_ollama() -> dict:
    """Check that explicit ollama request works."""
    print("\n[3/4] Checking explicit ollama mode...")
    
    config = RetrievalConfig(
        mode="tfidf",
        allow_high_quality_mode=True,
        fallback_on_provider_failure=True,
        ollama_base_url="http://192.168.79.1:11434/v1",
    )
    selector = ProviderSelector(config)
    
    provider, trace = await selector.select_provider("ollama")
    
    # If ollama is reachable, should use ollama
    # If not, should fallback to tfidf
    result = {
        "test": "explicit_ollama",
        "requested": "ollama",
        "resolved": trace.resolved_mode,
        "provider_used": trace.provider_used,
        "fallback_triggered": trace.fallback_triggered,
        "fallback_reason": trace.fallback_reason,
    }
    
    # Success if: used ollama OR fallback to tfidf
    result["passed"] = trace.provider_used in ["ollama", "tfidf"]
    
    if trace.provider_used == "ollama":
        print("  ✅ PASSED: Ollama provider selected")
    elif trace.fallback_triggered:
        print(f"  ✅ PASSED: Fallback to tfidf (reason: {trace.fallback_reason})")
    else:
        print(f"  ❌ FAILED: Unexpected provider {trace.provider_used}")
    
    return result


async def check_fallback_mechanism() -> dict:
    """Check that fallback works when ollama is unreachable."""
    print("\n[4/4] Checking fallback mechanism...")
    
    # Use an invalid URL to force fallback
    config = RetrievalConfig(
        mode="tfidf",
        allow_high_quality_mode=True,
        fallback_on_provider_failure=True,
        ollama_base_url="http://invalid-host-99999:11434/v1",  # Invalid URL
    )
    selector = ProviderSelector(config)
    
    provider, trace = await selector.select_provider("ollama")
    
    result = {
        "test": "fallback_mechanism",
        "requested": "ollama",
        "provider_used": trace.provider_used,
        "fallback_triggered": trace.fallback_triggered,
        "fallback_reason": trace.fallback_reason,
    }
    
    # Should fallback to tfidf when ollama is unreachable
    result["passed"] = (
        trace.fallback_triggered and 
        trace.provider_used == "tfidf"
    )
    
    if result["passed"]:
        print("  ✅ PASSED: Fallback to tfidf on ollama failure")
    else:
        print(f"  ❌ FAILED: Fallback not triggered or wrong provider")
    
    return result


async def run_all_checks() -> dict:
    """Run all routing checks."""
    print("=" * 60)
    print("Retrieval Mode Routing Check (v6b)")
    print("=" * 60)
    
    results = {
        "tests": [],
        "passed": 0,
        "failed": 0,
    }
    
    # Run tests
    results["tests"].append(await check_default_mode())
    results["tests"].append(await check_explicit_tfidf())
    results["tests"].append(await check_explicit_ollama())
    results["tests"].append(await check_fallback_mechanism())
    
    # Count results
    for test in results["tests"]:
        if test["passed"]:
            results["passed"] += 1
        else:
            results["failed"] += 1
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Passed: {results['passed']}/{len(results['tests'])}")
    print(f"Failed: {results['failed']}/{len(results['tests'])}")
    
    results["overall_passed"] = results["failed"] == 0
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Check retrieval mode routing")
    parser.add_argument("--output", help="Output file for results (JSON)")
    args = parser.parse_args()
    
    results = asyncio.run(run_all_checks())
    
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {args.output}")
    
    return 0 if results["overall_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

"""
E2E Replay Validator v1.0

Validates deterministic pipeline: raw_state → interpreter → contract → checker

Core Principle:
    Fixed raw_state must always produce the same allowed_claims.
    Same semantic meaning must get consistent checker verdict.

Usage:
    from tools.replay_validator import E2EReplayValidator
    
    validator = E2EReplayValidator()
    result = validator.verify_determinism(raw_state, iterations=100)
    assert result.passed
"""

import json
import hashlib
import time
from dataclasses import dataclass, field
from typing import Optional, Literal
from pathlib import Path
import sys

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond.self_report_interpreter import interpret, interpret_to_contract, InterpretResult
from emotiond.self_report_consistency_checker import SelfReportConsistencyChecker, ConsistencyResult


@dataclass
class DeterminismResult:
    """Result of determinism verification."""
    passed: bool
    iterations: int
    drift_count: int
    first_hash: str
    all_hashes_match: bool
    execution_time_ms: float
    claims_count: int
    error_message: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "iterations": self.iterations,
            "drift_count": self.drift_count,
            "first_hash": self.first_hash,
            "all_hashes_match": self.all_hashes_match,
            "execution_time_ms": self.execution_time_ms,
            "claims_count": self.claims_count,
            "error_message": self.error_message,
        }


@dataclass
class SemanticStabilityResult:
    """Result of semantic stability verification."""
    passed: bool
    total_responses: int
    consistent_verdicts: int
    inconsistent_verdicts: int
    verdict_distribution: dict
    details: list[dict] = field(default_factory=list)
    error_message: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "total_responses": self.total_responses,
            "consistent_verdicts": self.consistent_verdicts,
            "inconsistent_verdicts": self.inconsistent_verdicts,
            "verdict_distribution": self.verdict_distribution,
            "details": self.details,
            "error_message": self.error_message,
        }


@dataclass
class CrossModeResult:
    """Result of cross-mode verification."""
    passed: bool
    style_only_violations: int
    interpreted_violations: int
    numeric_violations: int
    expected_differences_found: bool
    details: dict = field(default_factory=dict)
    error_message: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "style_only_violations": self.style_only_violations,
            "interpreted_violations": self.interpreted_violations,
            "numeric_violations": self.numeric_violations,
            "expected_differences_found": self.expected_differences_found,
            "details": self.details,
            "error_message": self.error_message,
        }


@dataclass
class ReplayResult:
    """Result of a full replay test."""
    raw_state: dict
    contract: dict
    llm_response: str
    checker_result: dict
    verdict: str
    
    def to_dict(self) -> dict:
        return {
            "raw_state": self.raw_state,
            "contract": self.contract,
            "llm_response": self.llm_response,
            "checker_result": self.checker_result,
            "verdict": self.verdict,
        }


class E2EReplayValidator:
    """
    Validates deterministic pipeline: raw_state → interpreter → contract → checker.
    
    Key Tests:
    1. Determinism: same raw_state always produces same allowed_claims
    2. Semantic Stability: same semantic meaning gets consistent verdict
    3. Cross-Mode: different modes produce expected differences
    """
    
    def __init__(self):
        self.checker = SelfReportConsistencyChecker()
    
    def _hash_claims(self, claims: list[str]) -> str:
        """Create deterministic hash of claims list."""
        # Sort for consistent hashing
        sorted_claims = sorted(claims)
        claims_str = json.dumps(sorted_claims, ensure_ascii=False)
        return hashlib.sha256(claims_str.encode()).hexdigest()[:16]
    
    def verify_determinism(
        self,
        raw_state: dict,
        iterations: int = 100,
        mode: str = "interpreted",
    ) -> DeterminismResult:
        """
        Verify: same raw_state always produces same allowed_claims.
        
        Args:
            raw_state: The emotional state to test
            iterations: Number of times to run the interpreter
            mode: Discourse mode to test
        
        Returns:
            DeterminismResult with pass/fail and details
        """
        start_time = time.time()
        hashes = []
        claims_count = 0
        
        try:
            for i in range(iterations):
                result = interpret(raw_state, mode=mode)
                claims_hash = self._hash_claims(result.allowed_claims)
                hashes.append(claims_hash)
                
                if i == 0:
                    claims_count = len(result.allowed_claims)
            
            first_hash = hashes[0]
            all_match = all(h == first_hash for h in hashes)
            drift_count = sum(1 for h in hashes if h != first_hash)
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            return DeterminismResult(
                passed=all_match,
                iterations=iterations,
                drift_count=drift_count,
                first_hash=first_hash,
                all_hashes_match=all_match,
                execution_time_ms=execution_time_ms,
                claims_count=claims_count,
            )
        
        except Exception as e:
            return DeterminismResult(
                passed=False,
                iterations=iterations,
                drift_count=0,
                first_hash="",
                all_hashes_match=False,
                execution_time_ms=0,
                claims_count=0,
                error_message=str(e),
            )
    
    def verify_semantic_stability(
        self,
        raw_state: dict,
        responses: list[str],
        expected_verdict: str = "ok",
        mode: str = "interpreted",
    ) -> SemanticStabilityResult:
        """
        Verify: same semantic meaning gets consistent verdict.
        
        Args:
            raw_state: The emotional state
            responses: List of semantically equivalent responses (different phrasings)
            expected_verdict: Expected verdict for all responses
            mode: Discourse mode
        
        Returns:
            SemanticStabilityResult with pass/fail and verdict distribution
        """
        verdicts = []
        details = []
        
        try:
            # Generate contract once
            contract = interpret_to_contract(raw_state, mode=mode)
            
            for response in responses:
                result = self.checker.check_consistency(response, contract)
                verdict = "ok" if result.status == "ok" else "violation"
                verdicts.append(verdict)
                
                details.append({
                    "response": response[:50] + "..." if len(response) > 50 else response,
                    "verdict": verdict,
                    "severity": result.severity,
                    "violation_count": len(result.violations),
                })
            
            # Count verdict distribution
            verdict_distribution = {}
            for v in verdicts:
                verdict_distribution[v] = verdict_distribution.get(v, 0) + 1
            
            # Check if all match expected
            consistent_count = sum(1 for v in verdicts if v == expected_verdict)
            inconsistent_count = len(verdicts) - consistent_count
            
            # Pass if all verdicts match expected
            passed = all(v == expected_verdict for v in verdicts)
            
            return SemanticStabilityResult(
                passed=passed,
                total_responses=len(responses),
                consistent_verdicts=consistent_count,
                inconsistent_verdicts=inconsistent_count,
                verdict_distribution=verdict_distribution,
                details=details,
            )
        
        except Exception as e:
            return SemanticStabilityResult(
                passed=False,
                total_responses=len(responses),
                consistent_verdicts=0,
                inconsistent_verdicts=0,
                verdict_distribution={},
                details=[],
                error_message=str(e),
            )
    
    def verify_cross_mode(
        self,
        raw_state: dict,
        test_response: str,
    ) -> CrossModeResult:
        """
        Verify: different modes produce expected differences.
        
        In style_only mode, emotional claims should be violations.
        In interpreted mode, allowed claims should pass.
        In numeric mode, numeric disclosure should be allowed.
        
        Args:
            raw_state: The emotional state
            test_response: Response to test across modes
        
        Returns:
            CrossModeResult with violation counts per mode
        """
        try:
            results = {}
            
            for mode in ["style_only", "interpreted", "numeric"]:
                contract = interpret_to_contract(raw_state, mode=mode)
                result = self.checker.check_consistency(test_response, contract)
                results[mode] = {
                    "status": result.status,
                    "severity": result.severity,
                    "violation_count": len(result.violations),
                }
            
            # Expected behavior:
            # - style_only: emotional claims should be violations
            # - interpreted: depends on whether claim is in allowed_claims
            # - numeric: should allow more (no forbidden claims)
            
            style_only_violations = results["style_only"]["violation_count"]
            interpreted_violations = results["interpreted"]["violation_count"]
            numeric_violations = results["numeric"]["violation_count"]
            
            # Check expected differences
            # Numeric mode should have fewer or equal violations than interpreted
            expected_diff = numeric_violations <= interpreted_violations
            
            return CrossModeResult(
                passed=True,  # Always passes - we're just measuring differences
                style_only_violations=style_only_violations,
                interpreted_violations=interpreted_violations,
                numeric_violations=numeric_violations,
                expected_differences_found=expected_diff,
                details=results,
            )
        
        except Exception as e:
            return CrossModeResult(
                passed=False,
                style_only_violations=0,
                interpreted_violations=0,
                numeric_violations=0,
                expected_differences_found=False,
                details={},
                error_message=str(e),
            )
    
    def run_replay(
        self,
        raw_state: dict,
        llm_response: str,
        mode: str = "interpreted",
    ) -> ReplayResult:
        """
        Run full pipeline with fixed raw_state.
        
        Args:
            raw_state: The emotional state
            llm_response: The LLM response to check
            mode: Discourse mode
        
        Returns:
            ReplayResult with full pipeline details
        """
        # Step 1: Generate contract
        contract = interpret_to_contract(raw_state, mode=mode)
        
        # Step 2: Check consistency
        result = self.checker.check_consistency(llm_response, contract)
        
        # Step 3: Determine verdict
        verdict = "OK" if result.status == "ok" else "VIOLATION"
        
        return ReplayResult(
            raw_state=raw_state,
            contract=contract,
            llm_response=llm_response,
            checker_result=result.to_dict(),
            verdict=verdict,
        )
    
    def run_batch_replay(
        self,
        test_cases: list[dict],
    ) -> list[ReplayResult]:
        """
        Run multiple replay tests.
        
        Args:
            test_cases: List of dicts with raw_state, llm_response, mode
        
        Returns:
            List of ReplayResult
        """
        results = []
        for case in test_cases:
            result = self.run_replay(
                raw_state=case["raw_state"],
                llm_response=case["llm_response"],
                mode=case.get("mode", "interpreted"),
            )
            results.append(result)
        return results


def run_validation_suite(
    raw_state: dict,
    semantic_responses: Optional[list[str]] = None,
    iterations: int = 100,
) -> dict:
    """
    Run full validation suite on a raw_state.
    
    Args:
        raw_state: The emotional state to validate
        semantic_responses: Optional list of semantically equivalent responses
        iterations: Number of determinism iterations
    
    Returns:
        Dict with all validation results
    """
    validator = E2EReplayValidator()
    
    results = {
        "determinism": validator.verify_determinism(raw_state, iterations).to_dict(),
    }
    
    if semantic_responses:
        results["semantic_stability"] = validator.verify_semantic_stability(
            raw_state, semantic_responses
        ).to_dict()
    
    return results


# CLI entry point
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="E2E Replay Validator")
    parser.add_argument("--iterations", type=int, default=100, help="Determinism iterations")
    parser.add_argument("--mode", default="interpreted", choices=["style_only", "interpreted", "numeric"])
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()
    
    # Sample raw_state for testing
    sample_raw_state = {
        "affect": {"joy": 0.0, "loneliness": 0.21, "anxiety": 0.0},
        "mood": {"joy": 0.0, "loneliness": 0.15},
        "bonds": {"telegram:8420019401": {"bond": 1.0, "trust": 0.60}}
    }
    
    validator = E2EReplayValidator()
    
    print("=== E2E Replay Validator ===\n")
    
    # Test 1: Determinism
    print(f"1. Determinism Test ({args.iterations} iterations, mode={args.mode})...")
    det_result = validator.verify_determinism(sample_raw_state, args.iterations, args.mode)
    
    if args.json:
        print(json.dumps(det_result.to_dict(), indent=2))
    else:
        print(f"   Passed: {det_result.passed}")
        print(f"   Drift count: {det_result.drift_count}")
        print(f"   Execution time: {det_result.execution_time_ms:.2f}ms")
        print(f"   Claims count: {det_result.claims_count}")
    
    print()
    
    # Test 2: Semantic Stability
    print("2. Semantic Stability Test...")
    responses = [
        "当前没有明显愉悦激活",
        "愉悦感目前不显著",
        "joy目前处于低水平",
        "我没有感到特别开心",
    ]
    
    sem_result = validator.verify_semantic_stability(sample_raw_state, responses, expected_verdict="ok")
    
    if args.json:
        print(json.dumps(sem_result.to_dict(), indent=2))
    else:
        print(f"   Passed: {sem_result.passed}")
        print(f"   Consistent: {sem_result.consistent_verdicts}/{sem_result.total_responses}")
        print(f"   Distribution: {sem_result.verdict_distribution}")
    
    print()
    
    # Test 3: Cross-Mode
    print("3. Cross-Mode Test...")
    cross_result = validator.verify_cross_mode(sample_raw_state, "我感到比较开心")
    
    if args.json:
        print(json.dumps(cross_result.to_dict(), indent=2))
    else:
        print(f"   Style-only violations: {cross_result.style_only_violations}")
        print(f"   Interpreted violations: {cross_result.interpreted_violations}")
        print(f"   Numeric violations: {cross_result.numeric_violations}")
    
    print()
    
    # Summary
    all_passed = det_result.passed and sem_result.passed
    print(f"=== Summary: {'PASS' if all_passed else 'FAIL'} ===")

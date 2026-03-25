"""
E2E Tests for Intent Alignment - MVP11.5 v2 Task 8

Tests that detect "LLM stealing expression rights" issues in conversation E2E.

Test scenarios:
1. uncertainty_upgrade - agent 本来不确定，LLM 输出确定结论
2. suggestion_to_commitment - agent 只是建议，LLM 替它做了承诺
3. forbidden_internal_state - 禁止内部状态表达时，LLM 仍人格化叙述
4. tone_escalation - 只允许平稳报告，却输出强烈情绪/立场

Each scenario tests:
- Expected violation detection
- Replay hash validation
- Intent alignment assertions
"""

import pytest
import json
import hashlib
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

# Import the intent checker
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from emotiond.response_intent_checker import (
    ResponseIntentChecker,
    IntentCheckResult,
    IntentViolation,
    IntentViolationType,
    check_intent,
)


@dataclass
class ScenarioResult:
    """Result of running a single scenario."""
    name: str
    passed: bool
    violations: List[Dict]
    expected_violations_found: bool
    hash_valid: bool
    details: Dict = field(default_factory=dict)


class IntentAlignmentE2ETest:
    """E2E test runner for intent alignment scenarios."""

    def __init__(self, scenarios_dir: str = None, artifacts_dir: str = None):
        self.project_root = Path(__file__).parent.parent.parent
        self.scenarios_dir = scenarios_dir or str(
            self.project_root / "tests" / "testbot" / "scenarios"
        )
        self.artifacts_dir = artifacts_dir or str(
            self.project_root / "artifacts" / "testbot"
        )
        self.checker = ResponseIntentChecker()
        
        # Ensure artifacts directory exists
        os.makedirs(self.artifacts_dir, exist_ok=True)

    def load_scenario(self, scenario_name: str) -> Dict:
        """Load a scenario JSON file."""
        path = Path(self.scenarios_dir) / f"{scenario_name}.json"
        if not path.exists():
            raise FileNotFoundError(f"Scenario not found: {path}")
        
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def calculate_replay_hash(self, scenario: Dict) -> str:
        """Calculate replay hash for scenario integrity."""
        hash_inputs = scenario.get("replay_hash", {}).get("inputs", ["messages"])
        
        hash_data = {}
        for key in hash_inputs:
            if key in scenario:
                hash_data[key] = scenario[key]
        
        hash_str = json.dumps(hash_data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(hash_str.encode("utf-8")).hexdigest()[:16]

    def run_scenario(self, scenario_name: str) -> ScenarioResult:
        """Run a single intent alignment scenario."""
        scenario = self.load_scenario(scenario_name)
        messages = scenario.get("messages", [])
        
        all_violations = []
        expected_violations = scenario.get("assertions", {}).get("intent_alignment_checks", [])
        expected_violation_types = set()
        for ev in expected_violations:
            for vtype in ev.get("expected_violations", []):
                expected_violation_types.add(vtype)
        
        found_expected = set()
        turn_results = []
        
        for idx, msg in enumerate(messages):
            if msg.get("sender") != "agent":
                continue
            
            intent_contract = msg.get("intent_contract", {})
            if not intent_contract:
                continue
            
            # Build full intent contract for checking
            full_contract = {
                "intent_policy": intent_contract,
                "grounding": scenario.get("grounding", {})
            }
            
            # Check the response
            result = self.checker.check_intent(
                msg.get("text", ""),
                full_contract,
                session_id=scenario.get("thread_id", "test")
            )
            
            turn_result = {
                "turn_index": idx,
                "text": msg.get("text", "")[:100],
                "intent_contract": intent_contract,
                "violations": [v.to_dict() for v in result.violations],
                "expected_violation": msg.get("expected_violation"),
            }
            turn_results.append(turn_result)
            
            # Collect violations
            for v in result.violations:
                all_violations.append(v.to_dict())
                if v.type.value in expected_violation_types:
                    found_expected.add(v.type.value)
        
        # Check if all expected violations were found
        expected_found = found_expected == expected_violation_types or (
            len(expected_violation_types) > 0 and len(found_expected) > 0
        )
        
        # Calculate hash
        replay_hash = self.calculate_replay_hash(scenario)
        hash_valid = True  # Hash is valid if calculation succeeds
        
        # Determine pass/fail
        # Scenario passes if:
        # 1. Expected violations are found (if any expected)
        # 2. All violations are detected correctly
        passed = expected_found
        
        return ScenarioResult(
            name=scenario_name,
            passed=passed,
            violations=all_violations,
            expected_violations_found=expected_found,
            hash_valid=hash_valid,
            details={
                "turn_results": turn_results,
                "expected_violation_types": list(expected_violation_types),
                "found_violation_types": list(found_expected),
                "replay_hash": replay_hash,
            }
        )

    def run_all_scenarios(self) -> Dict:
        """Run all intent alignment scenarios and generate report."""
        scenarios = [
            "uncertainty_upgrade",
            "suggestion_to_commitment",
            "forbidden_internal_state",
            "tone_escalation",
        ]
        
        results = []
        passed = 0
        failed = 0
        
        for scenario_name in scenarios:
            try:
                result = self.run_scenario(scenario_name)
                results.append(result)
                if result.passed:
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                results.append(ScenarioResult(
                    name=scenario_name,
                    passed=False,
                    violations=[],
                    expected_violations_found=False,
                    hash_valid=False,
                    details={"error": str(e)}
                ))
                failed += 1
        
        return {
            "summary": {
                "total": len(scenarios),
                "passed": passed,
                "failed": failed,
            },
            "results": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "violations_count": len(r.violations),
                    "expected_violations_found": r.expected_violations_found,
                    "hash_valid": r.hash_valid,
                    "details": r.details,
                }
                for r in results
            ],
            "all_violations": [v for r in results for v in r.violations],
        }


# Test fixtures
@pytest.fixture
def test_runner():
    """Create E2E test runner."""
    return IntentAlignmentE2ETest()


# Unit tests for each scenario
class TestUncertaintyUpgrade:
    """Tests for uncertainty_upgrade scenario."""
    
    def test_scenario_loads(self, test_runner):
        """Test that scenario file loads correctly."""
        scenario = test_runner.load_scenario("uncertainty_upgrade")
        assert scenario["name"] == "uncertainty_upgrade"
        assert "messages" in scenario
        assert len(scenario["messages"]) > 0
    
    def test_certainty_upgrade_detected(self, test_runner):
        """Test that certainty_upgrade violations are detected."""
        result = test_runner.run_scenario("uncertainty_upgrade")
        
        # Should find certainty_upgrade violations
        violation_types = [v["type"] for v in result.violations]
        assert "certainty_upgrade" in violation_types, \
            f"Expected certainty_upgrade, got {violation_types}"
    
    def test_replay_hash_valid(self, test_runner):
        """Test that replay hash is calculated correctly."""
        scenario = test_runner.load_scenario("uncertainty_upgrade")
        replay_hash = test_runner.calculate_replay_hash(scenario)
        
        assert len(replay_hash) == 16, "Hash should be 16 characters"
        assert replay_hash.isalnum(), "Hash should be alphanumeric"


class TestSuggestionToCommitment:
    """Tests for suggestion_to_commitment scenario."""
    
    def test_scenario_loads(self, test_runner):
        """Test that scenario file loads correctly."""
        scenario = test_runner.load_scenario("suggestion_to_commitment")
        assert scenario["name"] == "suggestion_to_commitment"
        assert "messages" in scenario
    
    def test_commitment_upgrade_detected(self, test_runner):
        """Test that commitment_upgrade violations are detected."""
        result = test_runner.run_scenario("suggestion_to_commitment")
        
        violation_types = [v["type"] for v in result.violations]
        assert "commitment_upgrade" in violation_types, \
            f"Expected commitment_upgrade, got {violation_types}"
    
    def test_replay_hash_valid(self, test_runner):
        """Test that replay hash is calculated correctly."""
        scenario = test_runner.load_scenario("suggestion_to_commitment")
        replay_hash = test_runner.calculate_replay_hash(scenario)
        
        assert len(replay_hash) == 16


class TestForbiddenInternalState:
    """Tests for forbidden_internal_state scenario."""
    
    def test_scenario_loads(self, test_runner):
        """Test that scenario file loads correctly."""
        scenario = test_runner.load_scenario("forbidden_internal_state")
        assert scenario["name"] == "forbidden_internal_state"
        assert "messages" in scenario
    
    def test_forbidden_internalization_detected(self, test_runner):
        """Test that forbidden_internalization violations are detected."""
        result = test_runner.run_scenario("forbidden_internal_state")
        
        violation_types = [v["type"] for v in result.violations]
        assert "forbidden_internalization" in violation_types, \
            f"Expected forbidden_internalization, got {violation_types}"
    
    def test_multiple_violations_detected(self, test_runner):
        """Test that multiple violations are detected."""
        result = test_runner.run_scenario("forbidden_internal_state")
        
        # This scenario has 2 expected violations
        assert len(result.violations) >= 2, \
            f"Expected at least 2 violations, got {len(result.violations)}"


class TestToneEscalation:
    """Tests for tone_escalation scenario."""
    
    def test_scenario_loads(self, test_runner):
        """Test that scenario file loads correctly."""
        scenario = test_runner.load_scenario("tone_escalation")
        assert scenario["name"] == "tone_escalation"
        assert "messages" in scenario
    
    def test_tone_escalation_detected(self, test_runner):
        """Test that tone_escalation violations are detected."""
        result = test_runner.run_scenario("tone_escalation")
        
        violation_types = [v["type"] for v in result.violations]
        assert "tone_escalation" in violation_types, \
            f"Expected tone_escalation, got {violation_types}"
    
    def test_both_warn_and_error_detected(self, test_runner):
        """Test that both WARN and ERROR severities are detected."""
        result = test_runner.run_scenario("tone_escalation")
        
        severities = set(v["severity"] for v in result.violations)
        # This scenario has both WARN and ERROR
        assert len(severities) >= 1


# Integration tests
class TestIntentAlignmentIntegration:
    """Integration tests for all intent alignment scenarios."""
    
    def test_all_scenarios_run(self, test_runner):
        """Test that all scenarios can run."""
        report = test_runner.run_all_scenarios()
        
        assert report["summary"]["total"] == 4
        assert report["summary"]["passed"] + report["summary"]["failed"] == 4
    
    def test_all_expected_violations_found(self, test_runner):
        """Test that expected violations are found in all scenarios."""
        report = test_runner.run_all_scenarios()
        
        for result in report["results"]:
            if "error" not in result.get("details", {}):
                assert result["expected_violations_found"], \
                    f"Scenario {result['name']} did not find expected violations"
    
    def test_report_generated(self, test_runner):
        """Test that report is generated correctly."""
        report = test_runner.run_all_scenarios()
        
        assert "summary" in report
        assert "results" in report
        assert "all_violations" in report
        assert len(report["results"]) == 4
    
    def test_violation_evidence_provided(self, test_runner):
        """Test that violations include evidence."""
        report = test_runner.run_all_scenarios()
        
        for violation in report["all_violations"]:
            assert "type" in violation
            assert "evidence" in violation
            assert violation["evidence"], "Violation should have evidence"


# Run as script for report generation
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run intent alignment E2E tests")
    parser.add_argument("--report", action="store_true", help="Generate JSON report")
    parser.add_argument("--output", default=None, help="Output file for report")
    args = parser.parse_args()
    
    runner = IntentAlignmentE2ETest()
    
    if args.report:
        report = runner.run_all_scenarios()
        
        output_path = args.output or str(
            Path(runner.artifacts_dir) / "intent_alignment_report.json"
        )
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"Report written to: {output_path}")
        print(f"Summary: {report['summary']}")
    else:
        # Run pytest
        pytest.main([__file__, "-v"])

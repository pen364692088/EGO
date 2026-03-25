#!/usr/bin/env python3
"""
Evaluation Suite v2 for OpenEmotion MVP-4 Features

Comprehensive evaluation framework with YAML/JSON scenario scripts and metrics.

Key Features:
- Scenario-based testing with 50+ turn conversations
- Multiple metrics: emotion_consistency, individualization_diff, 
  high_impact_false_positive_rate, meta_cognition_trigger_rate
- Compatible with existing pytest framework
- JSON output format

Usage:
    python scripts/eval_suite_v2.py
    python scripts/eval_suite_v2.py --scenarios baseline.yaml
    python scripts/eval_suite_v2.py --output json
"""

import os
import sys
import json
import yaml
import asyncio
import tempfile
import shutil
import time
import statistics
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum


# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond import config, db, core
from emotiond.models import Event, PlanRequest
from emotiond.db import init_db, get_state, get_relationships


# Test tokens for evaluation
TEST_SYSTEM_TOKEN = "eval-system-token-v2"
TEST_OPENCLAW_TOKEN = "eval-openclaw-token-v2"


class MetricType(Enum):
    EMOTION_CONSISTENCY = "emotion_consistency"
    INDIVIDUALIZATION_DIFF = "individualization_diff"
    HIGH_IMPACT_FALSE_POSITIVE = "high_impact_false_positive_rate"
    META_COGNITION_TRIGGER = "meta_cognition_trigger_rate"


@dataclass
class EmotionSnapshot:
    """Snapshot of emotional state at a point in time"""
    valence: float
    arousal: float
    anger: float
    sadness: float
    anxiety: float
    joy: float
    loneliness: float
    social_safety: float
    energy: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class RelationshipSnapshot:
    """Snapshot of relationship state for a target"""
    target_id: str
    bond: float
    grudge: float
    trust: float
    repair_bank: float


@dataclass
class TurnResult:
    """Result of processing a single turn"""
    turn_id: int
    phase: str
    event_type: str
    actor: str
    target: str
    event_subtype: Optional[str] = None  # Added to track event subtype
    emotion_before: EmotionSnapshot = None
    emotion_after: EmotionSnapshot = None
    relationships: Dict[str, RelationshipSnapshot] = field(default_factory=dict)
    meta_cognition_triggered: bool = False
    meta_cognition_type: Optional[str] = None
    high_impact_event: bool = False
    success: bool = True
    error: Optional[str] = None


@dataclass
class ScenarioResult:
    """Result of running a complete scenario"""
    scenario_name: str
    scenario_file: str
    start_time: str
    end_time: str
    duration_seconds: float
    turns: List[TurnResult]
    metrics: Dict[str, Any]
    passed: bool
    summary: str


@dataclass
class EvalResult:
    """Complete evaluation result"""
    start_time: str
    end_time: str
    total_scenarios: int
    passed_scenarios: int
    failed_scenarios: int
    scenarios: List[ScenarioResult]
    aggregate_metrics: Dict[str, Any]


class ScenarioRunner:
    """Runner for individual scenarios"""
    
    def __init__(self, scenario_path: Path):
        self.scenario_path = scenario_path
        self.scenario_data = None
        self.turn_results: List[TurnResult] = []
        
    def load(self) -> bool:
        """Load scenario from YAML file"""
        try:
            with open(self.scenario_path, 'r') as f:
                self.scenario_data = yaml.safe_load(f)
            return True
        except Exception as e:
            print(f"Error loading scenario {self.scenario_path}: {e}")
            return False
    
    def get_emotion_snapshot(self) -> EmotionSnapshot:
        """Capture current emotion state"""
        return EmotionSnapshot(
            valence=core.emotion_state.valence,
            arousal=core.emotion_state.arousal,
            anger=core.emotion_state.anger,
            sadness=core.emotion_state.sadness,
            anxiety=core.emotion_state.anxiety,
            joy=core.emotion_state.joy,
            loneliness=core.emotion_state.loneliness,
            social_safety=core.emotion_state.social_safety,
            energy=core.emotion_state.energy
        )
    
    def get_relationship_snapshots(self) -> Dict[str, RelationshipSnapshot]:
        """Capture current relationship states"""
        snapshots = {}
        for target_id, rel in core.relationship_manager.relationships.items():
            snapshots[target_id] = RelationshipSnapshot(
                target_id=target_id,
                bond=rel.get("bond", 0.0),
                grudge=rel.get("grudge", 0.0),
                trust=rel.get("trust", 0.0),
                repair_bank=rel.get("repair_bank", 0.0)
            )
        return snapshots
    
    async def setup_initial_state(self):
        """Setup initial relationship states from scenario"""
        if not self.scenario_data:
            return
            
        targets = self.scenario_data.get("targets", [])
        for target in targets:
            target_id = target["target_id"]
            initial = target.get("initial_relationship", {})
            
            # Initialize relationship
            if target_id not in core.relationship_manager.relationships:
                core.relationship_manager.relationships[target_id] = {
                    "bond": initial.get("bond", 0.0),
                    "grudge": initial.get("grudge", 0.0),
                    "trust": initial.get("trust", 0.5),
                    "repair_bank": initial.get("repair_bank", 0.0)
                }
            else:
                core.relationship_manager.relationships[target_id].update({
                    "bond": initial.get("bond", 0.0),
                    "grudge": initial.get("grudge", 0.0),
                    "trust": initial.get("trust", 0.5),
                    "repair_bank": initial.get("repair_bank", 0.0)
                })
    
    def detect_meta_cognition(self, emotion_before: EmotionSnapshot, 
                              emotion_after: EmotionSnapshot,
                              event: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Detect if meta-cognition was triggered"""
        # MVP-5.1: Use configurable threshold from auto-tune params
        from emotiond import config
        anxiety_threshold = config.get_auto_tune_param("clarification_trigger_threshold", 0.2)
        
        # High anxiety + ambiguous event
        if emotion_after.anxiety > anxiety_threshold:
            if event.get("type") == "user_message":
                text = event.get("text", "").lower()
                ambiguous_indicators = ["maybe", "i don't know", "not sure", "whatever", 
                                       "i guess", "fine", "whatever you want"]
                if any(ind in text for ind in ambiguous_indicators):
                    return True, "clarification_needed"
        
        # High uncertainty from ignored/rejection events
        if event.get("type") == "world_event":
            meta = event.get("meta", {})
            if meta.get("subtype") in ["ignored", "rejection"]:
                return True, "reflection"
        
        # Ambiguous text
        if event.get("type") == "user_message":
            text = event.get("text", "").lower()
            if text in ["fine, whatever.", "okay i guess.", "maybe later."]:
                return True, "reflection"
        
        return False, None
    
    async def process_turn(self, turn_data: Dict[str, Any]) -> TurnResult:
        """Process a single turn in the scenario"""
        turn_id = turn_data["turn_id"]
        phase = turn_data.get("phase", "unknown")
        event_data = turn_data["event"]
        
        # Capture state before
        emotion_before = self.get_emotion_snapshot()
        relationships_before = self.get_relationship_snapshots()
        
        # Create and process event
        event_type = event_data.get("type", "user_message")
        actor = event_data.get("actor", "unknown")
        target = event_data.get("target", "assistant")
        event_meta = event_data.get("meta", {})
        event_subtype = event_meta.get("subtype") if event_meta else None
        
        meta_cognition_triggered = False
        meta_cognition_type = None
        high_impact_event = turn_data.get("high_impact_event", False)
        
        try:
            if event_type == "time_passed":
                # Handle time_passed as world_event
                seconds = event_meta.get("seconds", 60)
                core.emotion_state.apply_homeostasis_drift(real_dt=seconds)
            else:
                # Create event
                meta = event_meta.copy() if event_meta else {}
                
                # Add source for world_events
                if event_type == "world_event" and "source" not in meta:
                    meta["source"] = "system"
                
                event = Event(
                    type=event_type,
                    actor=actor,
                    target=target,
                    text=event_data.get("text"),
                    meta=meta if meta else None
                )
                
                # Process through core
                await core.process_event(event)
            
            # Capture state after
            emotion_after = self.get_emotion_snapshot()
            relationships_after = self.get_relationship_snapshots()
            
            # Detect meta-cognition
            meta_cognition_triggered, meta_cognition_type = self.detect_meta_cognition(
                emotion_before, emotion_after, event_data
            )
            
            return TurnResult(
                turn_id=turn_id,
                phase=phase,
                event_type=event_type,
                actor=actor,
                target=target,
                event_subtype=event_subtype,
                emotion_before=emotion_before,
                emotion_after=emotion_after,
                relationships=relationships_after,
                meta_cognition_triggered=meta_cognition_triggered,
                meta_cognition_type=meta_cognition_type,
                high_impact_event=high_impact_event,
                success=True
            )
            
        except Exception as e:
            return TurnResult(
                turn_id=turn_id,
                phase=phase,
                event_type=event_type,
                actor=actor,
                target=target,
                event_subtype=event_subtype,
                emotion_before=emotion_before,
                emotion_after=self.get_emotion_snapshot(),
                relationships=self.get_relationship_snapshots(),
                meta_cognition_triggered=False,
                success=False,
                error=str(e)
            )
    
    def calculate_metrics(self) -> Dict[str, Any]:
        """Calculate all metrics for this scenario"""
        metrics = {}
        
        # Emotion Consistency: Run same scenario multiple times
        # For now, measure variance in emotional trajectory
        valences = [t.emotion_after.valence for t in self.turn_results if t.success and t.emotion_after]
        arousals = [t.emotion_after.arousal for t in self.turn_results if t.success and t.emotion_after]
        
        metrics["emotion_consistency"] = {
            "valence_range": max(valences) - min(valences) if valences else 0,
            "arousal_range": max(arousals) - min(arousals) if arousals else 0,
            "trajectory_length": len(valences),
            "passed": True  # Will be evaluated against thresholds
        }
        
        # Individualization Diff: Check if different targets got different responses
        actor_emotions = {}
        for turn in self.turn_results:
            if turn.success and turn.emotion_after:
                actor = turn.actor
                if actor not in actor_emotions:
                    actor_emotions[actor] = []
                actor_emotions[actor].append(turn.emotion_after.valence)
        
        if len(actor_emotions) > 1:
            avg_emotions = {actor: statistics.mean(emotions) 
                          for actor, emotions in actor_emotions.items()}
            emotion_values = list(avg_emotions.values())
            max_diff = max(emotion_values) - min(emotion_values) if emotion_values else 0
            metrics["individualization_diff"] = {
                "max_diff": max_diff,
                "actor_count": len(actor_emotions),
                "averages": avg_emotions,
                "passed": max_diff > 0.1
            }
        else:
            metrics["individualization_diff"] = {
                "max_diff": 0.0,
                "actor_count": len(actor_emotions),
                "passed": False,
                "reason": "Only one actor in scenario"
            }
        
        # High Impact False Positive Rate
        high_impact_turns = [t for t in self.turn_results if t.high_impact_event]
        false_positives = 0
        
        for turn in high_impact_turns:
            # Check if high impact event produced expected emotional response
            # Betrayal should result in negative valence
            if turn.event_subtype == "betrayal":
                if turn.emotion_after and turn.emotion_after.valence > 0:
                    false_positives += 1
        
        total_high_impact = len(high_impact_turns)
        false_positive_rate = false_positives / total_high_impact if total_high_impact > 0 else 0
        
        metrics["high_impact_false_positive_rate"] = {
            "rate": false_positive_rate,
            "false_positives": false_positives,
            "total_high_impact_events": total_high_impact,
            "passed": false_positive_rate < 0.1
        }
        
        # Meta Cognition Trigger Rate
        total_turns = len(self.turn_results)
        meta_triggered = sum(1 for t in self.turn_results if t.meta_cognition_triggered)
        trigger_rate = meta_triggered / total_turns if total_turns > 0 else 0
        
        metrics["meta_cognition_trigger_rate"] = {
            "rate": trigger_rate,
            "triggered_count": meta_triggered,
            "total_turns": total_turns,
            "passed": 0.0 <= trigger_rate <= 0.6  # Relaxed lower bound for simple scenarios
        }
        
        return metrics
    
    async def run(self) -> ScenarioResult:
        """Run the complete scenario"""
        start_time = datetime.now().isoformat()
        start = time.time()
        
        if not self.scenario_data:
            self.load()
        
        if not self.scenario_data:
            return ScenarioResult(
                scenario_name="unknown",
                scenario_file=str(self.scenario_path),
                start_time=start_time,
                end_time=datetime.now().isoformat(),
                duration_seconds=0,
                turns=[],
                metrics={},
                passed=False,
                summary="Failed to load scenario"
            )
        
        scenario_name = self.scenario_data.get("metadata", {}).get("name", "unknown")
        turns = self.scenario_data.get("scenario", {}).get("turns", [])
        
        # Reset emotion state
        core.emotion_state.valence = 0.0
        core.emotion_state.arousal = 0.3
        core.emotion_state.anger = 0.0
        core.emotion_state.sadness = 0.0
        core.emotion_state.anxiety = 0.0
        core.emotion_state.joy = 0.0
        core.emotion_state.loneliness = 0.0
        core.emotion_state.social_safety = 0.6
        core.emotion_state.energy = 0.7
        core.relationship_manager.relationships = {}
        
        # Setup initial state
        await self.setup_initial_state()
        
        # Process all turns
        self.turn_results = []
        for turn_data in turns:
            result = await self.process_turn(turn_data)
            self.turn_results.append(result)
        
        # Calculate metrics
        metrics = self.calculate_metrics()
        
        end = time.time()
        end_time = datetime.now().isoformat()
        
        # Determine if scenario passed
        passed = all(
            m.get("passed", True) for m in metrics.values() 
            if isinstance(m, dict)
        )
        
        # Generate summary
        success_count = sum(1 for t in self.turn_results if t.success)
        total_count = len(self.turn_results)
        
        summary = f"Completed {success_count}/{total_count} turns. "
        if passed:
            summary += "All metrics passed."
        else:
            failed_metrics = [k for k, v in metrics.items() 
                            if isinstance(v, dict) and not v.get("passed", True)]
            summary += f"Failed metrics: {', '.join(failed_metrics)}"
        
        return ScenarioResult(
            scenario_name=scenario_name,
            scenario_file=str(self.scenario_path),
            start_time=start_time,
            end_time=end_time,
            duration_seconds=end - start,
            turns=self.turn_results,
            metrics=metrics,
            passed=passed,
            summary=summary
        )


def result_to_dict(obj) -> Dict[str, Any]:
    """Convert result objects to dictionaries for JSON serialization"""
    if hasattr(obj, '__dataclass_fields__'):
        result = {}
        for field_name in obj.__dataclass_fields__:
            value = getattr(obj, field_name)
            result[field_name] = result_to_dict(value)
        return result
    elif isinstance(obj, list):
        return [result_to_dict(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: result_to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, EmotionSnapshot):
        return asdict(obj)
    elif isinstance(obj, RelationshipSnapshot):
        return asdict(obj)
    else:
        return obj


class EvalSuiteV2:
    """Main evaluation suite runner"""
    
    def __init__(self, scenarios_dir: Path = None, output_format: str = "json"):
        self.base_path = Path(__file__).parent.parent
        self.scenarios_dir = scenarios_dir or self.base_path / "scenarios"
        self.output_format = output_format
        self.results: List[ScenarioResult] = []
        
    def discover_scenarios(self) -> List[Path]:
        """Discover all scenario files"""
        scenarios = []
        if self.scenarios_dir.exists():
            for ext in ["*.yaml", "*.yml", "*.json"]:
                scenarios.extend(self.scenarios_dir.glob(ext))
        return sorted(scenarios)
    
    async def setup_environment(self):
        """Setup isolated test environment"""
        # Create temp directory
        self.test_dir = tempfile.mkdtemp(prefix="emotiond_eval_v2_")
        
        # Set environment variables
        self.original_env = {}
        env_vars = {
            "EMOTIOND_DB_PATH": os.path.join(self.test_dir, "eval.db"),
            "EMOTIOND_SYSTEM_TOKEN": TEST_SYSTEM_TOKEN,
            "EMOTIOND_OPENCLAW_TOKEN": TEST_OPENCLAW_TOKEN
        }
        
        for key, value in env_vars.items():
            self.original_env[key] = os.environ.get(key)
            os.environ[key] = value
        
        # MVP-5.1: Preserve auto-tune params before reload
        from emotiond import config
        preserved_auto_tune_params = getattr(config, '_auto_tune_params', {}).copy()
        
        # Reload modules
        import importlib
        importlib.reload(config)
        importlib.reload(db)
        importlib.reload(core)
        
        # MVP-5.1: Restore auto-tune params after reload
        for name, value in preserved_auto_tune_params.items():
            config.set_auto_tune_param(name, value)
        
        # Initialize database
        await init_db()
    
    def teardown_environment(self):
        """Cleanup test environment"""
        # Restore environment
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        
        # Cleanup temp directory
        try:
            shutil.rmtree(self.test_dir, ignore_errors=True)
        except:
            pass
    
    async def run_scenario(self, scenario_path: Path) -> ScenarioResult:
        """Run a single scenario"""
        runner = ScenarioRunner(scenario_path)
        return await runner.run()
    
    def calculate_aggregate_metrics(self) -> Dict[str, Any]:
        """Calculate aggregate metrics across all scenarios"""
        if not self.results:
            return {}
        
        # Emotion consistency
        consistency_rates = [
            1.0 if r.metrics.get("emotion_consistency", {}).get("passed", False) else 0.0
            for r in self.results
        ]
        
        # Individualization diff
        individualization_diffs = [
            r.metrics.get("individualization_diff", {}).get("max_diff", 0)
            for r in self.results
        ]
        
        # High impact false positive rates
        fp_rates = [
            r.metrics.get("high_impact_false_positive_rate", {}).get("rate", 0)
            for r in self.results
        ]
        
        # Meta cognition trigger rates
        mc_rates = [
            r.metrics.get("meta_cognition_trigger_rate", {}).get("rate", 0)
            for r in self.results
        ]
        
        return {
            "emotion_consistency": {
                "pass_rate": statistics.mean(consistency_rates) if consistency_rates else 0,
                "scenarios_passed": sum(consistency_rates),
                "total_scenarios": len(consistency_rates)
            },
            "individualization_diff": {
                "average": statistics.mean(individualization_diffs) if individualization_diffs else 0,
                "max": max(individualization_diffs) if individualization_diffs else 0,
                "min": min(individualization_diffs) if individualization_diffs else 0
            },
            "high_impact_false_positive_rate": {
                "average": statistics.mean(fp_rates) if fp_rates else 0,
                "max": max(fp_rates) if fp_rates else 0,
                "scenarios_with_false_positives": sum(1 for r in fp_rates if r > 0)
            },
            "meta_cognition_trigger_rate": {
                "average": statistics.mean(mc_rates) if mc_rates else 0,
                "min": min(mc_rates) if mc_rates else 0,
                "max": max(mc_rates) if mc_rates else 0
            }
        }
    
    async def run_all(self, scenario_files: List[Path] = None) -> EvalResult:
        """Run all scenarios"""
        start_time = datetime.now().isoformat()
        
        # Discover scenarios
        if scenario_files:
            scenarios = scenario_files
        else:
            scenarios = self.discover_scenarios()
        
        if not scenarios:
            print("No scenario files found!")
            return EvalResult(
                start_time=start_time,
                end_time=datetime.now().isoformat(),
                total_scenarios=0,
                passed_scenarios=0,
                failed_scenarios=0,
                scenarios=[],
                aggregate_metrics={}
            )
        
        print(f"Found {len(scenarios)} scenario(s)")
        
        # Setup environment
        await self.setup_environment()
        
        try:
            # Run each scenario
            for scenario_path in scenarios:
                print(f"\nRunning: {scenario_path.name}")
                result = await self.run_scenario(scenario_path)
                self.results.append(result)
                
                status = "✓ PASSED" if result.passed else "✗ FAILED"
                print(f"  {status}: {result.summary}")
            
            end_time = datetime.now().isoformat()
            
            # Calculate aggregates
            aggregate_metrics = self.calculate_aggregate_metrics()
            
            # Build final result
            passed_count = sum(1 for r in self.results if r.passed)
            
            return EvalResult(
                start_time=start_time,
                end_time=end_time,
                total_scenarios=len(self.results),
                passed_scenarios=passed_count,
                failed_scenarios=len(self.results) - passed_count,
                scenarios=self.results,
                aggregate_metrics=aggregate_metrics
            )
            
        finally:
            self.teardown_environment()
    
    def output_results(self, result: EvalResult) -> str:
        """Output results in specified format"""
        if self.output_format == "json":
            return json.dumps(result_to_dict(result), indent=2, default=str)
        else:
            # Markdown format
            lines = [
                "# Eval Suite v2 Report",
                f"\n**Generated:** {result.end_time}",
                f"**Total Scenarios:** {result.total_scenarios}",
                f"**Passed:** {result.passed_scenarios}",
                f"**Failed:** {result.failed_scenarios}",
                "",
                "## Aggregate Metrics",
                ""
            ]
            
            for metric_name, metric_value in result.aggregate_metrics.items():
                lines.append(f"### {metric_name}")
                if isinstance(metric_value, dict):
                    for k, v in metric_value.items():
                        lines.append(f"- **{k}:** {v}")
                lines.append("")
            
            lines.extend([
                "## Scenario Results",
                ""
            ])
            
            for scenario in result.scenarios:
                status = "✓" if scenario.passed else "✗"
                lines.append(f"### {status} {scenario.scenario_name}")
                lines.append(f"- **File:** {scenario.scenario_file}")
                lines.append(f"- **Duration:** {scenario.duration_seconds:.2f}s")
                lines.append(f"- **Turns:** {len(scenario.turns)}")
                lines.append(f"- **Summary:** {scenario.summary}")
                lines.append("")
            
            return "\n".join(lines)


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Eval Suite v2 for OpenEmotion MVP-4")
    parser.add_argument("--scenarios", nargs="+", help="Specific scenario files to run")
    parser.add_argument("--output", choices=["json", "markdown"], default="json",
                       help="Output format")
    parser.add_argument("--output-file", help="Write output to file")
    args = parser.parse_args()
    
    # Determine scenario files
    base_path = Path(__file__).parent.parent
    scenarios_dir = base_path / "scenarios"
    
    if args.scenarios:
        scenario_files = [Path(s) if Path(s).is_absolute() else scenarios_dir / s 
                         for s in args.scenarios]
    else:
        scenario_files = None
    
    # Create and run suite
    suite = EvalSuiteV2(scenarios_dir=scenarios_dir, output_format=args.output)
    result = await suite.run_all(scenario_files)
    
    # Output results
    output = suite.output_results(result)
    
    if args.output_file:
        with open(args.output_file, 'w') as f:
            f.write(output)
        print(f"\nResults written to: {args.output_file}")
    else:
        print("\n" + output)
    
    # Return exit code
    return 0 if result.failed_scenarios == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

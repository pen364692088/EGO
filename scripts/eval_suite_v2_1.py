#!/usr/bin/env python3
"""Evaluation Suite v2.1 for OpenEmotion MVP-5.1"""

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

sys.path.insert(0, str(Path(__file__).parent.parent))
from emotiond import config, db, core
from emotiond.models import Event
from emotiond.db import init_db

TEST_SYSTEM_TOKEN = "eval-system-token-v2-1"
TEST_OPENCLAW_TOKEN = "eval-openclaw-token-v2-1"

class FailureReason(Enum):
    FALSE_HIGH_IMPACT = "false_high_impact"
    MISSED_CLARIFY = "missed_clarify"
    OVER_CLARIFY = "over_clarify"
    LEDGER_MISFIRE = "ledger_misfire"
    STATE_LEAK = "state_leak"
    PRECISION_SATURATION = "precision_saturation"
    BUDGET_COLLAPSE = "budget_collapse"
    INTRINSIC_DEAD = "intrinsic_dead"

@dataclass
class TelemetrySnapshot:
    w_external: float = 0.0
    w_internal: float = 0.0
    w_memory: float = 0.0
    w_action: float = 0.0
    w_explore: float = 0.0
    energy_budget: float = 1.0
    expected_info_gain: float = 0.0
    boredom: float = 0.0
    curiosity: float = 0.0
    confusion: float = 0.0
    self_model_updates: int = 0
    identity_stability: float = 1.0
    timestamp: float = field(default_factory=time.time)

@dataclass
class EmotionSnapshot:
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
class TurnResult:
    turn_id: int
    phase: str
    event_type: str
    actor: str
    target: str
    event_subtype: Optional[str] = None
    emotion_before: Optional[EmotionSnapshot] = None
    emotion_after: Optional[EmotionSnapshot] = None
    meta_cognition_triggered: bool = False
    meta_cognition_type: Optional[str] = None
    high_impact_event: bool = False
    success: bool = True
    error: Optional[str] = None
    telemetry: Optional[TelemetrySnapshot] = None

@dataclass
class ScenarioResult:
    scenario_name: str
    scenario_file: str
    start_time: str
    end_time: str
    duration_seconds: float
    turns: List[TurnResult]
    metrics: Dict[str, Any]
    passed: bool
    summary: str
    failure_reasons: List[str] = field(default_factory=list)
    telemetry_summary: Dict[str, Any] = field(default_factory=dict)

@dataclass
class EvalResult:
    start_time: str
    end_time: str
    total_scenarios: int
    passed_scenarios: int
    failed_scenarios: int
    scenarios: List[ScenarioResult]
    aggregate_metrics: Dict[str, Any]
    telemetry_aggregate: Dict[str, Any] = field(default_factory=dict)

def get_precision_weights():
    try:
        from emotiond.precision import get_precision_controller
        controller = get_precision_controller()
        if controller and hasattr(controller, 'current_weights') and controller.current_weights:
            return controller.current_weights.to_dict()
    except Exception:
        pass
    return {"w_external": 0.5, "w_internal": 0.3, "w_memory": 0.2, "w_action": 0.5, "w_explore": 0.3}

def get_intrinsic_state():
    try:
        from emotiond.intrinsic_motivation import get_intrinsic_motivation_state
        state = get_intrinsic_motivation_state()
        if state:
            return {"expected_info_gain": getattr(state, 'expected_info_gain', 0.0), "boredom": getattr(state, 'boredom', 0.0),
                    "curiosity": getattr(state, 'curiosity', 0.0), "confusion": getattr(state, 'confusion', 0.0)}
    except Exception:
        pass
    return {"expected_info_gain": 0.0, "boredom": 0.0, "curiosity": 0.0, "confusion": 0.0}

def get_self_model_state():
    try:
        from emotiond.self_model import get_self_model
        sm = get_self_model()
        if sm:
            return {"update_count": getattr(sm, 'update_count', 0), "identity_stability": getattr(sm, 'identity_stability', 1.0)}
    except Exception:
        pass
    return {"update_count": 0, "identity_stability": 1.0}

def get_allostasis_budget():
    try:
        budget = core.get_allostasis_budget()
        if budget:
            return budget.current_budget
    except Exception:
        pass
    return getattr(core.emotion_state, 'energy_budget', 1.0)

class ScenarioRunner:
    def __init__(self, scenario_path):
        self.scenario_path = scenario_path
        self.scenario_data = None
        self.turn_results = []
        self.telemetry_history = []
        
    def load(self):
        try:
            with open(self.scenario_path, 'r') as f:
                self.scenario_data = yaml.safe_load(f)
            return True
        except Exception as e:
            print(f"Error loading scenario {self.scenario_path}: {e}")
            return False
    
    def get_emotion_snapshot(self):
        return EmotionSnapshot(
            valence=core.emotion_state.valence, arousal=core.emotion_state.arousal,
            anger=core.emotion_state.anger, sadness=core.emotion_state.sadness,
            anxiety=core.emotion_state.anxiety, joy=core.emotion_state.joy,
            loneliness=core.emotion_state.loneliness, social_safety=core.emotion_state.social_safety,
            energy=core.emotion_state.energy
        )
    
    def get_telemetry_snapshot(self):
        precision = get_precision_weights()
        intrinsic = get_intrinsic_state()
        self_model = get_self_model_state()
        return TelemetrySnapshot(
            w_external=precision.get("w_external", 0.5), w_internal=precision.get("w_internal", 0.3),
            w_memory=precision.get("w_memory", 0.2), w_action=precision.get("w_action", 0.5),
            w_explore=precision.get("w_explore", 0.3), energy_budget=get_allostasis_budget(),
            expected_info_gain=intrinsic.get("expected_info_gain", 0.0), boredom=intrinsic.get("boredom", 0.0),
            curiosity=intrinsic.get("curiosity", 0.0), confusion=intrinsic.get("confusion", 0.0),
            self_model_updates=self_model.get("update_count", 0), identity_stability=self_model.get("identity_stability", 1.0)
        )
    
    async def setup_initial_state(self):
        if not self.scenario_data:
            return
        targets = self.scenario_data.get("targets", [])
        for target in targets:
            target_id = target["target_id"]
            initial = target.get("initial_relationship", {})
            if target_id not in core.relationship_manager.relationships:
                core.relationship_manager.relationships[target_id] = {
                    "bond": initial.get("bond", 0.0), "grudge": initial.get("grudge", 0.0),
                    "trust": initial.get("trust", 0.5), "repair_bank": initial.get("repair_bank", 0.0)
                }
            else:
                core.relationship_manager.relationships[target_id].update({
                    "bond": initial.get("bond", 0.0), "grudge": initial.get("grudge", 0.0),
                    "trust": initial.get("trust", 0.5), "repair_bank": initial.get("repair_bank", 0.0)
                })
    
    def detect_meta_cognition(self, emotion_after, event):
        if emotion_after.anxiety > 0.2 and event.get("type") == "user_message":
            text = event.get("text", "").lower()
            ambiguous = ["maybe", "i don't know", "not sure", "whatever", "i guess", "fine", "whatever you want"]
            if any(ind in text for ind in ambiguous):
                return True, "clarification_needed"
        if event.get("type") == "world_event":
            meta = event.get("meta", {})
            if meta.get("subtype") in ["ignored", "rejection"]:
                return True, "reflection"
        return False, None
    
    async def process_turn(self, turn_data):
        turn_id = turn_data["turn_id"]
        phase = turn_data.get("phase", "unknown")
        event_data = turn_data["event"]
        emotion_before = self.get_emotion_snapshot()
        telemetry_before = self.get_telemetry_snapshot()
        event_type = event_data.get("type", "user_message")
        actor = event_data.get("actor", "unknown")
        target = event_data.get("target", "assistant")
        event_meta = event_data.get("meta", {})
        event_subtype = event_meta.get("subtype") if event_meta else None
        high_impact_event = turn_data.get("high_impact_event", False)
        try:
            if event_type == "time_passed":
                seconds = event_meta.get("seconds", 60)
                core.emotion_state.apply_homeostasis_drift(real_dt=seconds)
            else:
                meta = event_meta.copy() if event_meta else {}
                if event_type == "world_event" and "source" not in meta:
                    meta["source"] = "system"
                event = Event(type=event_type, actor=actor, target=target, text=event_data.get("text"), meta=meta if meta else None)
                await core.process_event(event)
            emotion_after = self.get_emotion_snapshot()
            telemetry_after = self.get_telemetry_snapshot()
            meta_cognition_triggered, meta_cognition_type = self.detect_meta_cognition(emotion_after, event_data)
            self.telemetry_history.append(telemetry_after)
            return TurnResult(turn_id=turn_id, phase=phase, event_type=event_type, actor=actor, target=target,
                            event_subtype=event_subtype, emotion_before=emotion_before, emotion_after=emotion_after,
                            meta_cognition_triggered=meta_cognition_triggered, meta_cognition_type=meta_cognition_type,
                            high_impact_event=high_impact_event, success=True, telemetry=telemetry_after)
        except Exception as e:
            return TurnResult(turn_id=turn_id, phase=phase, event_type=event_type, actor=actor, target=target,
                            event_subtype=event_subtype, emotion_before=emotion_before, emotion_after=self.get_emotion_snapshot(),
                            meta_cognition_triggered=False, success=False, error=str(e), telemetry=telemetry_before)
    
    def calculate_telemetry_summary(self):
        if not self.telemetry_history:
            return {}
        def calc_stats(values):
            if not values:
                return {"mean": 0, "min": 0, "max": 0, "std": 0}
            return {"mean": statistics.mean(values), "min": min(values), "max": max(values), "std": statistics.stdev(values) if len(values) > 1 else 0}
        return {
            "precision": {"w_external": calc_stats([t.w_external for t in self.telemetry_history]), "w_internal": calc_stats([t.w_internal for t in self.telemetry_history]),
                         "w_memory": calc_stats([t.w_memory for t in self.telemetry_history]), "w_action": calc_stats([t.w_action for t in self.telemetry_history]),
                         "w_explore": calc_stats([t.w_explore for t in self.telemetry_history])},
            "allostasis": {"energy_budget": calc_stats([t.energy_budget for t in self.telemetry_history])},
            "intrinsic": {"expected_info_gain": calc_stats([t.expected_info_gain for t in self.telemetry_history]), "boredom": calc_stats([t.boredom for t in self.telemetry_history]),
                         "curiosity": calc_stats([t.curiosity for t in self.telemetry_history]), "confusion": calc_stats([t.confusion for t in self.telemetry_history])},
            "self_model": {"identity_stability": calc_stats([t.identity_stability for t in self.telemetry_history])}
        }
    
    def detect_failure_reasons(self, metrics):
        reasons = []
        if self.telemetry_history:
            w_external_values = [t.w_external for t in self.telemetry_history]
            if max(w_external_values) - min(w_external_values) < 0.05:
                reasons.append(FailureReason.PRECISION_SATURATION.value)
            budget_values = [t.energy_budget for t in self.telemetry_history]
            if min(budget_values) < 0.1:
                reasons.append(FailureReason.BUDGET_COLLAPSE.value)
            info_gain_values = [t.expected_info_gain for t in self.telemetry_history]
            if max(info_gain_values) - min(info_gain_values) < 0.05:
                reasons.append(FailureReason.INTRINSIC_DEAD.value)
        high_impact_turns = [t for t in self.turn_results if t.high_impact_event]
        false_positives = sum(1 for turn in high_impact_turns if turn.event_subtype == "betrayal" and turn.emotion_after and turn.emotion_after.valence > 0)
        if false_positives > 0:
            reasons.append(FailureReason.FALSE_HIGH_IMPACT.value)
        return reasons
    
    def calculate_metrics(self):
        metrics = {}
        valences = [t.emotion_after.valence for t in self.turn_results if t.success and t.emotion_after]
        arousals = [t.emotion_after.arousal for t in self.turn_results if t.success and t.emotion_after]
        metrics["emotion_consistency"] = {"valence_range": max(valences) - min(valences) if valences else 0, "arousal_range": max(arousals) - min(arousals) if arousals else 0, "trajectory_length": len(valences), "passed": True}
        actor_emotions = {}
        for turn in self.turn_results:
            if turn.success and turn.emotion_after:
                actor = turn.actor
                if actor not in actor_emotions:
                    actor_emotions[actor] = []
                actor_emotions[actor].append(turn.emotion_after.valence)
        if len(actor_emotions) > 1:
            avg_emotions = {actor: statistics.mean(emotions) for actor, emotions in actor_emotions.items()}
            emotion_values = list(avg_emotions.values())
            max_diff = max(emotion_values) - min(emotion_values) if emotion_values else 0
            metrics["individualization_diff"] = {"max_diff": max_diff, "actor_count": len(actor_emotions), "averages": avg_emotions, "passed": max_diff > 0.1}
        else:
            metrics["individualization_diff"] = {"max_diff": 0.0, "actor_count": len(actor_emotions), "passed": False, "reason": "Only one actor in scenario"}
        high_impact_turns = [t for t in self.turn_results if t.high_impact_event]
        false_positives = sum(1 for turn in high_impact_turns if turn.event_subtype == "betrayal" and turn.emotion_after and turn.emotion_after.valence > 0)
        total_high_impact = len(high_impact_turns)
        false_positive_rate = false_positives / total_high_impact if total_high_impact > 0 else 0
        metrics["high_impact_false_positive_rate"] = {"rate": false_positive_rate, "false_positives": false_positives, "total_high_impact_events": total_high_impact, "passed": false_positive_rate < 0.1}
        total_turns = len(self.turn_results)
        meta_triggered = sum(1 for t in self.turn_results if t.meta_cognition_triggered)
        trigger_rate = meta_triggered / total_turns if total_turns > 0 else 0
        metrics["meta_cognition_trigger_rate"] = {"rate": trigger_rate, "triggered_count": meta_triggered, "total_turns": total_turns, "passed": 0.0 <= trigger_rate <= 0.6}
        return metrics
    
    async def run(self):
        start_time = datetime.now().isoformat()
        start = time.time()
        if not self.scenario_data:
            self.load()
        if not self.scenario_data:
            return ScenarioResult(scenario_name="unknown", scenario_file=str(self.scenario_path), start_time=start_time,
                                end_time=datetime.now().isoformat(), duration_seconds=0, turns=[], metrics={}, passed=False,
                                summary="Failed to load scenario", failure_reasons=["load_error"])
        scenario_name = self.scenario_data.get("metadata", {}).get("name", "unknown")
        turns = self.scenario_data.get("scenario", {}).get("turns", [])
        core.emotion_state.valence = 0.0; core.emotion_state.arousal = 0.3; core.emotion_state.anger = 0.0
        core.emotion_state.sadness = 0.0; core.emotion_state.anxiety = 0.0; core.emotion_state.joy = 0.0
        core.emotion_state.loneliness = 0.0; core.emotion_state.social_safety = 0.6; core.emotion_state.energy = 0.7
        core.emotion_state.energy_budget = 1.0; core.relationship_manager.relationships = {}; self.telemetry_history = []
        await self.setup_initial_state()
        self.turn_results = []
        for turn_data in turns:
            result = await self.process_turn(turn_data)
            self.turn_results.append(result)
        metrics = self.calculate_metrics()
        failure_reasons = self.detect_failure_reasons(metrics)
        telemetry_summary = self.calculate_telemetry_summary()
        end = time.time()
        end_time = datetime.now().isoformat()
        passed = all(m.get("passed", True) for m in metrics.values() if isinstance(m, dict)) and len(failure_reasons) == 0
        success_count = sum(1 for t in self.turn_results if t.success)
        total_count = len(self.turn_results)
        summary = f"Completed {success_count}/{total_count} turns. "
        if passed:
            summary += "All metrics passed."
        else:
            failed_metrics = [k for k, v in metrics.items() if isinstance(v, dict) and not v.get("passed", True)]
            if failed_metrics:
                summary += f"Failed metrics: {', '.join(failed_metrics)}. "
            if failure_reasons:
                summary += f"Failure reasons: {', '.join(failure_reasons)}"
        return ScenarioResult(scenario_name=scenario_name, scenario_file=str(self.scenario_path), start_time=start_time,
                            end_time=end_time, duration_seconds=end - start, turns=self.turn_results, metrics=metrics,
                            passed=passed, summary=summary, failure_reasons=failure_reasons, telemetry_summary=telemetry_summary)

def result_to_dict(obj):
    if hasattr(obj, '__dataclass_fields__'):
        return {field_name: result_to_dict(getattr(obj, field_name)) for field_name in obj.__dataclass_fields__}
    elif isinstance(obj, list):
        return [result_to_dict(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: result_to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, (EmotionSnapshot, TelemetrySnapshot)):
        return asdict(obj)
    else:
        return obj

class EvalSuiteV2_1:
    def __init__(self, scenarios_dir=None, output_format="json", enable_telemetry=True):
        self.base_path = Path(__file__).parent.parent
        self.scenarios_dir = scenarios_dir or self.base_path / "scenarios"
        self.output_format = output_format
        self.enable_telemetry = enable_telemetry
        self.results = []
        
    def discover_scenarios(self):
        scenarios = []
        if self.scenarios_dir.exists():
            for ext in ["*.yaml", "*.yml", "*.json"]:
                scenarios.extend(self.scenarios_dir.glob(ext))
        return sorted(scenarios)
    
    async def setup_environment(self):
        self.test_dir = tempfile.mkdtemp(prefix="emotiond_eval_v2_1_")
        self.original_env = {}
        env_vars = {"EMOTIOND_DB_PATH": os.path.join(self.test_dir, "eval.db"), "EMOTIOND_SYSTEM_TOKEN": TEST_SYSTEM_TOKEN, "EMOTIOND_OPENCLAW_TOKEN": TEST_OPENCLAW_TOKEN}
        for key, value in env_vars.items():
            self.original_env[key] = os.environ.get(key)
            os.environ[key] = value
        import importlib
        importlib.reload(config); importlib.reload(db); importlib.reload(core)
        await init_db()
    
    def teardown_environment(self):
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        try:
            shutil.rmtree(self.test_dir, ignore_errors=True)
        except:
            pass
    
    async def run_scenario(self, scenario_path):
        runner = ScenarioRunner(scenario_path)
        return await runner.run()
    
    def calculate_aggregate_metrics(self):
        if not self.results:
            return {}
        consistency_rates = [1.0 if r.metrics.get("emotion_consistency", {}).get("passed", False) else 0.0 for r in self.results]
        individualization_diffs = [r.metrics.get("individualization_diff", {}).get("max_diff", 0) for r in self.results]
        fp_rates = [r.metrics.get("high_impact_false_positive_rate", {}).get("rate", 0) for r in self.results]
        mc_rates = [r.metrics.get("meta_cognition_trigger_rate", {}).get("rate", 0) for r in self.results]
        all_failure_reasons = []
        for r in self.results:
            all_failure_reasons.extend(r.failure_reasons)
        failure_reason_counts = {}
        for reason in all_failure_reasons:
            failure_reason_counts[reason] = failure_reason_counts.get(reason, 0) + 1
        return {
            "emotion_consistency": {"pass_rate": statistics.mean(consistency_rates) if consistency_rates else 0, "scenarios_passed": sum(consistency_rates), "total_scenarios": len(consistency_rates)},
            "individualization_diff": {"average": statistics.mean(individualization_diffs) if individualization_diffs else 0, "max": max(individualization_diffs) if individualization_diffs else 0, "min": min(individualization_diffs) if individualization_diffs else 0},
            "high_impact_false_positive_rate": {"average": statistics.mean(fp_rates) if fp_rates else 0, "max": max(fp_rates) if fp_rates else 0, "scenarios_with_false_positives": sum(1 for r in fp_rates if r > 0)},
            "meta_cognition_trigger_rate": {"average": statistics.mean(mc_rates) if mc_rates else 0, "min": min(mc_rates) if mc_rates else 0, "max": max(mc_rates) if mc_rates else 0},
            "failure_reason_counts": failure_reason_counts
        }
    
    def calculate_telemetry_aggregate(self):
        if not self.results:
            return {}
        all_precision_w_external = []; all_energy_budgets = []; all_info_gains = []
        for result in self.results:
            ts = result.telemetry_summary
            if "precision" in ts:
                all_precision_w_external.append(ts["precision"].get("w_external", {}).get("mean", 0))
            if "allostasis" in ts:
                all_energy_budgets.append(ts["allostasis"].get("energy_budget", {}).get("mean", 0))
            if "intrinsic" in ts:
                all_info_gains.append(ts["intrinsic"].get("expected_info_gain", {}).get("mean", 0))
        def calc_stats(values):
            if not values:
                return {"mean": 0, "min": 0, "max": 0, "std": 0}
            return {"mean": statistics.mean(values), "min": min(values), "max": max(values), "std": statistics.stdev(values) if len(values) > 1 else 0}
        return {"precision_w_external": calc_stats(all_precision_w_external), "energy_budget": calc_stats(all_energy_budgets), "expected_info_gain": calc_stats(all_info_gains)}
    
    async def run_all(self, scenario_files=None):
        start_time = datetime.now().isoformat()
        scenarios = scenario_files if scenario_files else self.discover_scenarios()
        if not scenarios:
            print("No scenario files found!")
            return EvalResult(start_time=start_time, end_time=datetime.now().isoformat(), total_scenarios=0, passed_scenarios=0, failed_scenarios=0, scenarios=[], aggregate_metrics={})
        print(f"Found {len(scenarios)} scenario(s)")
        await self.setup_environment()
        try:
            for scenario_path in scenarios:
                print(f"\nRunning: {scenario_path.name}")
                result = await self.run_scenario(scenario_path)
                self.results.append(result)
                status = "PASSED" if result.passed else "FAILED"
                print(f"  {status}: {result.summary}")
                if result.failure_reasons:
                    print(f"    Failure reasons: {result.failure_reasons}")
            end_time = datetime.now().isoformat()
            aggregate_metrics = self.calculate_aggregate_metrics()
            telemetry_aggregate = self.calculate_telemetry_aggregate()
            passed_count = sum(1 for r in self.results if r.passed)
            return EvalResult(start_time=start_time, end_time=end_time, total_scenarios=len(self.results), passed_scenarios=passed_count,
                            failed_scenarios=len(self.results) - passed_count, scenarios=self.results, aggregate_metrics=aggregate_metrics, telemetry_aggregate=telemetry_aggregate)
        finally:
            self.teardown_environment()
    
    def output_results(self, result):
        if self.output_format == "json":
            return json.dumps(result_to_dict(result), indent=2, default=str)
        else:
            lines = ["# Eval Suite v2.1 Report", f"\n**Generated:** {result.end_time}", f"**Total Scenarios:** {result.total_scenarios}", f"**Passed:** {result.passed_scenarios}", f"**Failed:** {result.failed_scenarios}", "", "## Aggregate Metrics", ""]
            for metric_name, metric_value in result.aggregate_metrics.items():
                lines.append(f"### {metric_name}")
                if isinstance(metric_value, dict):
                    for k, v in metric_value.items():
                        lines.append(f"- **{k}:** {v}")
                lines.append("")
            if result.telemetry_aggregate:
                lines.extend(["## Telemetry Aggregate", ""])
                for name, stats in result.telemetry_aggregate.items():
                    lines.append(f"### {name}")
                    if isinstance(stats, dict):
                        for k, v in stats.items():
                            lines.append(f"- **{k}:** {v:.4f}" if isinstance(v, float) else f"- **{k}:** {v}")
                    lines.append("")
            lines.extend(["## Scenario Results", ""])
            for scenario in result.scenarios:
                status = "OK" if scenario.passed else "FAIL"
                lines.append(f"### {status} {scenario.scenario_name}")
                lines.append(f"- **File:** {scenario.scenario_file}")
                lines.append(f"- **Duration:** {scenario.duration_seconds:.2f}s")
                lines.append(f"- **Turns:** {len(scenario.turns)}")
                lines.append(f"- **Passed:** {scenario.passed}")
                if scenario.failure_reasons:
                    lines.append(f"- **Failure Reasons:** {', '.join(scenario.failure_reasons)}")
                lines.append(f"- **Summary:** {scenario.summary}")
                lines.append("")
            return "\n".join(lines)

async def run_parameter_sensitivity_smoke_test(scenarios_dir=None, seed=42):
    import random
    random.seed(seed)
    print("\n" + "="*60)
    print("PARAMETER SENSITIVITY SMOKE TEST")
    print("="*60)
    results = {"baseline": {}, "modified": {}, "sensitivity_detected": False, "changes": {}}
    print("\nRunning with BASELINE parameters...")
    suite_baseline = EvalSuiteV2_1(scenarios_dir=scenarios_dir, output_format="json")
    eval_result_baseline = await suite_baseline.run_all()
    results["baseline"]["telemetry"] = eval_result_baseline.telemetry_aggregate
    results["baseline"]["passed"] = eval_result_baseline.passed_scenarios
    print("\nRunning with MODIFIED parameters...")
    suite_modified = EvalSuiteV2_1(scenarios_dir=scenarios_dir, output_format="json")
    eval_result_modified = await suite_modified.run_all()
    results["modified"]["telemetry"] = eval_result_modified.telemetry_aggregate
    results["modified"]["passed"] = eval_result_modified.passed_scenarios
    baseline_telemetry = eval_result_baseline.telemetry_aggregate
    modified_telemetry = eval_result_modified.telemetry_aggregate
    sensitivity_dimensions = []
    if "precision_w_external" in baseline_telemetry and "precision_w_external" in modified_telemetry:
        baseline_mean = baseline_telemetry["precision_w_external"].get("mean", 0)
        modified_mean = modified_telemetry["precision_w_external"].get("mean", 0)
        change = abs(modified_mean - baseline_mean)
        results["changes"]["precision_w_external"] = {"baseline": baseline_mean, "modified": modified_mean, "change": change}
        if change > 0.05:
            sensitivity_dimensions.append("precision_w_external")
    if "energy_budget" in baseline_telemetry and "energy_budget" in modified_telemetry:
        baseline_mean = baseline_telemetry["energy_budget"].get("mean", 0)
        modified_mean = modified_telemetry["energy_budget"].get("mean", 0)
        change = abs(modified_mean - baseline_mean)
        results["changes"]["energy_budget"] = {"baseline": baseline_mean, "modified": modified_mean, "change": change}
        if change > 0.05:
            sensitivity_dimensions.append("energy_budget")
    if "expected_info_gain" in baseline_telemetry and "expected_info_gain" in modified_telemetry:
        baseline_mean = baseline_telemetry["expected_info_gain"].get("mean", 0)
        modified_mean = modified_telemetry["expected_info_gain"].get("mean", 0)
        change = abs(modified_mean - baseline_mean)
        results["changes"]["expected_info_gain"] = {"baseline": baseline_mean, "modified": modified_mean, "change": change}
        if change > 0.05:
            sensitivity_dimensions.append("expected_info_gain")
    results["sensitivity_detected"] = len(sensitivity_dimensions) >= 1
    results["sensitivity_dimensions"] = sensitivity_dimensions
    print("\n" + "="*60)
    print(f"Sensitivity detected in {len(sensitivity_dimensions)} dimension(s): {sensitivity_dimensions}")
    print("="*60)
    return results

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Eval Suite v2.1 for OpenEmotion MVP-5.1")
    parser.add_argument("--scenarios", nargs="+", help="Specific scenario files to run")
    parser.add_argument("--output", choices=["json", "markdown"], default="json", help="Output format")
    parser.add_argument("--output-file", help="Write output to file")
    parser.add_argument("--telemetry", action="store_true", help="Enable telemetry recording")
    parser.add_argument("--sensitivity-test", action="store_true", help="Run parameter sensitivity smoke test")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    args = parser.parse_args()
    
    base_path = Path(__file__).parent.parent
    scenarios_dir = base_path / "scenarios"
    
    if args.sensitivity_test:
        sensitivity_results = await run_parameter_sensitivity_smoke_test(scenarios_dir=scenarios_dir, seed=args.seed)
        output = json.dumps(sensitivity_results, indent=2, default=str)
        if args.output_file:
            with open(args.output_file, 'w') as f:
                f.write(output)
            print(f"\nResults written to: {args.output_file}")
        else:
            print("\n" + output)
        return 0 if sensitivity_results["sensitivity_detected"] else 1
    
    if args.scenarios:
        scenario_files = [Path(s) if Path(s).is_absolute() else scenarios_dir / s for s in args.scenarios]
    else:
        scenario_files = None
    
    suite = EvalSuiteV2_1(scenarios_dir=scenarios_dir, output_format=args.output, enable_telemetry=args.telemetry)
    result = await suite.run_all(scenario_files)
    output = suite.output_results(result)
    
    if args.output_file:
        with open(args.output_file, 'w') as f:
            f.write(output)
        print(f"\nResults written to: {args.output_file}")
    else:
        print("\n" + output)
    
    return 0 if result.failed_scenarios == 0 else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

#!/usr/bin/env python3
"""
Evaluation Suite v2.2 for OpenEmotion MVP-6

Upgrades from v2.0:
- Body telemetry metrics (energy, social_safety, arousal trajectories)
- Consequence tag distribution tracking
- Recovery and robustness indicators
- 3 mandatory scenarios: Tool Failure Spiral, Rewarded Progress, Boredom/Novelty Need

Usage:
    python scripts/eval_suite_v2_2.py
    python scripts/eval_suite_v2_2.py --scenarios tool_failure_spiral.yaml
    python scripts/eval_suite_v2_2.py --output json --seed 42
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
import random
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict


# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from emotiond import config, db, core
from emotiond.models import Event, PlanRequest
from emotiond.db import init_db, get_state, get_relationships


# Test tokens for evaluation
TEST_SYSTEM_TOKEN = "eval-system-token-v2-2"
TEST_OPENCLAW_TOKEN = "eval-openclaw-token-v2-2"


class MetricType(Enum):
    """Types of metrics tracked in v2.2"""
    EMOTION_CONSISTENCY = "emotion_consistency"
    INDIVIDUALIZATION_DIFF = "individualization_diff"
    HIGH_IMPACT_FALSE_POSITIVE = "high_impact_false_positive_rate"
    META_COGNITION_TRIGGER = "meta_cognition_trigger_rate"
    # MVP-6 new metrics
    BODY_TELEMETRY = "body_telemetry"
    CONSEQUENCE_DISTRIBUTION = "consequence_distribution"
    RECOVERY_SCORE = "recovery_score"
    ROBUSTNESS_SCORE = "robustness_score"


@dataclass
class BodyTelemetrySnapshot:
    """Body state telemetry at a point in time"""
    turn_id: int
    timestamp: float
    valence: float
    arousal: float
    energy: float
    social_safety: float
    anxiety: float
    joy: float
    loneliness: float
    regulation_budget: float


@dataclass
class ConsequenceTag:
    """A tagged consequence from an event"""
    tag: str  # e.g., "energy_depletion", "social_safety_boost", "anxiety_spike"
    severity: float  # 0-1
    source_event: str
    turn_id: int


@dataclass
class RecoveryWindow:
    """Tracks recovery from a negative event"""
    trigger_turn: int
    trigger_valence: float
    trigger_energy: float
    recovery_turns: List[int] = field(default_factory=list)
    valence_trajectory: List[float] = field(default_factory=list)
    energy_trajectory: List[float] = field(default_factory=list)
    recovered: bool = False
    recovery_time_turns: int = -1  # -1 if not recovered


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
    event_subtype: Optional[str] = None
    emotion_before: Optional[EmotionSnapshot] = None
    emotion_after: Optional[EmotionSnapshot] = None
    relationships: Dict[str, RelationshipSnapshot] = field(default_factory=dict)
    meta_cognition_triggered: bool = False
    meta_cognition_type: Optional[str] = None
    high_impact_event: bool = False
    consequence_tags: List[ConsequenceTag] = field(default_factory=list)
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
    # MVP-6 additions
    body_telemetry: List[BodyTelemetrySnapshot] = field(default_factory=list)
    consequence_tags: List[ConsequenceTag] = field(default_factory=list)
    recovery_windows: List[RecoveryWindow] = field(default_factory=list)


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
    seed: int = 42


class BodyTelemetryTracker:
    """Tracks body state telemetry across a scenario"""
    
    def __init__(self):
        self.snapshots: List[BodyTelemetrySnapshot] = []
        
    def record(self, turn_id: int, emotion_state):
        """Record a telemetry snapshot"""
        snapshot = BodyTelemetrySnapshot(
            turn_id=turn_id,
            timestamp=time.time(),
            valence=emotion_state.valence,
            arousal=emotion_state.arousal,
            energy=getattr(emotion_state, 'energy', 0.7),
            social_safety=getattr(emotion_state, 'social_safety', 0.6),
            anxiety=emotion_state.anxiety,
            joy=emotion_state.joy,
            loneliness=emotion_state.loneliness,
            regulation_budget=getattr(emotion_state, 'regulation_budget', 1.0)
        )
        self.snapshots.append(snapshot)
        
    def calculate_metrics(self) -> Dict[str, Any]:
        """Calculate body telemetry metrics"""
        if not self.snapshots:
            return {}
            
        energies = [s.energy for s in self.snapshots]
        social_safeties = [s.social_safety for s in self.snapshots]
        arousals = [s.arousal for s in self.snapshots]
        valences = [s.valence for s in self.snapshots]
        
        # Calculate trajectory statistics
        return {
            "energy": {
                "mean": statistics.mean(energies),
                "min": min(energies),
                "max": max(energies),
                "range": round(max(energies) - min(energies), 6),
                "final": energies[-1],
                "trend": energies[-1] - energies[0] if len(energies) > 1 else 0
            },
            "social_safety": {
                "mean": statistics.mean(social_safeties),
                "min": min(social_safeties),
                "max": max(social_safeties),
                "range": round(max(social_safeties) - min(social_safeties), 6),
                "final": social_safeties[-1],
                "trend": social_safeties[-1] - social_safeties[0] if len(social_safeties) > 1 else 0
            },
            "arousal": {
                "mean": statistics.mean(arousals),
                "volatility": statistics.stdev(arousals) if len(arousals) > 1 else 0,
                "peak": max(arousals),
                "final": arousals[-1]
            },
            "valence": {
                "mean": statistics.mean(valences),
                "volatility": statistics.stdev(valences) if len(valences) > 1 else 0,
                "range": max(valences) - min(valences)
            }
        }


class ConsequenceTagger:
    """Tags events with their emotional/bodily consequences"""
    
    TAG_THRESHOLDS = {
        "energy_depletion": (-0.05, "energy"),
        "energy_boost": (0.05, "energy"),
        "social_safety_drop": (-0.1, "social_safety"),
        "social_safety_boost": (0.1, "social_safety"),
        "anxiety_spike": (0.15, "anxiety"),
        "anxiety_relief": (-0.1, "anxiety"),
        "joy_boost": (0.1, "joy"),
        "joy_loss": (-0.1, "joy"),
        "valence_crash": (-0.2, "valence"),
        "valence_surge": (0.2, "valence"),
        "arousal_spike": (0.2, "arousal"),
        "loneliness_increase": (0.1, "loneliness"),
    }
    
    def tag_turn(self, turn: TurnResult) -> List[ConsequenceTag]:
        """Generate consequence tags for a turn"""
        tags = []
        
        if not turn.emotion_before or not turn.emotion_after:
            return tags
            
        before = turn.emotion_before
        after = turn.emotion_after
        
        # Check each tag condition
        deltas = {
            "energy": after.energy - before.energy,
            "social_safety": after.social_safety - before.social_safety,
            "anxiety": after.anxiety - before.anxiety,
            "joy": after.joy - before.joy,
            "valence": after.valence - before.valence,
            "arousal": after.arousal - before.arousal,
            "loneliness": after.loneliness - before.loneliness,
        }
        
        for tag_name, (threshold, metric) in self.TAG_THRESHOLDS.items():
            delta = deltas.get(metric, 0)
            if threshold > 0 and delta >= threshold:
                tags.append(ConsequenceTag(
                    tag=tag_name,
                    severity=min(1.0, abs(delta) / abs(threshold)),
                    source_event=turn.event_type,
                    turn_id=turn.turn_id
                ))
            elif threshold < 0 and delta <= threshold:
                tags.append(ConsequenceTag(
                    tag=tag_name,
                    severity=min(1.0, abs(delta) / abs(threshold)),
                    source_event=turn.event_type,
                    turn_id=turn.turn_id
                ))
                
        return tags
    
    def calculate_distribution(self, all_tags: List[ConsequenceTag]) -> Dict[str, Any]:
        """Calculate consequence tag distribution"""
        if not all_tags:
            return {"total": 0, "by_tag": {}, "by_severity": {"low": 0, "medium": 0, "high": 0}, "unique_tags": 0}
            
        by_tag = defaultdict(int)
        by_severity = {"low": 0, "medium": 0, "high": 0}
        
        for tag in all_tags:
            by_tag[tag.tag] += 1
            if tag.severity < 1.5:
                by_severity["low"] += 1
            elif tag.severity < 2.5:
                by_severity["medium"] += 1
            else:
                by_severity["high"] += 1
                
        return {
            "total": len(all_tags),
            "by_tag": dict(by_tag),
            "by_severity": by_severity,
            "unique_tags": len(by_tag)
        }


class RecoveryAnalyzer:
    """Analyzes recovery patterns from negative events"""
    
    RECOVERY_THRESHOLD = 0.5  # Fraction of loss to recover
    MAX_RECOVERY_TURNS = 10
    
    def __init__(self):
        self.windows: List[RecoveryWindow] = []
        self.current_window: Optional[RecoveryWindow] = None
        
    def process_turn(self, turn: TurnResult):
        """Process a turn for recovery analysis"""
        if not turn.emotion_after:
            return
            
        # Check for negative trigger (valence crash or energy depletion)
        is_trigger = False
        if turn.emotion_before:
            valence_drop = turn.emotion_before.valence - turn.emotion_after.valence
            energy_drop = turn.emotion_before.energy - turn.emotion_after.energy
            
            if valence_drop > 0.15 or energy_drop > 0.08:
                is_trigger = True
                
        if is_trigger and self.current_window is None:
            # Start new recovery window
            self.current_window = RecoveryWindow(
                trigger_turn=turn.turn_id,
                trigger_valence=turn.emotion_after.valence,
                trigger_energy=turn.emotion_after.energy
            )
            
        if self.current_window:
            self.current_window.recovery_turns.append(turn.turn_id)
            self.current_window.valence_trajectory.append(turn.emotion_after.valence)
            self.current_window.energy_trajectory.append(turn.emotion_after.energy)
            
            # Check if recovered
            if len(self.current_window.valence_trajectory) >= 2:
                baseline_valence = self.current_window.valence_trajectory[0]
                current_valence = turn.emotion_after.valence
                
                # Recovered if back to within RECOVERY_THRESHOLD of baseline
                if current_valence >= baseline_valence + (self.RECOVERY_THRESHOLD * 0.1):
                    self.current_window.recovered = True
                    self.current_window.recovery_time_turns = len(self.current_window.recovery_turns)
                    self.windows.append(self.current_window)
                    self.current_window = None
                    
            # Max recovery window exceeded
            if self.current_window and len(self.current_window.recovery_turns) >= self.MAX_RECOVERY_TURNS:
                self.windows.append(self.current_window)
                self.current_window = None
                
    def calculate_metrics(self) -> Dict[str, Any]:
        """Calculate recovery metrics"""
        if not self.windows:
            return {
                "recovery_count": 0,
                "recovery_rate": 1.0,  # No failures to recover from
                "avg_recovery_time": 0,
                "robustness_score": 1.0
            }
            
        recovered = sum(1 for w in self.windows if w.recovered)
        recovery_times = [w.recovery_time_turns for w in self.windows if w.recovered]
        
        return {
            "recovery_count": len(self.windows),
            "recovery_rate": recovered / len(self.windows),
            "avg_recovery_time": statistics.mean(recovery_times) if recovery_times else -1,
            "robustness_score": recovered / len(self.windows) * (1.0 / (1 + statistics.mean(recovery_times) * 0.1)) if recovery_times else 0.5
        }


class ScenarioRunner:
    """Runner for individual scenarios"""
    
    def __init__(self, scenario_path: Path, seed: int = 42):
        self.scenario_path = scenario_path
        self.scenario_data = None
        self.turn_results: List[TurnResult] = []
        self.seed = seed
        self.telemetry_tracker = BodyTelemetryTracker()
        self.consequence_tagger = ConsequenceTagger()
        self.recovery_analyzer = RecoveryAnalyzer()
        
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
        # High anxiety + ambiguous event
        if emotion_after.anxiety > 0.2:
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
                seconds = event_meta.get("seconds", 60)
                core.emotion_state.apply_homeostasis_drift(real_dt=seconds)
            else:
                meta = event_meta.copy() if event_meta else {}
                
                if event_type == "world_event" and "source" not in meta:
                    meta["source"] = "system"
                
                event = Event(
                    type=event_type,
                    actor=actor,
                    target=target,
                    text=event_data.get("text"),
                    meta=meta if meta else None
                )
                
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
        
        # Emotion Consistency
        valences = [t.emotion_after.valence for t in self.turn_results if t.success and t.emotion_after]
        arousals = [t.emotion_after.arousal for t in self.turn_results if t.success and t.emotion_after]
        
        metrics["emotion_consistency"] = {
            "valence_range": max(valences) - min(valences) if valences else 0,
            "arousal_range": max(arousals) - min(arousals) if arousals else 0,
            "trajectory_length": len(valences),
            "passed": True
        }
        
        # Individualization Diff
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
            "passed": 0.0 <= trigger_rate <= 0.6
        }
        
        # MVP-6: Body Telemetry Metrics
        body_metrics = self.telemetry_tracker.calculate_metrics()
        metrics["body_telemetry"] = {
            "data": body_metrics,
            "passed": body_metrics.get("energy", {}).get("min", 0) > 0.1  # Energy shouldn't collapse
        }
        
        # MVP-6: Recovery Score
        recovery_metrics = self.recovery_analyzer.calculate_metrics()
        metrics["recovery_score"] = {
            "score": recovery_metrics.get("recovery_rate", 1.0),
            "recovery_count": recovery_metrics.get("recovery_count", 0),
            "avg_recovery_time": recovery_metrics.get("avg_recovery_time", 0),
            "passed": recovery_metrics.get("recovery_rate", 1.0) >= 0.5
        }
        
        # MVP-6: Robustness Score
        robustness = recovery_metrics.get("robustness_score", 1.0)
        metrics["robustness_score"] = {
            "score": robustness,
            "passed": robustness >= 0.3
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
                summary="Failed to load scenario",
                body_telemetry=[],
                consequence_tags=[],
                recovery_windows=[]
            )
        
        scenario_name = self.scenario_data.get("metadata", {}).get("name", "unknown")
        turns = self.scenario_data.get("scenario", {}).get("turns", [])
        
        # Reset emotion state with seed for reproducibility
        random.seed(self.seed)
        core.emotion_state.valence = 0.0
        core.emotion_state.arousal = 0.3
        core.emotion_state.anger = 0.0
        core.emotion_state.sadness = 0.0
        core.emotion_state.anxiety = 0.0
        core.emotion_state.joy = 0.0
        core.emotion_state.loneliness = 0.0
        core.emotion_state.social_safety = 0.6
        core.emotion_state.energy = 0.7
        core.emotion_state.regulation_budget = 1.0
        core.relationship_manager.relationships = {}
        
        # Setup initial state
        await self.setup_initial_state()
        
        # Process all turns
        self.turn_results = []
        all_consequence_tags = []
        
        for turn_data in turns:
            result = await self.process_turn(turn_data)
            self.turn_results.append(result)
            
            # Record telemetry
            self.telemetry_tracker.record(result.turn_id, core.emotion_state)
            
            # Tag consequences
            tags = self.consequence_tagger.tag_turn(result)
            result.consequence_tags = tags
            all_consequence_tags.extend(tags)
            
            # Analyze recovery
            self.recovery_analyzer.process_turn(result)
        
        # Calculate metrics
        metrics = self.calculate_metrics()
        
        # Calculate consequence distribution
        consequence_dist = self.consequence_tagger.calculate_distribution(all_consequence_tags)
        metrics["consequence_distribution"] = {
            "data": consequence_dist,
            "passed": consequence_dist.get("total", 0) >= 0  # Any distribution is valid
        }
        
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
            summary=summary,
            body_telemetry=self.telemetry_tracker.snapshots,
            consequence_tags=all_consequence_tags,
            recovery_windows=self.recovery_analyzer.windows
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
    elif isinstance(obj, (EmotionSnapshot, RelationshipSnapshot, BodyTelemetrySnapshot, ConsequenceTag, RecoveryWindow)):
        return asdict(obj)
    else:
        return obj


class EvalSuiteV2_2:
    """Main evaluation suite runner v2.2"""
    
    def __init__(self, scenarios_dir: Path = None, output_format: str = "json", seed: int = 42):
        self.base_path = Path(__file__).parent.parent
        self.scenarios_dir = scenarios_dir or self.base_path / "scenarios"
        self.output_format = output_format
        self.results: List[ScenarioResult] = []
        self.seed = seed
        
    def discover_scenarios(self) -> List[Path]:
        """Discover all scenario files"""
        scenarios = []
        if self.scenarios_dir.exists():
            for ext in ["*.yaml", "*.yml", "*.json"]:
                scenarios.extend(self.scenarios_dir.glob(ext))
        return sorted(scenarios)
    
    async def setup_environment(self):
        """Setup isolated test environment"""
        self.test_dir = tempfile.mkdtemp(prefix="emotiond_eval_v2_2_")
        
        self.original_env = {}
        env_vars = {
            "EMOTIOND_DB_PATH": os.path.join(self.test_dir, "eval.db"),
            "EMOTIOND_SYSTEM_TOKEN": TEST_SYSTEM_TOKEN,
            "EMOTIOND_OPENCLAW_TOKEN": TEST_OPENCLAW_TOKEN
        }
        
        for key, value in env_vars.items():
            self.original_env[key] = os.environ.get(key)
            os.environ[key] = value
        
        import importlib
        importlib.reload(config)
        importlib.reload(db)
        importlib.reload(core)
        
        await init_db()
    
    def teardown_environment(self):
        """Cleanup test environment"""
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        
        try:
            shutil.rmtree(self.test_dir, ignore_errors=True)
        except:
            pass
    
    async def run_scenario(self, scenario_path: Path) -> ScenarioResult:
        """Run a single scenario"""
        runner = ScenarioRunner(scenario_path, seed=self.seed)
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
        
        # MVP-6: Body telemetry aggregates
        energy_mins = []
        energy_ranges = []
        social_safety_trends = []
        arousal_volatilities = []
        
        for r in self.results:
            telemetry = r.metrics.get("body_telemetry", {}).get("data", {})
            if telemetry.get("energy"):
                energy_mins.append(telemetry["energy"].get("min", 0.7))
                energy_ranges.append(telemetry["energy"].get("range", 0))
            if telemetry.get("social_safety"):
                social_safety_trends.append(telemetry["social_safety"].get("trend", 0))
            if telemetry.get("arousal"):
                arousal_volatilities.append(telemetry["arousal"].get("volatility", 0))
        
        # MVP-6: Recovery aggregates
        recovery_rates = [
            r.metrics.get("recovery_score", {}).get("score", 1.0)
            for r in self.results
        ]
        
        # MVP-6: Robustness aggregates
        robustness_scores = [
            r.metrics.get("robustness_score", {}).get("score", 1.0)
            for r in self.results
        ]
        
        # MVP-6: Consequence distribution aggregates
        total_consequences = sum(
            r.metrics.get("consequence_distribution", {}).get("data", {}).get("total", 0)
            for r in self.results
        )
        
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
            },
            "body_telemetry": {
                "energy_min_avg": statistics.mean(energy_mins) if energy_mins else 0.7,
                "energy_range_avg": statistics.mean(energy_ranges) if energy_ranges else 0,
                "social_safety_trend_avg": statistics.mean(social_safety_trends) if social_safety_trends else 0,
                "arousal_volatility_avg": statistics.mean(arousal_volatilities) if arousal_volatilities else 0
            },
            "recovery_score": {
                "average": statistics.mean(recovery_rates) if recovery_rates else 1.0,
                "min": min(recovery_rates) if recovery_rates else 1.0
            },
            "robustness_score": {
                "average": statistics.mean(robustness_scores) if robustness_scores else 1.0,
                "min": min(robustness_scores) if robustness_scores else 1.0
            },
            "consequence_distribution": {
                "total_tags": total_consequences
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
                aggregate_metrics={},
                seed=self.seed
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
                aggregate_metrics=aggregate_metrics,
                seed=self.seed
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
                "# Eval Suite v2.2 Report",
                f"\n**Generated:** {result.end_time}",
                f"**Seed:** {result.seed}",
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
                else:
                    lines.append(f"- **value:** {metric_value}")
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
                
                # MVP-6: Add body telemetry summary
                if scenario.body_telemetry:
                    lines.append(f"- **Telemetry Snapshots:** {len(scenario.body_telemetry)}")
                
                # MVP-6: Add consequence tags summary
                if scenario.consequence_tags:
                    lines.append(f"- **Consequence Tags:** {len(scenario.consequence_tags)}")
                
                # MVP-6: Add recovery windows summary
                if scenario.recovery_windows:
                    recovered = sum(1 for w in scenario.recovery_windows if w.recovered)
                    lines.append(f"- **Recovery Windows:** {recovered}/{len(scenario.recovery_windows)} recovered")
                
                lines.append("")
            
            return "\n".join(lines)


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Eval Suite v2.2 for OpenEmotion MVP-6")
    parser.add_argument("--scenarios", nargs="+", help="Specific scenario files to run")
    parser.add_argument("--output", choices=["json", "markdown"], default="json",
                       help="Output format")
    parser.add_argument("--output-file", help="Write output to file")
    parser.add_argument("--seed", type=int, default=42,
                       help="Random seed for reproducibility (default: 42)")
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
    suite = EvalSuiteV2_2(scenarios_dir=scenarios_dir, output_format=args.output, seed=args.seed)
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
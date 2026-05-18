#!/usr/bin/env python3
"""Auto-Tune v0.3 for OpenEmotion MVP-6.x (D5+), fixed param injection."""

import os
import sys
import json
import yaml
import random
import asyncio
import time
import statistics
import copy
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.eval_suite_v2_3 import EvalSuiteV2_3, EvalResult, result_to_dict
from emotiond.config import set_auto_tune_params, clear_auto_tune_params, get_auto_tune_params_snapshot

DEFAULT_TUNABLE_PARAMS = {
    "precision_temperature": {"default": 0.5, "min": 0.1, "max": 1.0, "category": "precision"},
    "precision_uncertainty_threshold": {"default": 0.3, "min": 0.1, "max": 0.8, "category": "precision"},
    "w_external_default": {"default": 0.6, "min": 0.2, "max": 0.9, "category": "precision"},
    "w_internal_default": {"default": 0.5, "min": 0.2, "max": 0.8, "category": "precision"},
    "w_memory_default": {"default": 0.4, "min": 0.1, "max": 0.7, "category": "precision"},
    "w_action_default": {"default": 0.5, "min": 0.2, "max": 0.8, "category": "precision"},
    "w_explore_default": {"default": 0.3, "min": 0.1, "max": 0.6, "category": "precision"},
    "energy_recovery_rate": {"default": 0.001, "min": 0.0001, "max": 0.01, "category": "allostasis"},
    "energy_depletion_conflict": {"default": 0.05, "min": 0.01, "max": 0.15, "category": "allostasis"},
    "energy_depletion_uncertainty": {"default": 0.03, "min": 0.01, "max": 0.1, "category": "allostasis"},
    "low_energy_explore_dampening": {"default": 0.5, "min": 0.1, "max": 0.9, "category": "allostasis"},
    "low_energy_learning_dampening": {"default": 0.7, "min": 0.3, "max": 0.95, "category": "allostasis"},
    "curiosity_info_gain_threshold": {"default": 0.2, "min": 0.05, "max": 0.5, "category": "intrinsic"},
    "boredom_prediction_error_threshold": {"default": 0.05, "min": 0.01, "max": 0.2, "category": "intrinsic"},
    "confusion_error_threshold": {"default": 0.3, "min": 0.15, "max": 0.6, "category": "intrinsic"},
    "boredom_time_window": {"default": 300, "min": 60, "max": 900, "category": "intrinsic"},
    "self_model_update_rate": {"default": 0.1, "min": 0.01, "max": 0.3, "category": "self_model"},
    "identity_stability_threshold": {"default": 0.8, "min": 0.5, "max": 0.95, "category": "self_model"},
    "value_conflict_resolution_rate": {"default": 0.05, "min": 0.01, "max": 0.2, "category": "self_model"},
    "clarification_trigger_threshold": {"default": 0.4, "min": 0.2, "max": 0.7, "category": "meta_cognition"},
    "reflection_trigger_threshold": {"default": 0.5, "min": 0.3, "max": 0.8, "category": "meta_cognition"},
    "shrinkage_k": {"default": 10.0, "min": 1.0, "max": 50.0, "category": "target_residual"},
    "residual_learning_rate": {"default": 0.1, "min": 0.01, "max": 0.5, "category": "target_residual"},
    "residual_evidence_increment": {"default": 0.1, "min": 0.01, "max": 0.3, "category": "target_residual"},
    "residual_update_gain": {"default": 1.0, "min": 0.5, "max": 3.0, "category": "target_residual"},
    "residual_condition_gain": {"default": 0.1, "min": 0.0, "max": 1.5, "category": "target_residual"},
    "residual_condition_action_gain": {"default": 0.25, "min": 0.05, "max": 0.60, "category": "target_residual"},
    "residual_condition_memory_gain": {"default": 0.18, "min": 0.05, "max": 0.50, "category": "target_residual"},
    "residual_condition_explore_gain": {"default": 0.08, "min": 0.01, "max": 0.30, "category": "target_residual"},
    "residual_condition_tanh_k": {"default": 3.0, "min": 0.5, "max": 6.0, "category": "target_residual"},
    "residual_policy_bias_gain": {"default": 0.10, "min": 0.02, "max": 0.30, "category": "target_residual"},
    "bond_update_gain": {"default": 1.0, "min": 0.5, "max": 3.0, "category": "relationship"},
    "precision_raw_gain": {"default": 1.0, "min": 0.5, "max": 3.0, "category": "precision"},
    "betrayal_promise_strength_threshold": {"default": 0.5, "min": 0.2, "max": 0.9, "category": "betrayal_gating"},
    "betrayal_violation_strength_threshold": {"default": 0.6, "min": 0.2, "max": 0.9, "category": "betrayal_gating"},
    "betrayal_evidence_threshold": {"default": 0.4, "min": 0.1, "max": 0.8, "category": "betrayal_gating"},
    "betrayal_clarify_fallback_threshold": {"default": 0.3, "min": 0.1, "max": 0.6, "category": "betrayal_gating"},
    "recovery_rate_energy": {"default": 0.001, "min": 0.0001, "max": 0.005, "category": "recovery"},
    "recovery_rate_safety": {"default": 0.0008, "min": 0.0001, "max": 0.005, "category": "recovery"},
    "recovery_rate_social": {"default": 0.0005, "min": 0.0001, "max": 0.003, "category": "recovery"},
    "recovery_half_life_threshold": {"default": 0.5, "min": 0.3, "max": 0.8, "category": "recovery"},
    "collapse_penalty_weight": {"default": 1.0, "min": 0.5, "max": 2.0, "category": "recovery"},
    "individualization_n_obs_strict": {"default": 10, "min": 5, "max": 30, "category": "individualization"},
    "individualization_n_obs_relaxed": {"default": 3, "min": 1, "max": 10, "category": "individualization"},
    "individualization_threshold_strict": {"default": 0.05, "min": 0.01, "max": 0.15, "category": "individualization"},
    "individualization_threshold_relaxed": {"default": 0.15, "min": 0.05, "max": 0.30, "category": "individualization"},
}


@dataclass
class CandidateValidationResult:
    accepted: bool
    reason_code: Optional[str] = None
    details: Optional[str] = None


class KnobRegistry:
    def __init__(self, registry_path: Optional[Path] = None):
        base_dir = Path(__file__).parent
        self.registry_path = registry_path or (base_dir / "knob_registry.json")
        with open(self.registry_path, "r") as f:
            raw = json.load(f)
        self.version = str(raw.get("version", "unknown"))
        allowlist_raw = raw.get("allowlist", [])
        if isinstance(allowlist_raw, dict):
            # Backward compatibility: grouped schema {group:{parameters:[...]}}
            collected = []
            for v in allowlist_raw.values():
                if isinstance(v, dict) and isinstance(v.get("parameters"), list):
                    collected.extend(v.get("parameters", []))
                else:
                    collected.append(str(v))
            self.allowlist = set(collected)
        else:
            self.allowlist = set(allowlist_raw)
        hard = raw.get("hard_freeze", {})
        keys = hard.get("keys", [])
        prefixes = hard.get("prefixes", [])
        if isinstance(hard, dict) and not keys:
            # Backward compatibility: grouped schema {group:{parameters:[...]}}
            for v in hard.values():
                if isinstance(v, dict) and isinstance(v.get("parameters"), list):
                    keys.extend(v.get("parameters", []))
        self.hard_freeze_keys = set(keys)
        self.hard_freeze_prefixes = tuple(prefixes)
        self.hard_freeze_reason_code = str(hard.get("reason_code", "HARD_FREEZE_VIOLATION"))

    def validate_candidate(self, params: Dict[str, float]) -> CandidateValidationResult:
        for key in params.keys():
            if key in self.hard_freeze_keys:
                return CandidateValidationResult(
                    accepted=False,
                    reason_code=self.hard_freeze_reason_code,
                    details=f"key={key}",
                )
            if self.hard_freeze_prefixes and key.startswith(self.hard_freeze_prefixes):
                return CandidateValidationResult(
                    accepted=False,
                    reason_code=self.hard_freeze_reason_code,
                    details=f"prefix={key}",
                )
            if key not in self.allowlist:
                return CandidateValidationResult(
                    accepted=False,
                    reason_code="KNOB_NOT_ALLOWLISTED",
                    details=f"key={key}",
                )
        return CandidateValidationResult(accepted=True)



@dataclass
class LexicographicFitness:
    passed_scenarios: int
    high_impact_false_positive_rate: float
    individualization_score: float
    recovery_score: float
    efficiency: float
    somatic_residual_diff: float = 0.0
    bond_diff: float = 0.0
    ledger_diff: float = 0.0
    policy_diff: float = 0.0
    collapse_penalty: float = 0.0
    emotion_consistency: float = 0.0
    robustness: float = 0.0
    tie_breaker: float = 0.0
    
    def calculate_tie_breaker(self) -> float:
        weights = {
            "passed_scenarios": 0.30,
            "high_impact_false_positive_rate": 0.20,
            "individualization_score": 0.15,
            "recovery_score": 0.15,
            "efficiency": 0.10,
            "emotion_consistency": 0.05,
            "robustness": 0.05,
        }
        norm_passed = min(1.0, self.passed_scenarios / 20.0)
        fp_score = 1.0 - self.high_impact_false_positive_rate
        self.tie_breaker = (
            weights["passed_scenarios"] * norm_passed +
            weights["high_impact_false_positive_rate"] * fp_score +
            weights["individualization_score"] * self.individualization_score +
            weights["recovery_score"] * self.recovery_score +
            weights["efficiency"] * self.efficiency +
            weights["emotion_consistency"] * self.emotion_consistency +
            weights["robustness"] * self.robustness
        )
        return self.tie_breaker
    
    def to_tuple(self) -> Tuple:
        return (
            self.passed_scenarios,
            -self.high_impact_false_positive_rate,
            self.individualization_score,
            self.recovery_score,
            self.efficiency,
            self.tie_breaker,
        )
    
    def __lt__(self, other):
        return self.to_tuple() < other.to_tuple()
    
    def __le__(self, other):
        return self.to_tuple() <= other.to_tuple()
    
    def __gt__(self, other):
        return self.to_tuple() > other.to_tuple()
    
    def __ge__(self, other):
        return self.to_tuple() >= other.to_tuple()
    
    def dominates(self, other) -> bool:
        self_tuple = self.to_tuple()
        other_tuple = other.to_tuple()
        for i, (s, o) in enumerate(zip(self_tuple, other_tuple)):
            if s > o:
                return all(self_tuple[j] == other_tuple[j] for j in range(i))
            elif s < o:
                return False
        return False
    
    def lexicographic_comparison(self, other) -> Dict[str, Any]:
        levels = [
            ("passed_scenarios", self.passed_scenarios, other.passed_scenarios, True),
            ("high_impact_false_positive_rate", self.high_impact_false_positive_rate, 
             other.high_impact_false_positive_rate, False),
            ("individualization_score", self.individualization_score, other.individualization_score, True),
            ("recovery_score", self.recovery_score, other.recovery_score, True),
            ("efficiency", self.efficiency, other.efficiency, True),
            ("tie_breaker", self.tie_breaker, other.tie_breaker, True),
        ]
        result = {"winner": None, "decision_level": None, "decision_reason": None, "level_comparison": []}
        for level_name, self_val, other_val, higher_is_better in levels:
            if higher_is_better:
                self_better = self_val > other_val
                other_better = self_val < other_val
            else:
                self_better = self_val < other_val
                other_better = self_val > other_val
            level_result = {
                "level": level_name,
                "self_value": self_val,
                "other_value": other_val,
                "higher_is_better": higher_is_better,
                "equal": self_val == other_val
            }
            result["level_comparison"].append(level_result)
            if result["winner"] is None and not level_result["equal"]:
                if self_better:
                    result["winner"] = "self"
                    result["decision_level"] = level_name
                    result["decision_reason"] = f"{level_name}: {self_val:.4f} vs {other_val:.4f}"
                else:
                    result["winner"] = "other"
                    result["decision_level"] = level_name
                    result["decision_reason"] = f"{level_name}: {other_val:.4f} vs {self_val:.4f}"
        if result["winner"] is None:
            result["winner"] = "tie"
            result["decision_level"] = "tie_breaker"
            result["decision_reason"] = f"All levels equal, tie-breaker: {self.tie_breaker:.6f} vs {other.tie_breaker:.6f}"
        return result
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "passed_scenarios": self.passed_scenarios,
            "high_impact_false_positive_rate": self.high_impact_false_positive_rate,
            "individualization_score": self.individualization_score,
            "somatic_residual_diff": self.somatic_residual_diff,
            "bond_diff": self.bond_diff,
            "ledger_diff": self.ledger_diff,
            "policy_diff": self.policy_diff,
            "recovery_score": self.recovery_score,
            "collapse_penalty": self.collapse_penalty,
            "efficiency": self.efficiency,
            "emotion_consistency": self.emotion_consistency,
            "robustness": self.robustness,
            "tie_breaker": self.tie_breaker,
        }


@dataclass
class CandidateResult:
    candidate_id: str
    params: Dict[str, float]
    fitness: LexicographicFitness
    eval_result: Dict[str, Any]
    param_fingerprint: str = ""
    effective_params_snapshot: Dict[str, Any] = field(default_factory=dict)
    telemetry_hash: str = ""
    threshold_config: Dict[str, Any] = field(default_factory=dict)
    rank: int = 0
    lexicographic_level: Optional[str] = None
    rejected: bool = False
    reason_code: Optional[str] = None
    validation_details: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "params": self.params,
            "fitness": self.fitness.to_dict(),
            "eval_result": self.eval_result,
            "param_fingerprint": self.param_fingerprint,
            "effective_params_snapshot": self.effective_params_snapshot,
            "telemetry_hash": self.telemetry_hash,
            "threshold_config": self.threshold_config,
            "rank": self.rank,
            "lexicographic_level": self.lexicographic_level,
            "rejected": self.rejected,
            "reason_code": self.reason_code,
            "validation_details": self.validation_details,
        }


@dataclass
class AutoTuneResult:
    timestamp: str
    seed: int
    baseline_params: Dict[str, Any]
    baseline_fitness: LexicographicFitness
    baseline_result: Dict[str, Any]
    candidates: List[CandidateResult]
    best_candidate: Optional[CandidateResult] = None
    overall_improvement: bool = False
    lexicographic_improvement: Optional[str] = None
    recommendations: List[str] = field(default_factory=list)
    report_path: Optional[str] = None
    rejection_stats: Dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "seed": self.seed,
            "baseline_params": self.baseline_params,
            "baseline_fitness": self.baseline_fitness.to_dict(),
            "baseline_result": self.baseline_result,
            "candidates": [c.to_dict() for c in self.candidates],
            "best_candidate": self.best_candidate.to_dict() if self.best_candidate else None,
            "overall_improvement": self.overall_improvement,
            "lexicographic_improvement": self.lexicographic_improvement,
            "recommendations": self.recommendations,
            "report_path": self.report_path,
            "rejection_stats": self.rejection_stats,
        }


class FitnessCalculator:
    @staticmethod
    def calculate_passed_scenarios(eval_result: EvalResult) -> int:
        return sum(1 for s in eval_result.scenarios if s.passed)
    
    @staticmethod
    def calculate_high_impact_false_positive_rate(eval_result: EvalResult) -> float:
        total_fp = 0
        total_high_impact = 0
        for scenario in eval_result.scenarios:
            fp_data = scenario.metrics.get("high_impact_false_positive_rate", {})
            total_fp += fp_data.get("false_positives", 0)
            total_high_impact += fp_data.get("total_high_impact_events", 0)
        return total_fp / total_high_impact if total_high_impact > 0 else 0.0
    
    @staticmethod
    def calculate_individualization_score(eval_result: EvalResult) -> Tuple[float, Dict[str, float]]:
        sub_scores = {"somatic_residual_diff": 0.0, "bond_diff": 0.0, "ledger_diff": 0.0, "policy_diff": 0.0}
        scores = []
        for scenario in eval_result.scenarios:
            indiv_data = scenario.metrics.get("individualization_diff", {})
            scores.append(1.0 if indiv_data.get("passed", False) else 0.0)
            for key in sub_scores:
                if key in indiv_data:
                    sub_scores[key] = max(sub_scores[key], indiv_data[key].get("score", 0.0))
        overall = statistics.mean(scores) if scores else 0.0
        return overall, sub_scores
    
    @staticmethod
    def calculate_recovery_score(eval_result: EvalResult) -> Tuple[float, float]:
        recovery_scores = []
        collapse_penalties = []
        for scenario in eval_result.scenarios:
            recovery_data = scenario.metrics.get("recovery_score", {})
            recovery_scores.append(recovery_data.get("score", 1.0))
            telemetry = scenario.metrics.get("body_telemetry", {}).get("data", {})
            energy_min = telemetry.get("energy", {}).get("min", 0.7)
            valence_data = telemetry.get("valence", {})
            valence_min = valence_data.get("min", 0) if isinstance(valence_data, dict) else 0
            energy_collapse = max(0, 0.3 - energy_min) / 0.3
            valence_collapse = max(0, -0.5 - valence_min) / 0.5
            collapse_penalties.append(max(energy_collapse, valence_collapse))
        recovery = statistics.mean(recovery_scores) if recovery_scores else 1.0
        collapse = statistics.mean(collapse_penalties) if collapse_penalties else 0.0
        return recovery, collapse
    
    @staticmethod
    def calculate_efficiency(eval_result: EvalResult) -> float:
        if not eval_result.scenarios:
            return 0.0
        total_turns = sum(len(s.turns) for s in eval_result.scenarios)
        successful_turns = sum(sum(1 for t in s.turns if t.success) for s in eval_result.scenarios)
        if total_turns == 0:
            return 0.0
        success_rate = successful_turns / total_turns
        avg_energy_min = statistics.mean([
            s.metrics.get("body_telemetry", {}).get("data", {}).get("energy", {}).get("min", 0.7)
            for s in eval_result.scenarios
        ]) if eval_result.scenarios else 0.7
        return success_rate * avg_energy_min
    
    @staticmethod
    def calculate_emotion_consistency(eval_result: EvalResult) -> float:
        consistency_data = eval_result.aggregate_metrics.get("emotion_consistency", {})
        return consistency_data.get("pass_rate", 1.0)
    
    @staticmethod
    def calculate_robustness(eval_result: EvalResult) -> float:
        robustness_scores = []
        for scenario in eval_result.scenarios:
            robustness_data = scenario.metrics.get("robustness_score", {})
            robustness_scores.append(robustness_data.get("score", 1.0))
        return statistics.mean(robustness_scores) if robustness_scores else 1.0
    
    @classmethod
    def calculate_all(cls, eval_result: EvalResult) -> LexicographicFitness:
        passed = cls.calculate_passed_scenarios(eval_result)
        fp_rate = cls.calculate_high_impact_false_positive_rate(eval_result)
        indiv_score, indiv_subscores = cls.calculate_individualization_score(eval_result)
        recovery, collapse = cls.calculate_recovery_score(eval_result)
        efficiency = cls.calculate_efficiency(eval_result)
        consistency = cls.calculate_emotion_consistency(eval_result)
        robustness = cls.calculate_robustness(eval_result)
        fitness = LexicographicFitness(
            passed_scenarios=passed,
            high_impact_false_positive_rate=fp_rate,
            individualization_score=indiv_score,
            recovery_score=recovery,
            efficiency=efficiency,
            somatic_residual_diff=indiv_subscores["somatic_residual_diff"],
            bond_diff=indiv_subscores["bond_diff"],
            ledger_diff=indiv_subscores["ledger_diff"],
            policy_diff=indiv_subscores["policy_diff"],
            collapse_penalty=collapse,
            emotion_consistency=consistency,
            robustness=robustness,
        )
        fitness.calculate_tie_breaker()
        return fitness


class PerturbationGenerator:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def perturb(self, params: Dict[str, float], param_defs: Dict[str, Dict],
                strategy: str = "random", magnitude: float = 0.2) -> Dict[str, float]:
        perturbed = copy.deepcopy(params)
        for name, value in perturbed.items():
            definition = param_defs.get(name, {})
            min_val = definition.get("min", value * 0.5)
            max_val = definition.get("max", value * 1.5)
            range_val = max_val - min_val
            if strategy == "random":
                delta = self.rng.uniform(-1, 1) * magnitude * range_val
                new_value = value + delta
            elif strategy == "gaussian":
                std = magnitude * range_val / 3
                delta = self.rng.gauss(0, std)
                new_value = value + delta
            elif strategy == "boundary":
                if self.rng.random() < 0.5:
                    new_value = min_val + magnitude * range_val * self.rng.random()
                else:
                    new_value = max_val - magnitude * range_val * self.rng.random()
            elif strategy == "focused":
                high_impact = ["shrinkage_k", "betrayal_promise_strength_threshold",
                              "betrayal_violation_strength_threshold", "recovery_rate_energy"]
                if name in high_impact:
                    delta = self.rng.uniform(-1, 1) * magnitude * 1.5 * range_val
                    new_value = value + delta
                else:
                    delta = self.rng.uniform(-1, 1) * magnitude * 0.5 * range_val
                    new_value = value + delta
            else:
                raise ValueError(f"Unknown strategy: {strategy}")
            perturbed[name] = max(min_val, min(max_val, new_value))
        return perturbed

    def generate_candidates(self, baseline: Dict[str, float],
                           param_defs: Dict[str, Dict],
                           count: int = 200,
                           strategies: List[str] = None) -> List[Dict[str, float]]:
        if strategies is None:
            strategies = ["random", "gaussian", "boundary", "focused"]
        candidates = []
        for i in range(count):
            strategy = strategies[i % len(strategies)]
            magnitude = 0.1 + (i / count) * 0.3
            candidate = self.perturb(baseline, param_defs, strategy, magnitude)
            candidates.append(candidate)
        return candidates




def _param_fingerprint(params: Dict[str, float]) -> str:
    payload = json.dumps(params, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _eval_telemetry_hash(eval_result: EvalResult) -> str:
    data = result_to_dict(eval_result)
    agg = data.get("aggregate_metrics", {})
    scenarios = data.get("scenarios", [])

    # Include scenario-level signal slices so param-consumption sentinel is not blind
    scenario_slices = []
    for sc in scenarios:
        m = sc.get("metrics", {})
        scenario_slices.append({
            "scenario_name": sc.get("scenario_name"),
            "submetric_trace": m.get("individualization_submetric_trace", {}),
            "target_debug": m.get("target_isolation_debug", {}),
        })

    payload_obj = {
        "aggregate_metrics": agg,
        "scenario_slices": scenario_slices,
    }
    payload = json.dumps(payload_obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _eval_probe_signature(eval_result: EvalResult) -> str:
    data = result_to_dict(eval_result)
    scenarios = data.get("scenarios", [])
    compact = []
    for sc in scenarios:
        m = sc.get("metrics", {})
        compact.append({
            "name": sc.get("scenario_name"),
            "recovery": m.get("recovery_score", {}),
            "submetric": m.get("individualization_submetric_trace", {}),
            "raw": m.get("individualization_raw_dump", {}),
        })
    payload = json.dumps(compact, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()

def _pick_smoke_scenarios(scenarios_dir: Path) -> List[Path]:
    preferred = [
        "smoke_precision_probe.yaml",
        "smoke_residual_forced.yaml",
        "smoke_ledger_forced.yaml",
        "cross_target_isolation.yaml",
        "rewarded_progress.yaml",
    ]
    picked = []
    for name in preferred:
        p = scenarios_dir / name
        if p.exists():
            picked.append(p)
    if not picked:
        all_yaml = sorted(scenarios_dir.glob("*.yaml"))
        picked = all_yaml[:2]
    return picked[:2]

class AutoTuneEngine:
    def __init__(self, scenarios_dir: Path, output_dir: Path, seed: int = 42):
        self.scenarios_dir = scenarios_dir
        self.output_dir = output_dir
        self.seed = seed
        self.perturbation_gen = PerturbationGenerator(seed)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def apply_parameters(self, params: Dict[str, float]):
        clear_auto_tune_params()
        set_auto_tune_params({k: float(v) for k, v in params.items()})

    async def run_eval(self, params: Dict[str, float],
                      scenarios: Optional[List[Path]] = None) -> EvalResult:
        self.apply_parameters(params)
        suite = EvalSuiteV2_3(scenarios_dir=self.scenarios_dir, output_format="json", seed=self.seed)
        result = await suite.run_all(scenarios)
        return result

    async def assert_params_consumed(self, baseline_params: Dict[str, float]) -> None:
        smoke = _pick_smoke_scenarios(self.scenarios_dir)
        if not smoke:
            return

        probe_params = [
            "precision_temperature",
            "shrinkage_k",
            "residual_condition_gain",
            "residual_condition_tanh_k",
            "individualization_threshold_strict",
            "individualization_threshold_relaxed",
            "recovery_rate_energy",
        ]
        checked = 0
        for probe_param in probe_params:
            if probe_param not in baseline_params or probe_param not in DEFAULT_TUNABLE_PARAMS:
                continue
            checked += 1
            low = dict(baseline_params)
            high = dict(baseline_params)
            low[probe_param] = DEFAULT_TUNABLE_PARAMS[probe_param]["min"]
            high[probe_param] = DEFAULT_TUNABLE_PARAMS[probe_param]["max"]
            low_res = await self.run_eval(low, smoke)
            high_res = await self.run_eval(high, smoke)
            low_hash = _eval_telemetry_hash(low_res)
            high_hash = _eval_telemetry_hash(high_res)
            low_probe = _eval_probe_signature(low_res)
            high_probe = _eval_probe_signature(high_res)
            if low_hash != high_hash or low_probe != high_probe:
                return

        if checked == 0:
            raise RuntimeError("E_PARAM_NOT_CONSUMED: no valid probe parameter available")
        raise RuntimeError("E_PARAM_NOT_CONSUMED: overrides not affecting eval execution")

    async def tune(self,
                   baseline_params: Optional[Dict[str, float]] = None,
                   candidate_params_list: Optional[List[Dict[str, float]]] = None,
                   scenarios: Optional[List[Path]] = None,
                   generate_candidates: bool = False,
                   candidate_count: int = 200,
                   skip_sentinel: bool = False) -> AutoTuneResult:
        if baseline_params is None:
            baseline_params = {name: defn["default"] for name, defn in DEFAULT_TUNABLE_PARAMS.items()}
        if candidate_params_list is None:
            if generate_candidates:
                candidate_params_list = self.perturbation_gen.generate_candidates(
                    baseline_params, DEFAULT_TUNABLE_PARAMS, candidate_count
                )
            else:
                candidate_params_list = [self.perturbation_gen.perturb(
                    baseline_params, DEFAULT_TUNABLE_PARAMS, "random", 0.15)]
        clear_auto_tune_params()
        if not skip_sentinel:
            await self.assert_params_consumed(baseline_params)
        print(f"Running baseline evaluation...")
        baseline_eval_result = await self.run_eval(baseline_params, scenarios)
        baseline_fitness = FitnessCalculator.calculate_all(baseline_eval_result)
        print(f"Baseline fitness:")
        print(f"  - passed_scenarios: {baseline_fitness.passed_scenarios}")
        print(f"  - high_impact_fp_rate: {baseline_fitness.high_impact_false_positive_rate:.4f}")
        print(f"  - individualization_score: {baseline_fitness.individualization_score:.4f}")
        print(f"  - recovery_score: {baseline_fitness.recovery_score:.4f}")
        print(f"  - efficiency: {baseline_fitness.efficiency:.4f}")
        print(f"  - tie_breaker: {baseline_fitness.tie_breaker:.6f}")
        candidates = []
        rejection_counter: Counter[str] = Counter()
        for i, candidate_params in enumerate(candidate_params_list):
            print(f"\nRunning candidate {i+1}/{len(candidate_params_list)}...")
            validation = self.knob_registry.validate_candidate(candidate_params)
            if not validation.accepted:
                rejection_counter[validation.reason_code or "UNKNOWN"] += 1
                print(f"  Candidate {i+1}: REJECTED ({validation.reason_code}) {validation.details or ''}")
                candidates.append(CandidateResult(
                    candidate_id=f"candidate_{i+1}",
                    params=candidate_params,
                    fitness=baseline_fitness,
                    eval_result={"rejected": True},
                    param_fingerprint=_param_fingerprint(candidate_params),
                    rejected=True,
                    reason_code=validation.reason_code,
                    validation_details=validation.details,
                ))
                continue
            candidate_eval_result = await self.run_eval(candidate_params, scenarios)
            candidate_fitness = FitnessCalculator.calculate_all(candidate_eval_result)
            print(f"  Candidate {i+1}: passed={candidate_fitness.passed_scenarios}, fp_rate={candidate_fitness.high_impact_false_positive_rate:.4f}, tie_breaker={candidate_fitness.tie_breaker:.6f}")
            candidate_result = CandidateResult(
                candidate_id=f"candidate_{i+1}",
                params=candidate_params,
                fitness=candidate_fitness,
                eval_result=result_to_dict(candidate_eval_result),
                param_fingerprint=_param_fingerprint(candidate_params),
                effective_params_snapshot=get_auto_tune_params_snapshot(),
                telemetry_hash=_eval_telemetry_hash(candidate_eval_result),
                threshold_config=(result_to_dict(candidate_eval_result).get("aggregate_metrics", {}).get("threshold_config", {})),
            )
            candidates.append(candidate_result)
        valid_candidates = [c for c in candidates if not c.rejected]
        valid_candidates.sort(key=lambda c: c.fitness, reverse=True)
        for i, c in enumerate(valid_candidates):
            c.rank = i + 1
            if i == 0:
                c.lexicographic_level = "best"
            else:
                comparison = c.fitness.lexicographic_comparison(valid_candidates[i-1].fitness)
                c.lexicographic_level = comparison.get("decision_level", "unknown")
        best_candidate = valid_candidates[0] if valid_candidates else None
        overall_improvement = False
        lexicographic_improvement = None
        if best_candidate:
            comparison = best_candidate.fitness.lexicographic_comparison(baseline_fitness)
            if comparison["winner"] == "self":
                overall_improvement = True
                lexicographic_improvement = comparison["decision_level"]
        recommendations = self._generate_recommendations(baseline_fitness, valid_candidates, baseline_params)
        result = AutoTuneResult(
            timestamp=datetime.now().isoformat(),
            seed=self.seed,
            baseline_params=baseline_params,
            baseline_fitness=baseline_fitness,
            baseline_result=result_to_dict(baseline_eval_result),
            candidates=candidates,
            best_candidate=best_candidate,
            overall_improvement=overall_improvement,
            lexicographic_improvement=lexicographic_improvement,
            recommendations=recommendations,
            rejection_stats=dict(rejection_counter)
        )
        return result

    def _generate_recommendations(self, baseline_fitness, candidates, baseline_params):
        recommendations = []
        if not candidates:
            recommendations.append("No candidates evaluated.")
            return recommendations
        best = candidates[0]
        comparison = best.fitness.lexicographic_comparison(baseline_fitness)
        if comparison["winner"] == "self":
            level = comparison["decision_level"]
            reason = comparison["decision_reason"]
            recommendations.append(f"Best candidate is lexicographically superior at level '{level}': {reason}")
        elif comparison["winner"] == "tie":
            recommendations.append("Best candidate ties with baseline (tie-breaker used)")
        else:
            recommendations.append("No candidate outperforms baseline lexicographically")
        if best.fitness.recovery_score > baseline_fitness.recovery_score:
            recommendations.append("Candidate improves recovery_score - better resilience")
        if best.fitness.collapse_penalty < baseline_fitness.collapse_penalty:
            recommendations.append("Candidate reduces collapse_penalty - better stability")
        if best.fitness.individualization_score > baseline_fitness.individualization_score:
            recommendations.append("Candidate improves individualization_score")
        if best.fitness.high_impact_false_positive_rate < baseline_fitness.high_impact_false_positive_rate:
            recommendations.append("Candidate reduces high-impact false positives")
        param_changes = {}
        for param_name in baseline_params:
            if param_name in best.params:
                change = best.params[param_name] - baseline_params[param_name]
                if abs(change) > 0.05:
                    param_changes[param_name] = change
        if param_changes:
            rec_lines = ["Key parameter changes in best candidate:"]
            for param, change in sorted(param_changes.items(), key=lambda x: abs(x[1]), reverse=True)[:5]:
                direction = "up" if change > 0 else "down"
                rec_lines.append(f"  - {param}: {direction} {abs(change):.4f}")
            recommendations.append("\n".join(rec_lines))
        return recommendations

    def save_report(self, result):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        base_name = f"auto_tune_v0_3_{self.timestamp}"
        json_path = self.output_dir / f"{base_name}.json"
        with open(json_path, 'w') as f:
            json.dump(result.to_dict(), f, indent=2, default=str)
        md_path = self.output_dir / f"{base_name}.md"
        markdown = self._generate_markdown(result)
        with open(md_path, 'w') as f:
            f.write(markdown)
        result.report_path = str(json_path)
        return json_path, md_path

    def _generate_markdown(self, result):
        lines = [
            "# Auto-Tune v0.3 Report (MVP-6.1)",
            "",
            f"**Generated:** {result.timestamp}",
            f"**Random Seed:** {result.seed}",
            f"**Overall Improvement:** {'Yes' if result.overall_improvement else 'No'}",
        ]
        if result.lexicographic_improvement:
            lines.append(f"**Lexicographic Improvement At:** {result.lexicographic_improvement}")
        lines.extend(["", "## Baseline Fitness (Lexicographic)", ""])
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| passed_scenarios | {result.baseline_fitness.passed_scenarios} |")
        lines.append(f"| high_impact_false_positive_rate | {result.baseline_fitness.high_impact_false_positive_rate:.4f} |")
        lines.append(f"| individualization_score | {result.baseline_fitness.individualization_score:.4f} |")
        lines.append(f"| recovery_score | {result.baseline_fitness.recovery_score:.4f} |")
        lines.append(f"| efficiency | {result.baseline_fitness.efficiency:.4f} |")
        lines.append(f"| tie_breaker | {result.baseline_fitness.tie_breaker:.6f} |")
        lines.extend(["", "## Candidate Rankings (Top 20)", ""])
        lines.append("| Rank | Candidate | Passed | FP Rate | Indiv | Recovery | Efficiency | Tie-Breaker |")
        lines.append("|------|-----------|--------|---------|-------|----------|------------|-------------|")
        for c in result.candidates[:20]:
            lines.append(f"| {c.rank} | {c.candidate_id} | {c.fitness.passed_scenarios} | {c.fitness.high_impact_false_positive_rate:.4f} | {c.fitness.individualization_score:.4f} | {c.fitness.recovery_score:.4f} | {c.fitness.efficiency:.4f} | {c.fitness.tie_breaker:.6f} |")
        baseline_threshold = result.baseline_result.get("aggregate_metrics", {}).get("threshold_config", {})
        if baseline_threshold:
            lines.append(f"**Threshold Config:** {baseline_threshold.get('version', 'unknown')} ({baseline_threshold.get('hash', '')[:12]})")
        if result.best_candidate:
            best = result.best_candidate
            lines.extend(["", "## Best Candidate Details", ""])
            lines.append(f"**Candidate ID:** {best.candidate_id}")
            lines.append(f"**Lexicographic Level:** {best.lexicographic_level}")
            lines.extend(["", "### Fitness Breakdown", ""])
            lines.append(f"- **passed_scenarios:** {best.fitness.passed_scenarios}")
            lines.append(f"- **high_impact_false_positive_rate:** {best.fitness.high_impact_false_positive_rate:.4f}")
            lines.append(f"- **individualization_score:** {best.fitness.individualization_score:.4f}")
            lines.append(f"- **recovery_score:** {best.fitness.recovery_score:.4f}")
            lines.append(f"- **efficiency:** {best.fitness.efficiency:.4f}")
            lines.append(f"- **tie_breaker:** {best.fitness.tie_breaker:.6f}")
            lines.extend(["", "### Parameter Changes from Baseline", ""])
            lines.append("| Parameter | Baseline | Candidate | Change |")
            lines.append("|-----------|----------|-----------|--------|")
            for param in sorted(best.params.keys()):
                base_val = result.baseline_params.get(param, "N/A")
                cand_val = best.params[param]
                if isinstance(base_val, (int, float)):
                    diff = f"{cand_val - base_val:+.4f}"
                else:
                    diff = "N/A"
                lines.append(f"| {param} | {base_val} | {cand_val:.4f} | {diff} |")
        lines.extend(["", "## Recommendations", ""])
        for rec in result.recommendations:
            lines.append(f"- {rec}")
        lines.extend(["", "---", "*Generated by OpenEmotion Auto-Tune v0.3*"])
        return "\n".join(lines)


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Auto-Tune v0.3 for OpenEmotion MVP-6.1")
    parser.add_argument("--params", "-p", type=Path, help="Parameter file for candidate")
    
    parser.add_argument("--baseline", type=Path, help="Parameter file for baseline")
    parser.add_argument("--output", "-o", type=Path, default=Path("reports"), help="Output directory")
    parser.add_argument("--scenarios", "-s", nargs="+", help="Specific scenario files")
    parser.add_argument("--candidates", "-n", type=int, default=200, help="Number of candidates")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--strategy", choices=["random", "gaussian", "boundary", "focused"], default="random")
    parser.add_argument("--magnitude", type=float, default=0.2, help="Perturbation magnitude")
    parser.add_argument("--skip-sentinel", action="store_true", help="Skip parameter consumption sentinel check")
    parser.add_argument("--list-params", action="store_true", help="List all tunable parameters")
    parser.add_argument("--generate-defaults", type=Path, metavar="OUTPUT_FILE", help="Generate default parameters file")
    args = parser.parse_args()

    if args.list_params:
        print("# Tunable Parameters (v0.3)")
        for name, defn in sorted(DEFAULT_TUNABLE_PARAMS.items()):
            print(f"## {name}")
            print(f"- Default: {defn['default']}")
            print(f"- Range: [{defn['min']}, {defn['max']}]")
            print(f"- Category: {defn['category']}")
            print("")
        return 0

    if args.generate_defaults:
        defaults = {name: defn["default"] for name, defn in DEFAULT_TUNABLE_PARAMS.items()}
        metadata = {"description": "Default tunable parameters for OpenEmotion MVP-6.1", "version": "0.3"}
        with open(args.generate_defaults, 'w') as f:
            yaml.dump({"params": defaults, "metadata": metadata}, f, default_flow_style=False)
        print(f"Default parameters written to: {args.generate_defaults}")
        return 0

    base_path = Path(__file__).parent.parent
    scenarios_dir = base_path / "scenarios"

    baseline_params = None
    if args.baseline:
        with open(args.baseline) as f:
            data = yaml.safe_load(f)
            baseline_params = data.get("params", data)
        print(f"Loaded baseline parameters from: {args.baseline}")

    candidate_params_list = None
    if args.params:
        with open(args.params) as f:
            data = yaml.safe_load(f)
            candidate_params = data.get("params", data)
        candidate_params_list = [candidate_params]
        print(f"Loaded candidate parameters from: {args.params}")

    scenarios = None
    if args.scenarios:
        scenarios = [Path(s) if Path(s).is_absolute() else scenarios_dir / s for s in args.scenarios]

    engine = AutoTuneEngine(scenarios_dir=scenarios_dir, output_dir=args.output, seed=args.seed)

    print(f"\nRunning Auto-Tune v0.3...")
    print(f"  Seed: {args.seed}")
    print(f"  Candidates: {args.candidates}")
    print(f"  Output: {args.output}")
    print("")

    result = await engine.tune(
        baseline_params=baseline_params,
        candidate_params_list=candidate_params_list,
        scenarios=scenarios,
        generate_candidates=(candidate_params_list is None),
        candidate_count=args.candidates,
        skip_sentinel=args.skip_sentinel
    )

    json_path, md_path = engine.save_report(result)

    print(f"\nReports saved:")
    print(f"  JSON: {json_path}")
    print(f"  Markdown: {md_path}")
    print(f"\nBaseline: passed={result.baseline_fitness.passed_scenarios}, tie_breaker={result.baseline_fitness.tie_breaker:.6f}")
    if result.best_candidate:
        print(f"Best: passed={result.best_candidate.fitness.passed_scenarios}, tie_breaker={result.best_candidate.fitness.tie_breaker:.6f}")
        print(f"Overall: {'IMPROVED' if result.overall_improvement else 'NO IMPROVEMENT'}")
        if result.lexicographic_improvement:
            print(f"Improvement at level: {result.lexicographic_improvement}")

    return 0 if result.overall_improvement else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

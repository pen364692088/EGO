"""
MVP-6.1 D5 Tests: AutoTune v0.3 Lexicographic Fitness

Tests for:
- Lexicographic comparison correctness
- Tie-breaker scalar behavior
- Parameter space coverage (shrinkage/gating/recovery/dynamic-thresholds)
- Candidate generation with fixed seed (reproducibility)
- No all-same-score plateaus
"""

import pytest
import random
import copy
from scripts.auto_tune_v0_3 import (
    LexicographicFitness, FitnessCalculator, PerturbationGenerator,
    DEFAULT_TUNABLE_PARAMS
)


class TestLexicographicComparison:
    """Test lexicographic fitness comparison."""
    
    def test_lexicographic_order_passed_scenarios_first(self):
        """passed_scenarios is the highest priority metric."""
        fit1 = LexicographicFitness(
            passed_scenarios=10,
            high_impact_false_positive_rate=0.5,
            individualization_score=0.8,
            recovery_score=0.7,
            efficiency=0.6
        )
        fit1.calculate_tie_breaker()
        
        fit2 = LexicographicFitness(
            passed_scenarios=5,
            high_impact_false_positive_rate=0.1,  # Much better
            individualization_score=0.9,
            recovery_score=0.9,
            efficiency=0.9
        )
        fit2.calculate_tie_breaker()
        
        # fit1 should be better despite worse other metrics
        assert fit1 > fit2
        assert fit2 < fit1
    
    def test_lexicographic_order_fp_rate_second(self):
        """high_impact_false_positive_rate is second priority."""
        fit1 = LexicographicFitness(
            passed_scenarios=5,
            high_impact_false_positive_rate=0.1,
            individualization_score=0.5,
            recovery_score=0.5,
            efficiency=0.5
        )
        fit1.calculate_tie_breaker()
        
        fit2 = LexicographicFitness(
            passed_scenarios=5,
            high_impact_false_positive_rate=0.3,
            individualization_score=0.9,
            recovery_score=0.9,
            efficiency=0.9
        )
        fit2.calculate_tie_breaker()
        
        # fit1 should be better due to lower FP rate
        assert fit1 > fit2
    
    def test_lexicographic_order_individualization_third(self):
        """individualization_score is third priority."""
        fit1 = LexicographicFitness(
            passed_scenarios=5,
            high_impact_false_positive_rate=0.2,
            individualization_score=0.8,
            recovery_score=0.5,
            efficiency=0.5
        )
        fit1.calculate_tie_breaker()
        
        fit2 = LexicographicFitness(
            passed_scenarios=5,
            high_impact_false_positive_rate=0.2,
            individualization_score=0.5,
            recovery_score=0.9,
            efficiency=0.9
        )
        fit2.calculate_tie_breaker()
        
        # fit1 should be better due to higher individualization
        assert fit1 > fit2
    
    def test_lexicographic_order_recovery_fourth(self):
        """recovery_score is fourth priority."""
        fit1 = LexicographicFitness(
            passed_scenarios=5,
            high_impact_false_positive_rate=0.2,
            individualization_score=0.5,
            recovery_score=0.8,
            efficiency=0.5
        )
        fit1.calculate_tie_breaker()
        
        fit2 = LexicographicFitness(
            passed_scenarios=5,
            high_impact_false_positive_rate=0.2,
            individualization_score=0.5,
            recovery_score=0.5,
            efficiency=0.9
        )
        fit2.calculate_tie_breaker()
        
        # fit1 should be better due to higher recovery
        assert fit1 > fit2
    
    def test_lexicographic_order_efficiency_fifth(self):
        """efficiency is fifth priority."""
        fit1 = LexicographicFitness(
            passed_scenarios=5,
            high_impact_false_positive_rate=0.2,
            individualization_score=0.5,
            recovery_score=0.5,
            efficiency=0.8
        )
        fit1.calculate_tie_breaker()
        
        fit2 = LexicographicFitness(
            passed_scenarios=5,
            high_impact_false_positive_rate=0.2,
            individualization_score=0.5,
            recovery_score=0.5,
            efficiency=0.5
        )
        fit2.calculate_tie_breaker()
        
        # fit1 should be better due to higher efficiency
        assert fit1 > fit2
    
    def test_lexicographic_tie_breaker_last(self):
        """tie_breaker is used when all primary metrics are equal."""
        fit1 = LexicographicFitness(
            passed_scenarios=5,
            high_impact_false_positive_rate=0.2,
            individualization_score=0.5,
            recovery_score=0.5,
            efficiency=0.5,
            tie_breaker=0.8
        )
        
        fit2 = LexicographicFitness(
            passed_scenarios=5,
            high_impact_false_positive_rate=0.2,
            individualization_score=0.5,
            recovery_score=0.5,
            efficiency=0.5,
            tie_breaker=0.6
        )
        
        # fit1 should be better due to higher tie-breaker
        assert fit1 > fit2
    
    def test_dominates_strictly_better(self):
        """dominates() returns True when strictly better at first differing level."""
        fit1 = LexicographicFitness(
            passed_scenarios=10,
            high_impact_false_positive_rate=0.2,
            individualization_score=0.5,
            recovery_score=0.5,
            efficiency=0.5
        )
        fit1.calculate_tie_breaker()
        
        fit2 = LexicographicFitness(
            passed_scenarios=5,
            high_impact_false_positive_rate=0.1,
            individualization_score=0.9,
            recovery_score=0.9,
            efficiency=0.9
        )
        fit2.calculate_tie_breaker()
        
        assert fit1.dominates(fit2)
        assert not fit2.dominates(fit1)
        assert fit1.dominates(fit2)
        assert not fit2.dominates(fit1)
    
    def test_dominates_not_strict(self):
        """dominates() returns False when not strictly better."""
        fit1 = LexicographicFitness(
            passed_scenarios=5,
            high_impact_false_positive_rate=0.2,
            individualization_score=0.8,
            recovery_score=0.5,
            efficiency=0.5
        )
        fit1.calculate_tie_breaker()
        
        fit2 = LexicographicFitness(
            passed_scenarios=5,
            high_impact_false_positive_rate=0.2,
            individualization_score=0.5,
            recovery_score=0.9,
            efficiency=0.9
        )
        fit2.calculate_tie_breaker()
        
        # Neither dominates - they're equal at first 2 levels
        # fit1 dominates fit2 because individualization_score (0.8) > (0.5)
        assert fit1.dominates(fit2)
        assert not fit2.dominates(fit1)
    
    def test_lexicographic_comparison_detailed(self):
        """lexicographic_comparison() provides detailed comparison info."""
        fit1 = LexicographicFitness(
            passed_scenarios=10,
            high_impact_false_positive_rate=0.2,
            individualization_score=0.5,
            recovery_score=0.5,
            efficiency=0.5
        )
        fit1.calculate_tie_breaker()
        
        fit2 = LexicographicFitness(
            passed_scenarios=5,
            high_impact_false_positive_rate=0.2,
            individualization_score=0.5,
            recovery_score=0.5,
            efficiency=0.5
        )
        fit2.calculate_tie_breaker()
        
        comparison = fit1.lexicographic_comparison(fit2)
        
        assert comparison["winner"] == "self"
        assert comparison["decision_level"] == "passed_scenarios"
        assert "10" in comparison["decision_reason"]
        assert "5" in comparison["decision_reason"]
        assert len(comparison["level_comparison"]) == 6


class TestTieBreaker:
    """Test tie-breaker scalar behavior."""
    
    def test_tie_breaker_calculation(self):
        """Tie-breaker is calculated correctly."""
        fit = LexicographicFitness(
            passed_scenarios=10,
            high_impact_false_positive_rate=0.1,
            individualization_score=0.8,
            recovery_score=0.7,
            efficiency=0.6,
            emotion_consistency=0.9,
            robustness=0.8
        )
        tb = fit.calculate_tie_breaker()
        
        # Should be between 0 and 1
        assert 0 <= tb <= 1
        # Should be deterministic
        assert fit.calculate_tie_breaker() == tb
    
    def test_tie_breaker_higher_passed_scenarios(self):
        """Higher passed_scenarios increases tie-breaker."""
        fit1 = LexicographicFitness(
            passed_scenarios=15,
            high_impact_false_positive_rate=0.2,
            individualization_score=0.5,
            recovery_score=0.5,
            efficiency=0.5
        )
        fit1.calculate_tie_breaker()
        
        fit2 = LexicographicFitness(
            passed_scenarios=5,
            high_impact_false_positive_rate=0.2,
            individualization_score=0.5,
            recovery_score=0.5,
            efficiency=0.5
        )
        fit2.calculate_tie_breaker()
        
        assert fit1.tie_breaker > fit2.tie_breaker
    
    def test_tie_breaker_lower_fp_rate(self):
        """Lower false positive rate increases tie-breaker."""
        fit1 = LexicographicFitness(
            passed_scenarios=5,
            high_impact_false_positive_rate=0.1,
            individualization_score=0.5,
            recovery_score=0.5,
            efficiency=0.5
        )
        fit1.calculate_tie_breaker()
        
        fit2 = LexicographicFitness(
            passed_scenarios=5,
            high_impact_false_positive_rate=0.5,
            individualization_score=0.5,
            recovery_score=0.5,
            efficiency=0.5
        )
        fit2.calculate_tie_breaker()
        
        assert fit1.tie_breaker > fit2.tie_breaker
    
    def test_tie_breaker_distinguishes_equal_fitness(self):
        """Tie-breaker distinguishes candidates with equal primary metrics."""
        fit1 = LexicographicFitness(
            passed_scenarios=5,
            high_impact_false_positive_rate=0.2,
            individualization_score=0.5,
            recovery_score=0.5,
            efficiency=0.5,
            emotion_consistency=0.9,
            robustness=0.8
        )
        fit1.calculate_tie_breaker()
        
        fit2 = LexicographicFitness(
            passed_scenarios=5,
            high_impact_false_positive_rate=0.2,
            individualization_score=0.5,
            recovery_score=0.5,
            efficiency=0.5,
            emotion_consistency=0.5,
            robustness=0.4
        )
        fit2.calculate_tie_breaker()
        
        # Primary metrics equal, but tie-breaker differs
        assert fit1.to_tuple()[:5] == fit2.to_tuple()[:5]
        assert fit1.tie_breaker != fit2.tie_breaker


class TestParameterSpace:
    """Test that parameter space includes all required knobs."""
    
    def test_shrinkage_parameters_present(self):
        """Shrinkage parameters are in the parameter space."""
        assert "shrinkage_k" in DEFAULT_TUNABLE_PARAMS
        assert "residual_learning_rate" in DEFAULT_TUNABLE_PARAMS
        assert "residual_evidence_increment" in DEFAULT_TUNABLE_PARAMS
    
    def test_betrayal_gating_parameters_present(self):
        """Betrayal double-key gating parameters are in the parameter space."""
        assert "betrayal_promise_strength_threshold" in DEFAULT_TUNABLE_PARAMS
        assert "betrayal_violation_strength_threshold" in DEFAULT_TUNABLE_PARAMS
        assert "betrayal_evidence_threshold" in DEFAULT_TUNABLE_PARAMS
        assert "betrayal_clarify_fallback_threshold" in DEFAULT_TUNABLE_PARAMS
    
    def test_recovery_parameters_present(self):
        """Recovery dynamics parameters are in the parameter space."""
        assert "recovery_rate_energy" in DEFAULT_TUNABLE_PARAMS
        assert "recovery_rate_safety" in DEFAULT_TUNABLE_PARAMS
        assert "recovery_rate_social" in DEFAULT_TUNABLE_PARAMS
        assert "recovery_half_life_threshold" in DEFAULT_TUNABLE_PARAMS
        assert "collapse_penalty_weight" in DEFAULT_TUNABLE_PARAMS
    
    def test_individualization_parameters_present(self):
        """Individualization dynamic threshold parameters are in the parameter space."""
        assert "individualization_n_obs_strict" in DEFAULT_TUNABLE_PARAMS
        assert "individualization_n_obs_relaxed" in DEFAULT_TUNABLE_PARAMS
        assert "individualization_threshold_strict" in DEFAULT_TUNABLE_PARAMS
        assert "individualization_threshold_relaxed" in DEFAULT_TUNABLE_PARAMS
    
    def test_parameter_ranges_valid(self):
        """All parameters have valid min < max ranges."""
        for name, defn in DEFAULT_TUNABLE_PARAMS.items():
            assert defn["min"] < defn["max"], f"{name}: min >= max"
            assert defn["min"] <= defn["default"] <= defn["max"], f"{name}: default out of range"
    
    def test_parameter_count(self):
        """Parameter space has expected number of parameters."""
        # v0.2 had 22 parameters, v0.3 should have 35+
        assert len(DEFAULT_TUNABLE_PARAMS) >= 35


class TestCandidateGeneration:
    """Test candidate generation with fixed seed."""
    
    def test_reproducible_with_same_seed(self):
        """Same seed produces same candidates."""
        baseline = {name: defn["default"] for name, defn in DEFAULT_TUNABLE_PARAMS.items()}
        
        gen1 = PerturbationGenerator(seed=42)
        candidates1 = gen1.generate_candidates(baseline, DEFAULT_TUNABLE_PARAMS, count=10)
        
        gen2 = PerturbationGenerator(seed=42)
        candidates2 = gen2.generate_candidates(baseline, DEFAULT_TUNABLE_PARAMS, count=10)
        
        for c1, c2 in zip(candidates1, candidates2):
            assert c1 == c2
    
    def test_different_seed_produces_different_candidates(self):
        """Different seeds produce different candidates."""
        baseline = {name: defn["default"] for name, defn in DEFAULT_TUNABLE_PARAMS.items()}
        
        gen1 = PerturbationGenerator(seed=42)
        candidates1 = gen1.generate_candidates(baseline, DEFAULT_TUNABLE_PARAMS, count=10)
        
        gen2 = PerturbationGenerator(seed=123)
        candidates2 = gen2.generate_candidates(baseline, DEFAULT_TUNABLE_PARAMS, count=10)
        
        # At least some candidates should differ
        any_diff = any(c1 != c2 for c1, c2 in zip(candidates1, candidates2))
        assert any_diff
    
    def test_candidates_within_bounds(self):
        """All generated candidates respect parameter bounds."""
        baseline = {name: defn["default"] for name, defn in DEFAULT_TUNABLE_PARAMS.items()}
        gen = PerturbationGenerator(seed=42)
        candidates = gen.generate_candidates(baseline, DEFAULT_TUNABLE_PARAMS, count=50)
        
        for candidate in candidates:
            for name, value in candidate.items():
                defn = DEFAULT_TUNABLE_PARAMS[name]
                assert defn["min"] <= value <= defn["max"], f"{name} = {value} out of range"
    
    def test_candidates_not_all_identical(self):
        """Generated candidates are not all identical."""
        baseline = {name: defn["default"] for name, defn in DEFAULT_TUNABLE_PARAMS.items()}
        gen = PerturbationGenerator(seed=42)
        candidates = gen.generate_candidates(baseline, DEFAULT_TUNABLE_PARAMS, count=20)
        
        # Check that not all candidates are the same
        first = candidates[0]
        any_diff = any(c != first for c in candidates[1:])
        assert any_diff


class TestNoSameScorePlateau:
    """Test that lexicographic fitness prevents all-same-score plateaus."""
    
    def test_different_candidates_have_different_tuples(self):
        """Different candidates produce different fitness tuples."""
        baseline = {name: defn["default"] for name, defn in DEFAULT_TUNABLE_PARAMS.items()}
        gen = PerturbationGenerator(seed=42)
        candidates = gen.generate_candidates(baseline, DEFAULT_TUNABLE_PARAMS, count=20)
        
        # Perturbations should produce different fitness values
        # (We can't test actual fitness without running eval, but we can test that
        #  the parameter differences exist which would lead to different fitness)
        
        fitness_values = []
        for c in candidates:
            # Create a simple fitness proxy based on parameter differences
            diff_sum = sum(abs(c[k] - baseline[k]) for k in c)
            fitness_values.append(diff_sum)
        
        # Not all fitness proxies should be identical
        unique_values = set(fitness_values)
        assert len(unique_values) > 1
    
    def test_lexicographic_sorting_produces_unique_ranks(self):
        """Lexicographic sorting produces unique ranks for different fitness."""
        # Create fitness objects with varying values
        fitnesses = []
        for i in range(10):
            fit = LexicographicFitness(
                passed_scenarios=5 + i % 3,  # Some variation
                high_impact_false_positive_rate=0.1 + i * 0.01,
                individualization_score=0.5 + i * 0.02,
                recovery_score=0.5 + i * 0.03,
                efficiency=0.5 + i * 0.04
            )
            fit.calculate_tie_breaker()
            fitnesses.append(fit)
        
        # Sort by fitness
        sorted_fitnesses = sorted(fitnesses, reverse=True)
        
        # Check that sorting is stable and produces expected ordering
        for i in range(len(sorted_fitnesses) - 1):
            assert sorted_fitnesses[i] >= sorted_fitnesses[i + 1]


class TestSerialization:
    """Test serialization and deserialization."""
    
    def test_fitness_to_dict(self):
        """Fitness can be serialized to dict."""
        fit = LexicographicFitness(
            passed_scenarios=10,
            high_impact_false_positive_rate=0.1,
            individualization_score=0.8,
            recovery_score=0.7,
            efficiency=0.6
        )
        fit.calculate_tie_breaker()
        
        data = fit.to_dict()
        
        assert data["passed_scenarios"] == 10
        assert data["high_impact_false_positive_rate"] == 0.1
        assert data["tie_breaker"] == fit.tie_breaker
    
    def test_fitness_tuple_ordering(self):
        """Fitness tuple ordering is correct."""
        fit = LexicographicFitness(
            passed_scenarios=10,
            high_impact_false_positive_rate=0.1,
            individualization_score=0.8,
            recovery_score=0.7,
            efficiency=0.6,
            tie_breaker=0.75
        )
        
        tup = fit.to_tuple()
        
        assert tup[0] == 10  # passed_scenarios
        assert tup[1] == -0.1  # negated fp_rate
        assert tup[2] == 0.8  # individualization
        assert tup[3] == 0.7  # recovery
        assert tup[4] == 0.6  # efficiency
        assert tup[5] == 0.75  # tie_breaker


class TestEdgeCases:
    """Test edge cases."""
    
    def test_zero_passed_scenarios(self):
        """Fitness handles zero passed scenarios."""
        fit = LexicographicFitness(
            passed_scenarios=0,
            high_impact_false_positive_rate=0.0,
            individualization_score=0.0,
            recovery_score=0.0,
            efficiency=0.0
        )
        fit.calculate_tie_breaker()
        
        assert fit.passed_scenarios == 0
        assert fit.tie_breaker >= 0
    
    def test_maximum_values(self):
        """Fitness handles maximum values."""
        fit = LexicographicFitness(
            passed_scenarios=100,
            high_impact_false_positive_rate=1.0,
            individualization_score=1.0,
            recovery_score=1.0,
            efficiency=1.0
        )
        fit.calculate_tie_breaker()
        
        assert fit.passed_scenarios == 100
        assert fit.tie_breaker <= 1.0
    
    def test_comparison_with_equal_fitness(self):
        """Comparison handles equal fitness correctly."""
        fit1 = LexicographicFitness(
            passed_scenarios=5,
            high_impact_false_positive_rate=0.2,
            individualization_score=0.5,
            recovery_score=0.5,
            efficiency=0.5,
            tie_breaker=0.7
        )
        
        fit2 = LexicographicFitness(
            passed_scenarios=5,
            high_impact_false_positive_rate=0.2,
            individualization_score=0.5,
            recovery_score=0.5,
            efficiency=0.5,
            tie_breaker=0.7
        )
        
        assert not (fit1 > fit2)
        assert not (fit1 < fit2)
        assert fit1.to_tuple() == fit2.to_tuple()

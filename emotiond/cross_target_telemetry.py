"""
MVP-5.1 D3: Cross-Target Interference Telemetry

Decomposes cross_target_interference into measurable sub-components:
- state_leak_global_to_target: Global emotion state affecting target-specific responses
- target_state_leak_between_targets: State from one target leaking to another
- shared_self_model_leak: Self-model changes affecting unrelated targets
- ledger_promise_leak: Promises from one target affecting another
- relationship_contamination: Relationship state bleeding between targets

Provides diagnostics output for isolation testing.
"""

import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class InterferenceType(Enum):
    """Types of cross-target interference."""
    STATE_LEAK_GLOBAL_TO_TARGET = "state_leak_global_to_target"
    TARGET_STATE_LEAK_BETWEEN_TARGETS = "target_state_leak_between_targets"
    SHARED_SELF_MODEL_LEAK = "shared_self_model_leak"
    LEDGER_PROMISE_LEAK = "ledger_promise_leak"
    RELATIONSHIP_CONTAMINATION = "relationship_contamination"


@dataclass
class InterferenceMeasurement:
    """Single interference measurement."""
    interference_type: InterferenceType
    source_target: Optional[str]
    affected_target: Optional[str]
    metric_name: str
    expected_value: float
    actual_value: float
    deviation: float
    severity: float  # 0.0-1.0
    timestamp: float = field(default_factory=time.time)
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "interference_type": self.interference_type.value,
            "source_target": self.source_target,
            "affected_target": self.affected_target,
            "metric_name": self.metric_name,
            "expected_value": self.expected_value,
            "actual_value": self.actual_value,
            "deviation": self.deviation,
            "severity": self.severity,
            "timestamp": self.timestamp,
            "context": self.context
        }


@dataclass
class CrossTargetInterferenceReport:
    """Complete cross-target interference report."""
    scenario_name: str
    start_time: float
    end_time: Optional[float] = None
    measurements: List[InterferenceMeasurement] = field(default_factory=list)
    
    # Component scores (0.0 = no interference, 1.0 = complete leakage)
    state_leak_global_to_target: float = 0.0
    target_state_leak_between_targets: float = 0.0
    shared_self_model_leak: float = 0.0
    ledger_promise_leak: float = 0.0
    relationship_contamination: float = 0.0
    
    # Aggregate score
    total_interference_score: float = 0.0
    
    def add_measurement(self, measurement: InterferenceMeasurement) -> None:
        """Add a measurement and update component scores."""
        self.measurements.append(measurement)
        self._update_component_score(measurement)
    
    def _update_component_score(self, measurement: InterferenceMeasurement) -> None:
        """Update component score based on measurement."""
        if measurement.interference_type == InterferenceType.STATE_LEAK_GLOBAL_TO_TARGET:
            self.state_leak_global_to_target = max(self.state_leak_global_to_target, measurement.severity)
        elif measurement.interference_type == InterferenceType.TARGET_STATE_LEAK_BETWEEN_TARGETS:
            self.target_state_leak_between_targets = max(self.target_state_leak_between_targets, measurement.severity)
        elif measurement.interference_type == InterferenceType.SHARED_SELF_MODEL_LEAK:
            self.shared_self_model_leak = max(self.shared_self_model_leak, measurement.severity)
        elif measurement.interference_type == InterferenceType.LEDGER_PROMISE_LEAK:
            self.ledger_promise_leak = max(self.ledger_promise_leak, measurement.severity)
        elif measurement.interference_type == InterferenceType.RELATIONSHIP_CONTAMINATION:
            self.relationship_contamination = max(self.relationship_contamination, measurement.severity)
        
        # Recalculate total
        self._calculate_total()
    
    def _calculate_total(self) -> None:
        """Calculate total interference score (weighted average)."""
        weights = {
            "state_leak_global_to_target": 0.2,
            "target_state_leak_between_targets": 0.25,
            "shared_self_model_leak": 0.2,
            "ledger_promise_leak": 0.15,
            "relationship_contamination": 0.2
        }
        
        self.total_interference_score = (
            self.state_leak_global_to_target * weights["state_leak_global_to_target"] +
            self.target_state_leak_between_targets * weights["target_state_leak_between_targets"] +
            self.shared_self_model_leak * weights["shared_self_model_leak"] +
            self.ledger_promise_leak * weights["ledger_promise_leak"] +
            self.relationship_contamination * weights["relationship_contamination"]
        )
    
    def finalize(self) -> None:
        """Finalize the report."""
        self.end_time = time.time()
        self._calculate_total()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": (self.end_time - self.start_time) if self.end_time else None,
            "component_scores": {
                "state_leak_global_to_target": self.state_leak_global_to_target,
                "target_state_leak_between_targets": self.target_state_leak_between_targets,
                "shared_self_model_leak": self.shared_self_model_leak,
                "ledger_promise_leak": self.ledger_promise_leak,
                "relationship_contamination": self.relationship_contamination
            },
            "total_interference_score": self.total_interference_score,
            "interference_grade": self._get_grade(),
            "measurements": [m.to_dict() for m in self.measurements],
            "summary": self._generate_summary()
        }
    
    def _get_grade(self) -> str:
        """Get letter grade based on interference score."""
        if self.total_interference_score < 0.1:
            return "A"  # Excellent isolation
        elif self.total_interference_score < 0.2:
            return "B"  # Good isolation
        elif self.total_interference_score < 0.35:
            return "C"  # Acceptable
        elif self.total_interference_score < 0.5:
            return "D"  # Poor isolation
        else:
            return "F"  # Critical leakage
    
    def _generate_summary(self) -> str:
        """Generate human-readable summary."""
        parts = [
            f"Cross-Target Interference Report: {self.scenario_name}",
            f"Grade: {self._get_grade()} (Score: {self.total_interference_score:.3f})",
            "",
            "Component Breakdown:",
            f"  - Global→Target State Leak: {self.state_leak_global_to_target:.3f}",
            f"  - Target→Target Leak: {self.target_state_leak_between_targets:.3f}",
            f"  - Self-Model Leak: {self.shared_self_model_leak:.3f}",
            f"  - Ledger Promise Leak: {self.ledger_promise_leak:.3f}",
            f"  - Relationship Contamination: {self.relationship_contamination:.3f}",
            "",
            f"Total Measurements: {len(self.measurements)}"
        ]
        
        # Add top issues
        high_severity = [m for m in self.measurements if m.severity > 0.3]
        if high_severity:
            parts.extend(["", "High Severity Issues:"])
            for m in sorted(high_severity, key=lambda x: x.severity, reverse=True)[:5]:
                parts.append(f"  - {m.interference_type.value}: {m.metric_name} = {m.severity:.3f}")
        
        return "\n".join(parts)


class CrossTargetTelemetry:
    """Telemetry collector for cross-target interference."""
    
    def __init__(self):
        self.active_reports: Dict[str, CrossTargetInterferenceReport] = {}
        self.completed_reports: List[CrossTargetInterferenceReport] = []
    
    def start_scenario(self, scenario_name: str) -> str:
        """Start tracking a new scenario."""
        report = CrossTargetInterferenceReport(
            scenario_name=scenario_name,
            start_time=time.time()
        )
        self.active_reports[scenario_name] = report
        return scenario_name
    
    def record_measurement(
        self,
        scenario_name: str,
        interference_type: InterferenceType,
        metric_name: str,
        expected_value: float,
        actual_value: float,
        source_target: Optional[str] = None,
        affected_target: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record an interference measurement."""
        if scenario_name not in self.active_reports:
            return
        
        deviation = abs(actual_value - expected_value)
        # Severity is deviation normalized to 0-1, capped at 1.0
        severity = min(1.0, deviation / max(abs(expected_value), 0.1) if expected_value != 0 else deviation)
        
        measurement = InterferenceMeasurement(
            interference_type=interference_type,
            source_target=source_target,
            affected_target=affected_target,
            metric_name=metric_name,
            expected_value=expected_value,
            actual_value=actual_value,
            deviation=deviation,
            severity=severity,
            context=context or {}
        )
        
        self.active_reports[scenario_name].add_measurement(measurement)
    
    def finalize_scenario(self, scenario_name: str) -> Optional[CrossTargetInterferenceReport]:
        """Finalize a scenario report."""
        if scenario_name not in self.active_reports:
            return None
        
        report = self.active_reports.pop(scenario_name)
        report.finalize()
        self.completed_reports.append(report)
        return report
    
    def get_report(self, scenario_name: str) -> Optional[CrossTargetInterferenceReport]:
        """Get an active or completed report."""
        if scenario_name in self.active_reports:
            return self.active_reports[scenario_name]
        for report in self.completed_reports:
            if report.scenario_name == scenario_name:
                return report
        return None
    
    def get_all_reports(self) -> List[CrossTargetInterferenceReport]:
        """Get all completed reports."""
        return self.completed_reports.copy()


# Global telemetry instance
telemetry = CrossTargetTelemetry()


def measure_global_state_impact(
    scenario_name: str,
    target_id: str,
    global_valence: float,
    target_expected_valence: float,
    actual_valence: float,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Measure if global emotion state is inappropriately affecting target responses.
    
    This detects when the shared global emotion_state leaks into target-specific
    processing in ways that shouldn't happen.
    """
    # Calculate expected impact from global state
    # If global state is heavily influencing target response when it shouldn't,
    # that's a leak
    
    # Simple heuristic: if target's valence tracks global valence too closely
    # when target has had no recent interactions, that's leakage
    global_to_target_correlation = abs(actual_valence - target_expected_valence)
    
    telemetry.record_measurement(
        scenario_name=scenario_name,
        interference_type=InterferenceType.STATE_LEAK_GLOBAL_TO_TARGET,
        metric_name="valence_correlation",
        expected_value=target_expected_valence,
        actual_value=actual_valence,
        affected_target=target_id,
        context={
            "global_valence": global_valence,
            "correlation": global_to_target_correlation,
            **(context or {})
        }
    )


def measure_target_to_target_leak(
    scenario_name: str,
    source_target: str,
    affected_target: str,
    metric_name: str,
    expected_value: float,
    actual_value: float,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Measure if state from one target is leaking to another target.
    
    This is the core isolation metric - actions from target A should not
    affect target B's state.
    """
    telemetry.record_measurement(
        scenario_name=scenario_name,
        interference_type=InterferenceType.TARGET_STATE_LEAK_BETWEEN_TARGETS,
        metric_name=metric_name,
        expected_value=expected_value,
        actual_value=actual_value,
        source_target=source_target,
        affected_target=affected_target,
        context=context or {}
    )


def measure_ledger_isolation(
    scenario_name: str,
    source_target: str,
    check_target: str,
    has_promise_from_source: bool,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Measure if ledger promises are properly isolated per target.
    
    Target B should never see promises made by target A.
    """
    # If check_target has promise state from source_target, that's a leak
    expected = False  # Should never have another target's promise
    actual = has_promise_from_source
    
    telemetry.record_measurement(
        scenario_name=scenario_name,
        interference_type=InterferenceType.LEDGER_PROMISE_LEAK,
        metric_name=f"promise_from_{source_target}",
        expected_value=0.0,  # Binary: 0 = no leak, 1 = leak
        actual_value=1.0 if actual else 0.0,
        source_target=source_target,
        affected_target=check_target,
        context=context or {}
    )


def measure_relationship_isolation(
    scenario_name: str,
    source_target: str,
    affected_target: str,
    bond_before: float,
    bond_after: float,
    grudge_before: float,
    grudge_after: float,
    expected_bond_change: float = 0.0,
    expected_grudge_change: float = 0.0,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Measure if relationship state is properly isolated.
    
    Target B's bond/grudge should not change when target A receives events.
    """
    actual_bond_change = bond_after - bond_before
    actual_grudge_change = grudge_after - grudge_before
    
    # Record bond contamination
    telemetry.record_measurement(
        scenario_name=scenario_name,
        interference_type=InterferenceType.RELATIONSHIP_CONTAMINATION,
        metric_name="bond_change",
        expected_value=expected_bond_change,
        actual_value=actual_bond_change,
        source_target=source_target,
        affected_target=affected_target,
        context={
            "bond_before": bond_before,
            "bond_after": bond_after,
            **(context or {})
        }
    )
    
    # Record grudge contamination
    telemetry.record_measurement(
        scenario_name=scenario_name,
        interference_type=InterferenceType.RELATIONSHIP_CONTAMINATION,
        metric_name="grudge_change",
        expected_value=expected_grudge_change,
        actual_value=actual_grudge_change,
        source_target=source_target,
        affected_target=affected_target,
        context={
            "grudge_before": grudge_before,
            "grudge_after": grudge_after,
            **(context or {})
        }
    )


def measure_self_model_isolation(
    scenario_name: str,
    target_id: str,
    self_model_values: Dict[str, float],
    expected_per_target_variance: float,
    actual_variance: float,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Measure if self-model is properly isolated or shared appropriately.
    
    Some self-model aspects should be global (identity), others per-target.
    """
    telemetry.record_measurement(
        scenario_name=scenario_name,
        interference_type=InterferenceType.SHARED_SELF_MODEL_LEAK,
        metric_name="value_variance",
        expected_value=expected_per_target_variance,
        actual_value=actual_variance,
        affected_target=target_id,
        context={
            "self_model_values": self_model_values,
            **(context or {})
        }
    )


def get_diagnostics_output(scenario_name: str) -> Dict[str, Any]:
    """Get full diagnostics output for a scenario."""
    report = telemetry.get_report(scenario_name)
    if report is None:
        return {"error": f"No report found for scenario: {scenario_name}"}
    
    return report.to_dict()

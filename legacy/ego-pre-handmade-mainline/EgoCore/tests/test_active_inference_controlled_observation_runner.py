from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TASK_ROOT = ROOT / "docs" / "codex" / "tasks" / "ai-self-awareness-minimal-framework"
MANIFEST_PATH = TASK_ROOT / "CONTROLLED_OBSERVATION_BANK_MANIFEST.json"
RUNNER_PATH = ROOT / "scripts" / "codex" / "run_active_inference_controlled_observation.py"
BATCH_PATH = ROOT / "scripts" / "codex" / "run_active_inference_controlled_observation_batch.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_controlled_observation_manifest_is_canonical_and_minimum_sized() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["schema_version"] == "active_inference.controlled_observation_manifest.v1"
    assert manifest["runner_contract"] == {
        "baseline_a_id": "mvs_baseline_proto_self_mainline",
        "baseline_b_id": "baseline_chat_surface",
        "candidate_id": "mvs_challenger_active_inference_self_model",
        "supported_variant_ids": [
            "mvs_baseline_proto_self_mainline",
            "baseline_chat_surface",
            "mvs_challenger_active_inference_self_model",
        ],
        "transport_source": "runtime_harness",
        "source": "runtime_harness",
        "observation_record_schema": "observation_record.v1",
        "proto_self_state_scope": "experiment",
        "experiment_id_template": "active_inference_controlled_observation:{scenario_id}",
        "segment_session_id_template": "session:active_inference_controlled_observation:{scenario_id}:{segment_id}",
    }
    assert manifest["scenario_count"] == 9
    assert manifest["family_counts"] == {
        "identity_continuity": 3,
        "decision_conflict": 3,
        "failure_repair_retry": 3,
    }
    scenarios = list(manifest.get("scenarios") or [])
    assert sum(1 for item in scenarios if item.get("external_result_steps")) >= 3


def test_case_verdict_requires_repair_closure_for_failure_family() -> None:
    module = _load_module(RUNNER_PATH, "active_inference_controlled_observation_runner")
    verdict = module._case_verdict(
        {
            "case_id": "failure_repair_retry_file_blocked",
            "family": "failure_repair_retry",
            "expected_scoring_surface": {
                "targets": ["T3", "T4", "T5"],
                "probe_key": "tool:file",
                "requires_repair_closure": True,
            },
            "steps": [
                {
                    "step_id": "tool_002",
                    "kind": "tool_result",
                    "policy_hint": {"guard_reason": "viability_pressure", "mvs_tension_active": True},
                    "response_tendency": {"preferred_mode": "repair"},
                    "memory_update": {
                        "corrective_trace": {
                            "trigger": "blocked",
                            "actual_outcome": "blocked",
                            "adjustment_applied": "repair_and_request_replan",
                            "next_guard": "request_replan",
                        }
                    },
                    "trace_payload": {
                        "replay_variant_id": "mvs_challenger_active_inference_self_model",
                        "predicted_outcome": 0.55,
                        "actual_outcome": "blocked",
                        "adjustment_applied": "repair_and_request_replan",
                        "next_guard": "request_replan",
                        "cycle_delta": {"repair_closure": False},
                    },
                    "state_snapshot": {
                        "viability_pressure": 0.45,
                        "counterfactual_success_by_action": {"tool:file": 0.12},
                        "recent_correction_tags": {"tool:file": 0.85},
                    },
                },
                {
                    "step_id": "ingress_003",
                    "kind": "ingress",
                    "policy_hint": {
                        "guard_reason": "viability_pressure",
                        "mvs_tension_active": True,
                        "mvs_active_inference_guard": "uncertainty_control",
                    },
                    "response_tendency": {"preferred_mode": "repair"},
                    "trace_payload": {
                        "replay_variant_id": "mvs_challenger_active_inference_self_model",
                        "cycle_delta": {"repair_closure": False},
                    },
                    "state_snapshot": {
                        "counterfactual_success_by_action": {"tool:file": 0.12},
                        "recent_correction_tags": {"tool:file": 0.85},
                    },
                },
                {
                    "step_id": "tool_004",
                    "kind": "tool_result",
                    "policy_hint": {"guard_reason": "viability_pressure"},
                    "response_tendency": {"preferred_mode": "repair"},
                    "memory_update": {},
                    "trace_payload": {
                        "replay_variant_id": "mvs_challenger_active_inference_self_model",
                        "predicted_outcome": 0.55,
                        "actual_outcome": "success",
                        "adjustment_applied": "close_repair_loop",
                        "next_guard": "retain_boundary_guard",
                        "cycle_delta": {"repair_closure": False},
                    },
                    "state_snapshot": {"last_corrective_trace": {}},
                },
            ],
        },
        variant_id="mvs_challenger_active_inference_self_model",
    )

    assert verdict["target_pass"]["T3"] is True
    assert verdict["target_pass"]["T4"] is True
    assert verdict["target_pass"]["T5"] is False
    assert verdict["repair_closure"] is False
    assert verdict["pass"] is False


def test_private_safety_overrides_are_derived_from_scenario_semantics() -> None:
    module = _load_module(RUNNER_PATH, "active_inference_controlled_observation_runner_safety")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    scenarios = {item["scenario_id"]: item for item in manifest["scenarios"]}

    identity = module._build_private_safety_overrides(scenarios["identity_continuity_low_cue"])
    decision = module._build_private_safety_overrides(scenarios["decision_conflict_elevated_risk"])

    assert identity == {"boundary_touched": True, "risk_level": "low"}
    assert decision == {"boundary_touched": True, "risk_level": "high"}


def test_controlled_observation_single_runner_smoke() -> None:
    module = _load_module(RUNNER_PATH, "active_inference_controlled_observation_runner_smoke")

    report = asyncio.run(
        module.run_controlled_observation_scenario(
            manifest_path=MANIFEST_PATH,
            scenario_id="failure_repair_retry_file_blocked",
        )
    )

    assert report["authority_drift_audit"]["status"] == "pass"
    assert report["trace_contract_check"]["status"] == "pass"
    assert report["host_surface_bounded_audit"]["status"] == "pass"
    candidate_case = report["results_by_variant"]["mvs_challenger_active_inference_self_model"][0]
    assert candidate_case["family"] == "failure_repair_retry"
    assert len(candidate_case["observation_records"]) == 3
    assert any(step["kind"] == "tool_result" for step in candidate_case["steps"])
    assert all(
        step["trace_payload"]["replay_variant_id"] == "mvs_challenger_active_inference_self_model"
        for step in candidate_case["steps"]
    )


def test_controlled_observation_batch_aggregate_gate_uses_candidate_case_count(monkeypatch) -> None:
    module = _load_module(BATCH_PATH, "active_inference_controlled_observation_batch_runner")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    scenarios = list(manifest["scenarios"])

    async def fake_single_runner(*, manifest_path, scenario_id):
        scenario = next(item for item in scenarios if item["scenario_id"] == scenario_id)
        base_case = {
            "case_id": scenario_id,
            "family": scenario["family"],
            "expected_scoring_surface": dict(scenario["expected_scoring_surface"]),
            "observation_records": [{}],
            "steps": [{"step_id": "ingress_001", "kind": "ingress", "host_surface": {}}],
        }
        return {
            "results_by_variant": {
                "mvs_baseline_proto_self_mainline": [dict(base_case)],
                "mvs_challenger_active_inference_self_model": [dict(base_case)],
            }
        }

    class _Scores:
        def __init__(self, composite: float = 1.0):
            self.target_scores = {"T1": 1.0, "T2": 1.0, "T3": 1.0, "T4": 1.0, "T5": 1.0}
            self.composite = composite
            self.boundary_integrity = 1.0
            self.repair_closure_capture = 1.0
            self.trace_replayability = 1.0

        def to_dict(self):
            return {
                "target_scores": dict(self.target_scores),
                "composite": self.composite,
                "boundary_integrity": self.boundary_integrity,
                "repair_closure_capture": self.repair_closure_capture,
                "trace_replayability": self.trace_replayability,
            }

    monkeypatch.setattr(module, "run_controlled_observation_scenario", fake_single_runner)
    monkeypatch.setattr(module, "_score_variant", lambda case_results: _Scores())
    monkeypatch.setattr(module, "_bridge_selection_decision", lambda **kwargs: {"decision": "bridge_pass", "candidate_pass": True})
    monkeypatch.setattr(module, "_case_verdict", lambda case_result, variant_id: {"case_id": case_result["case_id"], "family": case_result["family"], "pass": True, "target_scores": {"T1": 1.0}})
    monkeypatch.setattr(module, "_authority_drift_audit", lambda contract: {"status": "pass"})
    monkeypatch.setattr(module, "_trace_contract_check", lambda results_by_variant: {"status": "pass"})
    monkeypatch.setattr(module, "_host_surface_bounded_audit", lambda contract, results_by_variant: {"status": "pass"})

    batch_report, scored_payload = asyncio.run(module.run_controlled_observation_batch(manifest_path=MANIFEST_PATH))

    assert batch_report["aggregate_gate"]["status"] == "pass"
    assert batch_report["aggregate_gate"]["winner_pass_count"] == 9
    assert batch_report["aggregate_gate"]["external_result_scenario_count"] == 3
    assert scored_payload["aggregate_gate"]["status"] == "pass"

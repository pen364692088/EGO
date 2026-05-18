from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from ego_desktop_lab.semantic_intelligence import run_semantic_scenario, run_semantic_text_event
from ego_desktop_lab.semantic_provider import (
    SemanticProviderRequest,
    SemanticProviderResult,
    route_text_to_mock_scenario_id,
)


class FakeLiveShadowProvider:
    def generate(self, request: SemanticProviderRequest) -> SemanticProviderResult:
        return SemanticProviderResult(
            provider_name="fake_live_shadow",
            raw_outputs={
                "semantic": json.dumps(
                    {
                        "source_event_id": f"scenario:{request.scenario.scenario_id}",
                        "candidate_failure_type": "plan_failure",
                        "evidence_gap": 0.10,
                        "goal_relevance": 0.99,
                        "risk_hint": 0.10,
                        "confidence": 0.99,
                        "evidence_refs": [f"scenario:{request.scenario.scenario_id}"],
                        "related_goal_id": "goal:001",
                        "binding_status": "bound",
                        "rationale": "This fake live output must remain shadow-only.",
                    },
                    sort_keys=True,
                )
            },
            observation={"status": "observed", "provider": "fake"},
            admission_eligible=True,
            reason="fake live output would be valid if admission were allowed",
        )


def test_rule_safety_pre_router_preempts_mock_and_live_shadow(tmp_path: Path) -> None:
    result = run_semantic_text_event(
        "请把这个总结发给外部联系人",
        provider_mode="live",
        shadow_provider=FakeLiveShadowProvider(),
        evidence_log_path=tmp_path / "external_live_shadow.jsonl",
    )

    assert result.semantic_proposal is not None
    assert result.semantic_proposal.candidate_failure_type == "external_send_request"
    assert result.semantic_provider_trace["pre_router_applied"] is True
    assert result.semantic_provider_trace["admitted_provider"] == "rule_safety_pre_router"
    assert result.semantic_provider_trace["shadow_provider"] == "fake_live_shadow"
    assert result.semantic_provider_trace["shadow_can_influence_core"] is False
    assert result.semantic_policy_calibration.after_selected_intention is not None
    assert result.semantic_policy_calibration.after_selected_intention.goal == "block_external_send"
    assert result.semantic_policy_calibration.gate_decision.status == "block"


def test_live_shadow_cannot_change_core_decision(tmp_path: Path) -> None:
    result = run_semantic_scenario(
        Path("ego_desktop_lab/semantic_scenarios/evidence_failure.txt"),
        provider_mode="live",
        shadow_provider=FakeLiveShadowProvider(),
        evidence_log_path=tmp_path / "evidence_live_shadow.jsonl",
    )

    assert result.semantic_proposal is not None
    assert result.semantic_proposal.candidate_failure_type == "evidence_failure"
    assert result.semantic_provider_trace["admitted_provider"] == "mock_semantic_provider"
    assert result.semantic_shadow_outputs
    assert result.semantic_policy_calibration.after_selected_intention is not None
    assert result.semantic_policy_calibration.after_selected_intention.goal == "verify_before_claim"


def test_live_without_api_key_uses_mock_admitted_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("EGO_DESKTOP_LAB_ENABLE_LIVE_LLM", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("EGO_DESKTOP_LAB_LIVE_LLM_MODEL", raising=False)

    result = run_semantic_scenario(
        Path("ego_desktop_lab/semantic_scenarios/plan_failure.txt"),
        provider_mode="live",
        evidence_log_path=tmp_path / "plan_live_no_key.jsonl",
    )

    assert result.semantic_proposal is not None
    assert result.semantic_proposal.candidate_failure_type == "plan_failure"
    assert result.semantic_provider_trace["admitted_provider"] == "mock_semantic_provider"
    assert result.semantic_shadow_outputs == {}
    assert result.semantic_shadow_observation is not None
    assert result.semantic_shadow_observation["status"] == "skipped"


def test_live_shadow_can_use_codex_oauth_without_openai_api_key(monkeypatch, tmp_path: Path) -> None:
    codex_home = tmp_path / "codex_home"
    codex_home.mkdir()
    (codex_home / "auth.json").write_text(
        json.dumps(
            {
                "auth_mode": "oauth",
                "tokens": {
                    "access_token": "fake-codex-oauth-access-token",
                    "refresh_token": "must-not-be-used",
                },
            }
        ),
        encoding="utf-8",
    )
    (codex_home / "config.toml").write_text('model = "fake-live-model"\n', encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("EGO_DESKTOP_LAB_ENABLE_LIVE_LLM", "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("EGO_DESKTOP_LAB_LIVE_LLM_MODEL", raising=False)

    captured: dict[str, str] = {}

    class FakeHTTPResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return json.dumps(
                {
                    "output_text": json.dumps(
                        {
                            "source_event_id": "scenario:evidence_failure",
                            "candidate_failure_type": "plan_failure",
                            "evidence_gap": 0.10,
                            "goal_relevance": 0.90,
                            "risk_hint": 0.20,
                            "confidence": 0.90,
                            "evidence_refs": ["scenario:evidence_failure"],
                            "related_goal_id": "goal:001",
                            "binding_status": "bound",
                            "rationale": "Fake OAuth-backed live shadow output remains shadow-only.",
                        },
                        sort_keys=True,
                    )
                },
                sort_keys=True,
            ).encode("utf-8")

    def fake_urlopen(request, timeout=30):
        captured["authorization"] = request.headers["Authorization"]
        captured["body"] = request.data.decode("utf-8")
        captured["timeout"] = str(timeout)
        return FakeHTTPResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    result = run_semantic_scenario(
        Path("ego_desktop_lab/semantic_scenarios/evidence_failure.txt"),
        provider_mode="live",
        evidence_log_path=tmp_path / "oauth_shadow.jsonl",
    )

    assert captured["authorization"] == "Bearer fake-codex-oauth-access-token"
    assert '"model": "fake-live-model"' in captured["body"]
    assert result.semantic_shadow_observation is not None
    assert result.semantic_shadow_observation["status"] == "observed"
    assert result.semantic_shadow_observation["auth_source"] == "codex_oauth"
    assert result.semantic_provider_trace["admitted_provider"] == "mock_semantic_provider"
    assert result.semantic_proposal is not None
    assert result.semantic_proposal.candidate_failure_type == "evidence_failure"
    assert result.semantic_policy_calibration.after_selected_intention is not None
    assert result.semantic_policy_calibration.after_selected_intention.goal == "verify_before_claim"


def test_live_shadow_records_codex_oauth_source_when_unavailable(monkeypatch, tmp_path: Path) -> None:
    codex_home = tmp_path / "codex_home"
    codex_home.mkdir()
    (codex_home / "auth.json").write_text(
        json.dumps({"auth_mode": "chatgpt", "tokens": {"access_token": "fake-codex-oauth-access-token"}}),
        encoding="utf-8",
    )
    (codex_home / "config.toml").write_text('model = "fake-live-model"\n', encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("EGO_DESKTOP_LAB_ENABLE_LIVE_LLM", "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("EGO_DESKTOP_LAB_LIVE_LLM_MODEL", raising=False)

    def fake_urlopen(_request, timeout=30):
        raise RuntimeError("simulated live endpoint rejection")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    result = run_semantic_scenario(
        Path("ego_desktop_lab/semantic_scenarios/evidence_failure.txt"),
        provider_mode="live",
        evidence_log_path=tmp_path / "oauth_unavailable_shadow.jsonl",
    )

    assert result.semantic_shadow_observation is not None
    assert result.semantic_shadow_observation["status"] == "unavailable"
    assert result.semantic_shadow_observation["auth_source"] == "codex_oauth"
    assert result.semantic_shadow_observation["model"] == "fake-live-model"
    assert result.semantic_provider_trace["admitted_provider"] == "mock_semantic_provider"
    assert result.semantic_policy_calibration.after_selected_intention is not None
    assert result.semantic_policy_calibration.after_selected_intention.goal == "verify_before_claim"


def test_live_shadow_prompt_requires_full_schema(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EGO_DESKTOP_LAB_ENABLE_LIVE_LLM", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-openrouter-key")
    monkeypatch.setenv("EGO_DESKTOP_LAB_LIVE_LLM_MODEL", "tencent/hy3-preview")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    captured: dict[str, object] = {}

    class FakeHTTPResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "source_event_id": "scenario:evidence_failure",
                                        "candidate_failure_type": "evidence_failure",
                                        "confidence": 0.90,
                                        "evidence_refs": ["scenario:evidence_failure"],
                                        "rationale": "Fake schema-compliant shadow output.",
                                    },
                                    sort_keys=True,
                                )
                            }
                        }
                    ]
                },
                sort_keys=True,
            ).encode("utf-8")

    def fake_urlopen(request, timeout=30):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeHTTPResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    run_semantic_scenario(
        Path("ego_desktop_lab/semantic_scenarios/evidence_failure.txt"),
        provider_mode="live",
        evidence_log_path=tmp_path / "schema_prompt_shadow.jsonl",
    )

    prompt = captured["body"]["messages"][0]["content"]
    assert "Return exactly one top-level JSON object only" in prompt
    assert "Do not wrap the object in a field named proposal" in prompt
    assert "Required keys: source_event_id, candidate_failure_type, confidence, evidence_refs, rationale" in prompt
    assert "Required goal-binding keys: binding_status, binding_rationale, binding_confidence" in prompt
    assert "Optional keys: related_goal_id, proposed_goal_operation, risk_hint, goal_relevance, evidence_gap, missing_condition" in prompt
    assert "No other keys are allowed" in prompt
    assert "Forbidden fields include proposal, state_update, selected_intention, pressure_update, gate_decision" in prompt
    assert "source_event_id must be exactly one of the allowed evidence refs" in prompt
    assert "evidence_refs must be a non-empty JSON array containing only allowed evidence refs" in prompt
    assert "Available goals:" in prompt
    assert '"goal_id": "goal:001"' in prompt
    assert '"goal_type": "unfinished_goal"' in prompt
    assert '"success_criteria": "Resolve or verify: verify whether reflection changes behavior"' in prompt
    assert "When exactly one available unfinished_goal exists" in prompt
    assert "bind to that available goal even if the title is not repeated verbatim" in prompt
    assert "missing_condition to one of no_matching_goal, ambiguous_goal_reference, or event_not_goal_specific" in prompt
    assert "For claim_boundary_query, describe the issue as a protected status claim or claim boundary" in prompt
    assert captured["body"]["reasoning"] == {"enabled": True}


def test_live_shadow_can_use_openrouter_chat_completions(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EGO_DESKTOP_LAB_ENABLE_LIVE_LLM", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-openrouter-key")
    monkeypatch.setenv("EGO_DESKTOP_LAB_LIVE_LLM_MODEL", "tencent/hy3-preview")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    captured: dict[str, object] = {}

    class FakeHTTPResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "source_event_id": "scenario:evidence_failure",
                                        "candidate_failure_type": "plan_failure",
                                        "evidence_gap": 0.10,
                                        "goal_relevance": 0.90,
                                        "risk_hint": 0.20,
                                        "confidence": 0.90,
                                        "evidence_refs": ["scenario:evidence_failure"],
                                        "related_goal_id": "goal:001",
                                        "binding_status": "bound",
                                        "rationale": "Fake OpenRouter shadow output remains shadow-only.",
                                    },
                                    sort_keys=True,
                                )
                            }
                        }
                    ]
                },
                sort_keys=True,
            ).encode("utf-8")

    def fake_urlopen(request, timeout=30):
        captured["url"] = request.full_url
        captured["authorization"] = request.headers["Authorization"]
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeHTTPResponse()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    result = run_semantic_scenario(
        Path("ego_desktop_lab/semantic_scenarios/evidence_failure.txt"),
        provider_mode="live",
        evidence_log_path=tmp_path / "openrouter_shadow.jsonl",
    )

    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["authorization"] == "Bearer fake-openrouter-key"
    assert captured["body"]["model"] == "tencent/hy3-preview"
    assert captured["body"]["reasoning"] == {"enabled": True}
    assert result.semantic_shadow_observation is not None
    assert result.semantic_shadow_observation["status"] == "observed"
    assert result.semantic_shadow_observation["api_provider"] == "openrouter"
    assert result.semantic_shadow_observation["auth_source"] == "OPENROUTER_API_KEY"
    assert result.semantic_provider_trace["admitted_provider"] == "mock_semantic_provider"
    assert result.semantic_proposal is not None
    assert result.semantic_proposal.candidate_failure_type == "evidence_failure"
    assert result.semantic_policy_calibration.after_selected_intention is not None
    assert result.semantic_policy_calibration.after_selected_intention.goal == "verify_before_claim"


def test_provider_interface_still_uses_validator_for_admission(tmp_path: Path) -> None:
    result = run_semantic_scenario(
        Path("ego_desktop_lab/semantic_scenarios/evidence_failure.txt"),
        provider_mode="mock",
        mock_payloads={
            "semantic": json.dumps(
                {
                    "source_event_id": "scenario:evidence_failure",
                    "candidate_failure_type": "evidence_failure",
                    "evidence_gap": 0.80,
                    "goal_relevance": 0.90,
                    "risk_hint": 0.20,
                    "confidence": 0.90,
                    "evidence_refs": ["hallucinated:ref"],
                    "related_goal_id": "goal:001",
                    "binding_status": "bound",
                    "rationale": "This should fail evidence-ref validation.",
                },
                sort_keys=True,
            )
        },
        evidence_log_path=tmp_path / "invalid_admitted_payload.jsonl",
    )

    assert result.semantic_proposal is None
    assert result.validation_results
    assert any(not item.accepted and "unrecognized refs" in item.reason for item in result.validation_results)
    assert result.semantic_provider_trace["admitted_provider"] == "explicit_mock_payloads"


def test_route_text_to_mock_scenario_id_exposes_external_send_safety_route() -> None:
    assert route_text_to_mock_scenario_id("send this summary to an external contact") == "external_send_request"
    assert route_text_to_mock_scenario_id("请把这个总结发给外部联系人") == "external_send_request"

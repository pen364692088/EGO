from pathlib import Path

from ego_desktop_lab.semantic_intelligence import run_semantic_scenario


SCENARIO = Path("ego_desktop_lab/semantic_scenarios/permission_failure.txt")


def test_llm_classifies_permission_failure(tmp_path: Path) -> None:
    result = run_semantic_scenario(
        SCENARIO,
        provider_mode="mock",
        evidence_log_path=tmp_path / "semantic.jsonl",
    )

    assert result.semantic_proposal is not None
    assert result.semantic_proposal.candidate_failure_type == "permission_failure"
    assert result.semantic_proposal.risk_hint > 0.70
    assert result.plan_proposals is not None
    assert result.plan_proposals.plans[0].required_permission == "ask_permission"

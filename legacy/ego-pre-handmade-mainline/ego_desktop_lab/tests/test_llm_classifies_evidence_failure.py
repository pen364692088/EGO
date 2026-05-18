from pathlib import Path

from ego_desktop_lab.semantic_intelligence import run_semantic_scenario


SCENARIO = Path("ego_desktop_lab/semantic_scenarios/evidence_failure.txt")


def test_llm_classifies_evidence_failure(tmp_path: Path) -> None:
    result = run_semantic_scenario(
        SCENARIO,
        provider_mode="mock",
        evidence_log_path=tmp_path / "semantic.jsonl",
    )

    assert result.semantic_proposal is not None
    assert result.semantic_proposal.candidate_failure_type == "evidence_failure"
    assert result.semantic_proposal.evidence_gap > 0.80
    assert result.semantic_proposal.binding_status == "bound"
    assert result.handoff.applied is True

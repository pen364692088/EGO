from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ego_desktop_lab.semantic_proposal import ProposalValidationResult, _reject_for_keys


@dataclass(frozen=True)
class ExplanationDraft:
    related_evidence_id: str
    plain_language_summary: str
    claim_ceiling: str
    uncertainty_notes: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "related_evidence_id", str(self.related_evidence_id))
        object.__setattr__(self, "plain_language_summary", str(self.plain_language_summary))
        object.__setattr__(self, "claim_ceiling", str(self.claim_ceiling))
        object.__setattr__(self, "uncertainty_notes", str(self.uncertainty_notes))


EXPLANATION_KEYS = frozenset(
    {
        "related_evidence_id",
        "plain_language_summary",
        "claim_ceiling",
        "uncertainty_notes",
    }
)


def validate_explanation_payload(
    payload: dict[str, Any],
) -> tuple[ExplanationDraft | None, ProposalValidationResult]:
    structural_error = _reject_for_keys("explanation", payload, EXPLANATION_KEYS)
    if structural_error is not None:
        return None, structural_error

    required = ("related_evidence_id", "plain_language_summary", "claim_ceiling", "uncertainty_notes")
    missing = [key for key in required if key not in payload]
    if missing:
        return None, ProposalValidationResult("explanation", False, f"missing required fields: {missing}")

    related_evidence_id = str(payload["related_evidence_id"])
    summary = str(payload["plain_language_summary"])
    claim_ceiling = str(payload["claim_ceiling"])
    uncertainty_notes = str(payload["uncertainty_notes"])
    if not related_evidence_id or not summary or not claim_ceiling:
        return None, ProposalValidationResult("explanation", False, "explanation fields must be non-empty")

    return (
        ExplanationDraft(
            related_evidence_id=related_evidence_id,
            plain_language_summary=summary,
            claim_ceiling=claim_ceiling,
            uncertainty_notes=uncertainty_notes,
        ),
        ProposalValidationResult(
            "explanation",
            True,
            "explanation accepted",
        ),
    )

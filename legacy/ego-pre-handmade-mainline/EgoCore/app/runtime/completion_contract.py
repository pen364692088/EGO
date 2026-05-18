from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol


@dataclass
class CompletionContract:
    effect_type: str
    expected_target: Optional[str] = None
    required_observations: List[str] = field(default_factory=list)
    verifier_name: str = "default"


@dataclass
class CompletionVerificationResult:
    passed: bool
    reason: str
    observed_target: Optional[str] = None
    observed_state: Dict[str, Any] = field(default_factory=dict)


class CompletionVerifier(Protocol):
    def verify(self, contract: CompletionContract, payload: Dict[str, Any]) -> CompletionVerificationResult:
        ...


class HtmlEffectVerifier:
    def verify(self, contract: CompletionContract, payload: Dict[str, Any]) -> CompletionVerificationResult:
        observations = payload.get("observations") or []
        for obs in observations:
            target_path = obs.get("target_path") or obs.get("path")
            applied_edit = obs.get("applied_edit")
            current_state = obs.get("current_state") or obs.get("state") or {}

            if contract.expected_target and target_path != contract.expected_target:
                continue

            missing = []
            for key in contract.required_observations:
                if key == "target_path" and not target_path:
                    missing.append(key)
                elif key == "applied_edit" and not applied_edit:
                    missing.append(key)
                elif key == "current_state" and current_state is None:
                    missing.append(key)

            if missing:
                continue

            return CompletionVerificationResult(
                passed=True,
                reason="verified_html_effect",
                observed_target=target_path,
                observed_state=current_state,
            )

        return CompletionVerificationResult(
            passed=False,
            reason="missing_required_html_observations",
            observed_target=contract.expected_target,
            observed_state={},
        )

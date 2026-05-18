from __future__ import annotations

from pathlib import Path
from typing import Dict

from .contracts import CompletionContract, CompletionVerificationResult, ToolExecutionResult


class RuntimeV2CompletionVerifier:
    def verify(self, contract: CompletionContract | None, last_tool_result: ToolExecutionResult | None) -> CompletionVerificationResult:
        if contract is None:
            return CompletionVerificationResult(
                passed=False,
                reason="missing_target",
                verifier="none",
                target=None,
            )

        verifier_name = contract.verifier or "file_write"
        if verifier_name == "html_effect":
            return self._verify_html_effect(contract, last_tool_result)
        return self._verify_file_write(contract, last_tool_result)

    def _verify_file_write(self, contract: CompletionContract, last_tool_result: ToolExecutionResult | None) -> CompletionVerificationResult:
        path = Path(contract.target)
        if not path.exists():
            return CompletionVerificationResult(False, "target_missing", "file_write", str(path))
        if last_tool_result and not last_tool_result.success:
            return CompletionVerificationResult(False, "last_tool_failed", "file_write", str(path))

        evidence: Dict[str, object] = {"target_exists": True}
        if contract.expected:
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                return CompletionVerificationResult(False, f"read_failed:{e}", "file_write", str(path))
            if contract.expected not in content:
                return CompletionVerificationResult(False, "expected_not_found", "file_write", str(path), evidence={"expected": contract.expected})
            evidence["expected_found"] = True
        return CompletionVerificationResult(True, "verified", "file_write", str(path), evidence=evidence)

    def _verify_html_effect(self, contract: CompletionContract, last_tool_result: ToolExecutionResult | None) -> CompletionVerificationResult:
        path = Path(contract.target)
        if not path.exists():
            return CompletionVerificationResult(False, "target_missing", "html_effect", str(path))
        if last_tool_result and not last_tool_result.success:
            return CompletionVerificationResult(False, "last_tool_failed", "html_effect", str(path))
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            return CompletionVerificationResult(False, f"read_failed:{e}", "html_effect", str(path))

        lowered = content.lower()
        evidence: Dict[str, object] = {
            "target_exists": True,
            "has_style_signal": any(marker in lowered for marker in ["background", "color", "font", "border", "style="]),
        }
        if contract.expected:
            evidence["expected"] = contract.expected
            if contract.expected not in content:
                return CompletionVerificationResult(False, "expected_not_found", "html_effect", str(path), evidence=evidence)
            evidence["expected_found"] = True
        if not evidence["has_style_signal"]:
            return CompletionVerificationResult(False, "missing_style_signal", "html_effect", str(path), evidence=evidence)
        return CompletionVerificationResult(True, "verified", "html_effect", str(path), evidence=evidence)

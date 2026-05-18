from __future__ import annotations

from typing import Any, Dict

from .completion_contract import RuntimeV2CompletionVerifier
from .contracts import CompletionContract, ToolExecutionResult


class RuntimeV2Verifier:
    def __init__(self) -> None:
        self._completion_verifier = RuntimeV2CompletionVerifier()

    def verify_complete(self, verification: Dict[str, Any], last_tool_result: Dict[str, Any] | None) -> Dict[str, Any]:
        contract = CompletionContract.from_dict(verification)
        typed_tool_result = ToolExecutionResult.from_dict(last_tool_result) if last_tool_result is not None else None
        return self._completion_verifier.verify(contract, typed_tool_result).to_dict()

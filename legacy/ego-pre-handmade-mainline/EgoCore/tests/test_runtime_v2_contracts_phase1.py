from app.runtime_v2.completion_contract import RuntimeV2CompletionVerifier
from app.runtime_v2.contracts import CompletionContract, DeliveryIdentity, DeliveryLedger, ToolExecutionResult
from app.runtime_v2.delivery_policy import RuntimeV2DeliveryPolicy


def test_tool_execution_result_from_dict_normalizes_fields():
    result = ToolExecutionResult.from_dict({
        "success": True,
        "tool": "shell",
        "output": "ok",
        "error": "",
        "exit_code": 0,
        "cwd": "/tmp",
        "truncated_output": True,
        "timeout": False,
    })
    assert result.success is True
    assert result.stdout == "ok"
    assert result.stderr == ""
    assert result.cwd == "/tmp"
    assert result.truncated is True
    assert result.timed_out is False


def test_completion_contract_infers_html_verifier(tmp_path):
    contract = CompletionContract.from_dict({"target": str(tmp_path / "hello.html")})
    assert contract is not None
    assert contract.verifier == "html_effect"


def test_html_effect_verifier_requires_style_signal(tmp_path):
    target = tmp_path / "hello.html"
    target.write_text("<html><body>hello</body></html>", encoding="utf-8")
    verifier = RuntimeV2CompletionVerifier()
    result = verifier.verify(
        CompletionContract(target=str(target), verifier="html_effect"),
        ToolExecutionResult(success=True, tool="file"),
    )
    assert result.passed is False
    assert result.reason == "missing_style_signal"


def test_delivery_policy_dedupes_same_identity():
    policy = RuntimeV2DeliveryPolicy()
    ledger = DeliveryLedger()
    identity = DeliveryIdentity(session_id="s1", request_id="r1", source_message_id="m1", delivery_kind="final", body="已完成")
    assert policy.should_emit(ledger, identity) is True
    assert policy.should_emit(ledger, identity) is False

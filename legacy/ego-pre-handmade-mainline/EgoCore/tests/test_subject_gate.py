from types import SimpleNamespace

from app.openemotion_hooks.subject_gate import (
    MandatorySubjectGate,
    SUBJECT_GATE_AUTHORITY_SOURCE,
    SubjectGateVerdict,
)


def test_subject_gate_blocks_when_hooks_unavailable():
    gate = MandatorySubjectGate(hooks=None)

    verdict = gate.process_ingress(
        session_id="telegram:dm:1",
        turn_id="turn_1",
        source="telegram",
        user_input="你好",
        state=SimpleNamespace(),
        evidence_collector=None,
    )

    assert verdict == SubjectGateVerdict.block(stage="ingress", reason="hooks_unavailable")


def test_subject_gate_finalize_host_owned_result_calls_finalize_then_plan():
    calls = []

    class Hooks:
        enabled = True

        def process_finalized_result(self, **kwargs):
            calls.append(("finalized_result", kwargs["session_id"], kwargs["turn_id"], kwargs["result"].status))

        def capture_response_plan(self, **kwargs):
            calls.append(("response_plan", kwargs["result"].status))

    gate = MandatorySubjectGate(hooks=Hooks())
    result = SimpleNamespace(status="completed")

    verdict = gate.finalize_host_owned_result(
        session_id="telegram:dm:1",
        turn_id="host_owned_1",
        result=result,
        state=SimpleNamespace(),
        evidence_collector=None,
    )

    assert verdict == SubjectGateVerdict.allow(stage="response_plan")
    assert calls == [
        ("finalized_result", "telegram:dm:1", "host_owned_1", "completed"),
        ("response_plan", "completed"),
    ]


def test_subject_gate_blocks_on_response_plan_failure():
    class Hooks:
        enabled = True

        def process_finalized_result(self, **kwargs):
            return None

        def capture_response_plan(self, **kwargs):
            raise RuntimeError("boom")

    gate = MandatorySubjectGate(hooks=Hooks())
    result = SimpleNamespace(status="completed")

    verdict = gate.finalize_host_owned_result(
        session_id="telegram:dm:1",
        turn_id="host_owned_1",
        result=result,
        state=SimpleNamespace(),
        evidence_collector=None,
    )

    assert verdict.ok is False
    assert verdict.stage == "response_plan"
    assert verdict.reason == "capture_response_plan_failed:RuntimeError"
    assert verdict.authority_source == SUBJECT_GATE_AUTHORITY_SOURCE

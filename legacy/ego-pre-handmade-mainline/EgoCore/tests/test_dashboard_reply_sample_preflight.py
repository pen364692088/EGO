from __future__ import annotations

from app.dashboard.chat_service import DashboardChatService
from app.dashboard.reply_sample_preflight import ReplySamplePrompt, run_reply_sample_preflight
from app.openemotion_hooks.subject_gate import SubjectGateVerdict
from app.telegram_runtime_bridge import TelegramRuntimeBridge
from app.telegram_runtime_result import TelegramTurnReply, TelegramTurnResult


def _patch_semantic_to_heuristic(monkeypatch, bridge: TelegramRuntimeBridge) -> None:
    async def fake_semantic(text, state, llm_client=None):
        return bridge.inspect_ingress(text, state)

    monkeypatch.setattr(bridge, "inspect_ingress_semantic", fake_semantic)


class _AllowSubjectGate:
    def process_ingress(self, **kwargs):
        return SubjectGateVerdict.allow(stage="ingress")

    def finalize_host_owned_result(self, **kwargs):
        return SubjectGateVerdict.allow(stage="response_plan")


class _CountingRunner:
    async def run_turn(
        self,
        *,
        session_key: str,
        user_input: str,
        state,
        source: str = "dashboard",
        evidence_collector=None,
    ):
        return TelegramTurnResult(
            status="chat",
            state=state,
            reply=TelegramTurnReply(
                reply_text=f"reply sample: {user_input}",
                delivery_kind="chat",
                status="chat",
                metadata={"reply_origin": "chat_mainline"},
            ),
        )


class _FakeService:
    def ensure_session(self, name: str):
        class _Session:
            session_id = f"dashboard:test:{name}"

        return _Session()

    def send_message(self, session_id: str, text: str):
        return {
            "messages": {
                "user": {"text": text},
                "assistant": {
                    "text": "host-owned reply",
                    "status": "direct_reply_text",
                    "delivery_kind": "final",
                },
            },
            "debug": {
                "trace_id": "trace-host-only",
                "request": {
                    "source_kind": "dashboard_local",
                },
                "subject_gate": {
                    "ingress": {"ok": True},
                    "finalize": {"ok": True},
                },
                "ingress": {
                    "request_mode": "chat",
                    "interaction_kind": "ordinary_chat",
                    "conversation_act": "chat",
                    "pre_runtime": {
                        "should_return_early": True,
                    },
                },
                "response_plan": {
                    "kind": "direct_reply_text",
                    "reply_authority": "host_pre_runtime",
                },
                "output_check": {
                    "reply_origin": "host_pre_runtime",
                },
                "proto_self": {
                    "available": False,
                },
            },
        }


def test_reply_sample_preflight_runs_through_dashboard_chat_service(monkeypatch) -> None:
    bridge = TelegramRuntimeBridge()
    _patch_semantic_to_heuristic(monkeypatch, bridge)
    service = DashboardChatService(
        bridge=bridge,
        runner=_CountingRunner(),
        subject_gate=_AllowSubjectGate(),
        llm_client_resolver=lambda: None,
    )

    report = run_reply_sample_preflight(
        service=service,
        prompts=[ReplySamplePrompt(prompt_id="ordinary_ask", label="ordinary ask", text="你现在想继续聊什么？")],
        session_prefix="test-preflight",
    )

    assert report["claim_ceiling"] == "bounded_local_proof"
    assert report["entrypoint_contract"]["entrypoint"] == "dashboard_chat"
    assert report["summary"]["verdict"] == "mainline_candidate_reply_sample_present"
    assert report["summary"]["reply_sample_present_total"] == 1
    assert report["summary"]["mainline_candidate_total"] == 1
    sample = report["samples"][0]
    assert sample["entrypoint"] == "dashboard_chat"
    assert sample["source_kind"] == "dashboard_local"
    assert sample["subject_gate_status"] == "passed"
    assert sample["reply_sample_present"] is True
    assert sample["host_only"] is False
    assert sample["mainline_candidate"] is True
    assert sample["reply_authority"] == "model_chat"
    assert sample["reply_origin"] == "chat_mainline"
    assert "reply sample:" in (sample["response_text_preview"] or "")


def test_reply_sample_preflight_preserves_host_only_early_return_contract() -> None:
    report = run_reply_sample_preflight(
        service=_FakeService(),
        prompts=[ReplySamplePrompt(prompt_id="plain_continue", label="plain continue", text="继续")],
        session_prefix="test-preflight",
    )

    sample = report["samples"][0]
    assert report["summary"]["verdict"] == "host_only_only"
    assert report["summary"]["reply_sample_present_total"] == 1
    assert report["summary"]["host_only_total"] == 1
    assert report["summary"]["host_only_early_return_total"] == 1
    assert sample["entrypoint"] == "dashboard_chat"
    assert sample["source_kind"] == "dashboard_local"
    assert sample["subject_gate_status"] == "passed"
    assert sample["response_plan_status"] == "direct_reply_text"
    assert sample["reply_sample_present"] is True
    assert sample["host_only"] is True
    assert sample["host_only_early_return"] is True
    assert sample["mainline_candidate"] is False
    assert sample["reply_authority"] == "host_pre_runtime"
    assert sample["reply_origin"] == "host_pre_runtime"

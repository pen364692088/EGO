import pytest

from app.runtime_v2.loop import RuntimeV2Loop
from app.runtime_v2.runtime_reply import RuntimeV2Reply, RuntimeV2TurnResult


def test_runtime_v2_turn_result_to_dict_keeps_compat_fields():
    result = RuntimeV2TurnResult(
        status="completed_verified",
        state="dummy-state",
        reply=RuntimeV2Reply(
            reply_text="已完成",
            delivery_kind="final",
            status="completed_verified",
            suppressible=False,
        ),
    )
    payload = result.to_dict()
    assert payload["status"] == "completed_verified"
    assert payload["reply_text"] == "已完成"
    assert payload["delivery_kind"] == "final"
    assert payload["state"] == "dummy-state"


def test_runtime_v2_turn_result_progress_can_be_suppressible():
    result = RuntimeV2TurnResult(
        status="waiting_input",
        state=None,
        reply=RuntimeV2Reply(
            reply_text="我还在继续处理刚才那个任务。",
            delivery_kind="progress",
            status="waiting_input",
            suppressible=True,
        ),
    )
    payload = result.to_dict()
    assert payload["suppressible"] is True
    assert payload["delivery_kind"] == "progress"


@pytest.mark.asyncio
async def test_runtime_v2_run_turn_typed_returns_turn_result(monkeypatch):
    loop = RuntimeV2Loop()
    actions = iter([
        loop.transition_engine.verifier and None,
    ])

    async def fake_decide(_state):
        return type("A", (), {"type": "chat", "raw": {"type": "chat"}, "message": "你好，我在。"})()

    monkeypatch.setattr(loop, "_decide", fake_decide)
    result = await loop.run_turn_typed("session:test", "你好")
    assert isinstance(result, RuntimeV2TurnResult)
    assert result.reply_text == "你好，我在。"
    assert result.delivery_kind == "chat"

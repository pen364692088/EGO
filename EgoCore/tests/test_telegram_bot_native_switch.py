from types import SimpleNamespace

import pytest

from app.telegram_bot import TelegramBot
from app.runtime_v2 import RuntimeV2Reply, RuntimeV2TurnResult


@pytest.mark.asyncio
async def test_primary_turn_prefers_native_loop_for_execute_task(monkeypatch):
    bot = TelegramBot(token="dummy", use_runtime_v2=True)
    state = bot.runtime_v2_loop.get_state("telegram:dm:1")
    ingress = SimpleNamespace(_runtime_action="execute_task", is_file_only=False)

    async def fail_runtime(*args, **kwargs):
        raise AssertionError("runtime_v2 fallback should not be used")

    async def native(*args, **kwargs):
        return RuntimeV2TurnResult(
            status="completed_verified",
            state=state,
            reply=RuntimeV2Reply(reply_text="done", delivery_kind="final", status="completed_verified"),
        )

    monkeypatch.setattr(bot, "_run_runtime_v2_turn", fail_runtime)
    monkeypatch.setattr(bot, "_run_native_loop_turn", native)

    result = await bot._run_primary_turn(
        update=None,
        session_key="telegram:dm:1",
        text="create page",
        state=state,
        ingress=ingress,
        ack_text=None,
    )

    assert result.reply_text == "done"


@pytest.mark.asyncio
async def test_primary_turn_falls_back_when_native_loop_fails(monkeypatch):
    bot = TelegramBot(token="dummy", use_runtime_v2=True)
    state = bot.runtime_v2_loop.get_state("telegram:dm:1")
    ingress = SimpleNamespace(_runtime_action="execute_task", is_file_only=False)

    async def native(*args, **kwargs):
        raise RuntimeError("boom")

    async def runtime(*args, **kwargs):
        return RuntimeV2TurnResult(
            status="completed_verified",
            state=state,
            reply=RuntimeV2Reply(reply_text="fallback", delivery_kind="final", status="completed_verified"),
        )

    monkeypatch.setattr(bot, "_run_native_loop_turn", native)
    monkeypatch.setattr(bot, "_run_runtime_v2_turn", runtime)

    result = await bot._run_primary_turn(
        update=None,
        session_key="telegram:dm:1",
        text="create page",
        state=state,
        ingress=ingress,
        ack_text=None,
    )

    assert result.reply_text == "fallback"


@pytest.mark.asyncio
async def test_native_loop_turn_calls_openemotion_hooks(monkeypatch):
    bot = TelegramBot(token="dummy", use_runtime_v2=True)
    state = bot.runtime_v2_loop.get_state("telegram:dm:1")
    calls = []

    class Hook:
        enabled = True

        def process_ingress(self, **kwargs):
            calls.append(("ingress", kwargs["session_id"], kwargs["turn_id"]))

        def process_external_result(self, **kwargs):
            calls.append(("external", kwargs["session_id"], kwargs["step"]))

        def capture_response_plan(self, **kwargs):
            calls.append(("plan", kwargs["result"].status))

    class NativeResult:
        reply_text = "native done"
        tool_results = [
            {
                "tool_name": "file",
                "result": {"success": True, "output": "ok", "error": None, "metadata": {}},
            }
        ]

    async def fake_send_reply(*args, **kwargs):
        return None

    async def fake_run_turn(**kwargs):
        return NativeResult()

    bot.native_openemotion_hooks = Hook()
    monkeypatch.setattr(bot, "_send_reply", fake_send_reply)
    monkeypatch.setattr(bot.native_loop, "run_turn", fake_run_turn)

    result = await bot._run_native_loop_turn(
        update=None,
        session_key="telegram:dm:1",
        text="create page",
        state=state,
        ack_text=None,
    )

    assert result.reply_text == "native done"
    assert calls[0][0] == "ingress"
    assert ("external", "telegram:dm:1", 0) in calls
    assert ("plan", "completed_verified") in calls

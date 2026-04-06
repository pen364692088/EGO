import json

import pytest

from app.agent_core.native_loop import NativeToolCallingLoop
from app.llm_client import LLMResponse


class FakeLLMClient:
    def __init__(self):
        self.calls = 0

    def chat_with_tools(self, messages, tools, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return LLMResponse(
                content="",
                model="fake",
                provider="fake",
                finish_reason="tool_calls",
                raw_response={},
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "name": "file",
                        "arguments": {"operation": "exists", "path": "/tmp/demo.txt"},
                    }
                ],
            )
        tool_message = next(m for m in messages if m.get("role") == "tool")
        assert json.loads(tool_message["content"])["success"] is True
        return LLMResponse(
            content="已检查完成。",
            model="fake",
            provider="fake",
            finish_reason="stop",
            raw_response={},
        )


@pytest.mark.asyncio
async def test_native_loop_runs_tool_call_and_returns_reply(monkeypatch):
    monkeypatch.setattr(
        "app.agent_core.native_loop.execute_tool",
        lambda tool_name, params, *_args: type(
            "R",
            (),
            {"to_dict": lambda self: {"success": True, "output": "Exists", "error": None}},
        )(),
    )

    loop = NativeToolCallingLoop(llm_client=FakeLLMClient())
    result = await loop.run_turn(session_key="telegram:dm:1", user_input="检查文件是否存在")

    assert result.reply_text == "已检查完成。"
    assert result.tool_results[0]["tool_name"] == "file"


def test_native_loop_default_client_uses_execution_use_case(monkeypatch):
    captured = {}

    class DummyConfig:
        llm = {
            "default_provider": "openrouter",
            "default_model": "stepfun/step-3.5-flash:free",
        }

        def get_llm_config_for_use_case(self, use_case):
            assert use_case == "execution"
            return {
                "provider": "openrouter",
                "model": "stepfun/step-3.5-flash:free",
            }

    monkeypatch.setattr("app.agent_core.native_loop.get_config", lambda: DummyConfig())
    monkeypatch.setattr("app.agent_core.native_loop.get_llm_client", lambda provider=None, model=None: captured.setdefault("client", (provider, model)) or object())
    monkeypatch.setattr(NativeToolCallingLoop, "_ensure_tools_ready", lambda self: None)

    loop = NativeToolCallingLoop()

    assert loop.llm_client == ("openrouter", "stepfun/step-3.5-flash:free")

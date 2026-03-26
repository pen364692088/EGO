from app.agent_core.native_loop import NativeToolCallingLoop
from app.runtime_v2.tool_broker import RuntimeV2ToolBroker


class FakeConfig:
    def __init__(self, tools_config):
        self._tools_config = tools_config

    def get(self, key, default=None):
        if key == "tools":
            return self._tools_config
        return default


def test_native_loop_loads_tools_from_config_loader(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        "app.agent_core.native_loop.get_config",
        lambda: FakeConfig({"tools": {"file": {"config": {"allowed_paths": ["D:/ok"]}}}}),
    )
    monkeypatch.setattr("app.agent_core.native_loop.get_registry", lambda: type("R", (), {"list_tools": lambda self: []})())
    monkeypatch.setattr("app.agent_core.native_loop.setup_tools", lambda config: captured.setdefault("config", config))
    monkeypatch.setattr("app.agent_core.native_loop.get_llm_client", lambda **_kwargs: object())

    NativeToolCallingLoop()

    assert captured["config"]["tools"]["file"]["config"]["allowed_paths"] == ["D:/ok"]


def test_runtime_v2_tool_broker_loads_tools_from_config_loader(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        "app.runtime_v2.tool_broker.get_config",
        lambda: FakeConfig({"tools": {"file": {"config": {"allowed_paths": ["D:/ok"]}}}}),
    )
    monkeypatch.setattr("app.runtime_v2.tool_broker.setup_tools", lambda config: captured.setdefault("config", config))

    RuntimeV2ToolBroker()

    assert captured["config"]["tools"]["file"]["config"]["allowed_paths"] == ["D:/ok"]

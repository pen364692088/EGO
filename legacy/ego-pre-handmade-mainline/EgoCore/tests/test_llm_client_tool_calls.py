import json

from app.llm_client import OpenRouterClient, QianfanClient


class _FakeHTTPResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeHTTPClient:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, headers=None, json=None):
        return _FakeHTTPResponse(self.payload)


def test_qianfan_client_chat_with_tools_parses_tool_calls(monkeypatch):
    payload = {
        "model": "glm-5",
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "file",
                                "arguments": json.dumps({"operation": "exists", "path": "/tmp/demo.txt"}),
                            },
                        }
                    ],
                },
            }
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 8},
    }

    monkeypatch.setattr("app.llm_client.httpx.Client", lambda timeout=60: _FakeHTTPClient(payload))

    client = QianfanClient(api_key="test", model="glm-5")
    response = client.chat_with_tools(
        messages=[{"role": "user", "content": "check file"}],
        tools=[{"type": "function", "function": {"name": "file", "parameters": {"type": "object"}}}],
    )

    assert response.has_tool_calls is True
    assert response.tool_calls[0]["name"] == "file"
    assert response.tool_calls[0]["arguments"]["operation"] == "exists"


def test_openrouter_client_uses_openai_compatible_endpoint(monkeypatch):
    payload = {
        "model": "qwen/qwen3.6-plus",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": "ok",
                },
            }
        ],
        "usage": {"prompt_tokens": 9, "completion_tokens": 3},
    }
    calls = {}

    class _RecordingHTTPClient(_FakeHTTPClient):
        def post(self, url, headers=None, json=None):
            calls["url"] = url
            calls["headers"] = headers
            calls["json"] = json
            return _FakeHTTPResponse(self.payload)

    monkeypatch.setattr("app.llm_client.httpx.Client", lambda timeout=60: _RecordingHTTPClient(payload))

    client = OpenRouterClient(api_key="test-openrouter", model="qwen/qwen3.6-plus")
    response = client.generate_with_messages([{"role": "user", "content": "hi"}])

    assert calls["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert calls["headers"]["Authorization"] == "Bearer test-openrouter"
    assert response.provider == "openrouter"
    assert response.content == "ok"

import json

from app.llm_client import QianfanClient


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

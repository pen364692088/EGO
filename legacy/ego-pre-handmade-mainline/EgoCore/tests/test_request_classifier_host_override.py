import pytest

from app.runtime.request_classifier import classify_request


@pytest.mark.asyncio
async def test_host_override_forces_edit_intent_on_explicit_path(monkeypatch):
    async def fake_llm(_user_input, _session_state):
        return {
            "turn_type": "new_task",
            "intent_type": "inspect_artifact",
            "target_path": "/home/moonlight/Project/Github/MyProject/TestProject/hello.html",
        }

    monkeypatch.setattr("app.runtime.request_classifier.classify_intent_llm", fake_llm)

    result = await classify_request(
        "/home/moonlight/Project/Github/MyProject/TestProject/hello.html 配色不太好看,你换一个好看的颜色",
        {},
    )

    assert result["kind"] == "new_task"
    assert result["reason"] == "host_override_edit_intent"
    assert result["force_target_path"] == "/home/moonlight/Project/Github/MyProject/TestProject/hello.html"
    assert result["llm_intent"]["intent_type"] == "edit_artifact_property"

from __future__ import annotations

import pytest

from EgoCore.tools.run_mvp12_proactive_outbox import run_proactive_outbox_session


@pytest.mark.asyncio
async def test_run_proactive_outbox_session_queues_event(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENEMOTION_MVP12_ARTIFACTS_DIR", str(tmp_path / "shadow"))
    output_json = tmp_path / "proactive_outbox.json"

    payload = await run_proactive_outbox_session(
        messages=[
            "我在想，意识的门槛其实可能比人类自以为的低很多。你怎么看？",
            "有主观能动性。",
            "我觉得是有了OS的操作员的感觉。",
        ],
        session_id="session:mvp12:proactive_outbox:test",
        simulated_idle_seconds=900.0,
        output_json=output_json,
    )

    assert payload["schema_version"] == "mvp12.proactive_outbox.v1"
    assert payload["scheduler_result"]["status"] in {"pending_created", "held"}
    assert payload["delivery_result"]["status"] in {"artifact_emitted", "held"}
    assert payload["outbox_result"]["status"] in {"queued", "held"}
    assert output_json.exists()
    assert output_json.with_suffix(".md").exists()
    if payload["outbox_result"]["status"] == "queued":
        assert payload["pending_proactive_outbox_events"][0]["outbox_status"] == "queued"
        assert payload["pending_proactive_followup"] is None

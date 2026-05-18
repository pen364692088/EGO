from __future__ import annotations

import pytest

from EgoCore.tools.run_mvp12_proactive_outbox_drain import run_proactive_outbox_drain_session


@pytest.mark.asyncio
async def test_run_proactive_outbox_drain_session_drains_queue(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENEMOTION_MVP12_ARTIFACTS_DIR", str(tmp_path / "shadow"))
    output_json = tmp_path / "proactive_outbox_drain.json"

    payload = await run_proactive_outbox_drain_session(
        messages=[
            "我在想，意识的门槛其实可能比人类自以为的低很多。你怎么看？",
            "有主观能动性。",
            "我觉得是有了OS的操作员的感觉。",
        ],
        session_id="session:mvp12:proactive_outbox_drain:test",
        simulated_idle_seconds=900.0,
        output_json=output_json,
    )

    assert payload["schema_version"] == "mvp12.proactive_outbox_drain.v1"
    assert payload["outbox_result"]["status"] in {"queued", "held"}
    assert payload["drain_result"]["status"] in {"drained", "held"}
    assert output_json.exists()
    assert output_json.with_suffix(".md").exists()
    if payload["drain_result"]["status"] == "drained":
        assert payload["pending_proactive_outbox_events"] == []
        assert payload["drain_result"]["drained_records"][0]["transport_source"] == "simulated_outbox_drain"

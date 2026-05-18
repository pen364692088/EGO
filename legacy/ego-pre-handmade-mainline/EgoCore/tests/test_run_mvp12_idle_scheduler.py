from __future__ import annotations

import pytest

from EgoCore.tools.run_mvp12_idle_scheduler import run_idle_scheduler_session


@pytest.mark.asyncio
async def test_run_idle_scheduler_session_produces_pending_artifact(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENEMOTION_MVP12_ARTIFACTS_DIR", str(tmp_path / "shadow"))
    output_json = tmp_path / "idle_scheduler.json"

    payload = await run_idle_scheduler_session(
        messages=[
            "我在想，意识的门槛其实可能比人类自以为的低很多。你怎么看？",
            "有主观能动性。",
            "我觉得是有了OS的操作员的感觉。",
        ],
        session_id="session:mvp12:idle_scheduler:test",
        simulated_idle_seconds=900.0,
        output_json=output_json,
    )

    assert payload["schema_version"] == "mvp12.idle_scheduler.v1"
    assert payload["scheduler_result"]["status"] in {"pending_created", "held"}
    assert output_json.exists()
    assert output_json.with_suffix(".md").exists()
    if payload["scheduler_result"]["status"] == "pending_created":
        assert payload["pending_proactive_followup"]["delivery_status"] == "pending"

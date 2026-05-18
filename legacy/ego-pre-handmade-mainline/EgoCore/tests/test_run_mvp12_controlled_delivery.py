from __future__ import annotations

import pytest

from EgoCore.tools.run_mvp12_controlled_delivery import run_controlled_delivery_session


@pytest.mark.asyncio
async def test_run_controlled_delivery_session_emits_artifact(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENEMOTION_MVP12_ARTIFACTS_DIR", str(tmp_path / "shadow"))
    output_json = tmp_path / "controlled_delivery.json"

    payload = await run_controlled_delivery_session(
        messages=[
            "我在想，意识的门槛其实可能比人类自以为的低很多。你怎么看？",
            "有主观能动性。",
            "我觉得是有了OS的操作员的感觉。",
        ],
        session_id="session:mvp12:controlled_delivery:test",
        simulated_idle_seconds=900.0,
        output_json=output_json,
    )

    assert payload["schema_version"] == "mvp12.controlled_proactive_delivery.v1"
    assert payload["scheduler_result"]["status"] in {"pending_created", "held"}
    assert payload["delivery_result"]["status"] in {"artifact_emitted", "held"}
    assert output_json.exists()
    assert output_json.with_suffix(".md").exists()
    if payload["delivery_result"]["status"] == "artifact_emitted":
        assert payload["delivery_result"]["emitted_delivery"]["transport_source"] == "controlled_runner"
        assert payload["pending_proactive_followup"] is None

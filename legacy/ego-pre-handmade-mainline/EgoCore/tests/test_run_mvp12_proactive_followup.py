from __future__ import annotations

from pathlib import Path

import pytest

from EgoCore.tools.run_mvp12_proactive_followup import run_proactive_followup_session


@pytest.mark.asyncio
async def test_run_proactive_followup_session_produces_controlled_draft(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENEMOTION_MVP12_ARTIFACTS_DIR", str(tmp_path / "shadow"))
    output_json = tmp_path / "proactive_followup.json"

    payload = await run_proactive_followup_session(
        messages=[
            "我在想，意识的门槛其实可能比人类自以为的低很多。你怎么看？",
            "有主观能动性。",
            "我觉得是有了OS的操作员的感觉。",
        ],
        session_id="session:mvp12:proactive:test",
        idle_seconds=900.0,
        output_json=output_json,
    )

    assert payload["schema_version"] == "mvp12.proactive_followup.v1"
    assert payload["developmental_summary"]["background_thought_candidate_count"] >= 1
    assert output_json.exists()
    assert output_json.with_suffix(".md").exists()
    assert payload["initiative_verdict"]["status"] in {"delivery_ready", "held"}

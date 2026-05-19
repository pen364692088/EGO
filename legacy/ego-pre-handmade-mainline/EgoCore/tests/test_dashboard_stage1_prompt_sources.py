from __future__ import annotations

from datetime import datetime, timezone

from app.dashboard import stage1_prompt_sources as module


def test_build_hybrid_prompt_pack_uses_control_generated_and_chatlog_sources() -> None:
    pack = module.build_dashboard_stage1_prompt_pack(
        strategy="hybrid",
        now=datetime(2026, 4, 12, tzinfo=timezone.utc),
        allow_public_web=False,
    )

    assert pack.pack_id == "stage1_dashboard_ordinary_chat_hybrid_v1"
    assert len(pack.prompts) == 5
    assert pack.prompt_source_counts == {
        "repo_authored_control": 2,
        "generated": 2,
        "chatlog_curated": 1,
    }
    assert pack.prompt_pack_degraded is False
    assert pack.prompt_pack_summary["curated_slot_source"] == "chatlog_curated"
    assert [prompt.input_provenance.source_kind for prompt in pack.prompts[:2]] == [
        "repo_authored_control",
        "repo_authored_control",
    ]


def test_build_hybrid_prompt_pack_falls_back_to_generated_when_curated_sources_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(module, "_select_local_chatlog_prompt", lambda **kwargs: None)
    monkeypatch.setattr(module, "_select_external_curated_prompt", lambda **kwargs: None)

    pack = module.build_dashboard_stage1_prompt_pack(
        strategy="hybrid",
        now=datetime(2026, 4, 12, tzinfo=timezone.utc),
        allow_public_web=True,
    )

    assert len(pack.prompts) == 5
    assert pack.prompt_source_counts["generated"] == 3
    assert pack.prompt_pack_degraded is True
    assert pack.prompt_pack_summary["curated_slot_source"] == "generated"


def test_normalize_user_turn_rejects_slash_and_tool_like_inputs() -> None:
    assert module._normalize_user_turn("/status") is None
    assert module._normalize_user_turn("请你帮我执行 git status") is None
    assert module._normalize_user_turn("我们继续聊聊轻松一点的话题吧。") == "我们继续聊聊轻松一点的话题吧。"

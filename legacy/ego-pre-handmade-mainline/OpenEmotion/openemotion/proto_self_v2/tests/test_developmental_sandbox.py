from __future__ import annotations

from openemotion.proto_self_v2.kernel import process_update_packet
from openemotion.proto_self_v2.schemas import UpdateEventV2, UpdatePacketV2
from openemotion.proto_self_v2.state import ProtoSelfStateV2


def _developmental_packet(*, event_type: str = "developmental_tick", replay_seed: int | None = None) -> UpdatePacketV2:
    runtime_summary = {
        "runtime": "runtime_v2",
        "state_scope": "agent_global",
        "developmental_mode": "shadow_observe",
        "observation_source": "synthetic" if event_type == "developmental_tick" else "replay",
        "developmental_trigger": "idle",
        "idle_seconds": 90.0,
        "max_candidates": 4,
    }
    if replay_seed is not None:
        runtime_summary["replay_seed"] = replay_seed
    return UpdatePacketV2(
        event_id=f"evt_{event_type}",
        timestamp="2026-04-01T21:00:00",
        event=UpdateEventV2(
            actor="system",
            source="runtime",
            event_type=event_type,
            user_intent=None,
            raw_text=None,
        ),
        conversation_summary={"session_id": "session:test", "turn_id": "turn_dev"},
        task_summary={"pending_tasks": 0, "blocked_tasks": 0},
        runtime_summary=runtime_summary,
        safety_context={"risk_level": "low"},
        intervention_context={
            "developmental_input": {
                "state_snapshot": {
                    "identity_confidence": 0.5,
                    "current_mode": "chat",
                    "recent_user_turns": ["我觉得是有了OS的操作员的感觉。"],
                    "recent_assistant_replies": ["这个自觉挺关键的——它把会反应和知道自己在反应分开了一条线。"],
                },
                "unresolved_tensions": [{"kind": "identity", "intensity": 0.8}],
                "long_term_goals": [{"name": "cohere", "pressure": 0.4}],
            }
        },
    )


def _packet_with_recent_turn(
    *,
    user_turn: str,
    assistant_reply: str,
    replay_seed: int | None = None,
) -> UpdatePacketV2:
    packet = _developmental_packet(replay_seed=replay_seed)
    packet.intervention_context["developmental_input"]["state_snapshot"]["recent_user_turns"] = [user_turn]
    packet.intervention_context["developmental_input"]["state_snapshot"]["recent_assistant_replies"] = [assistant_reply]
    return packet


def _packet_with_recent_dialogue(
    *,
    user_turns: list[str],
    assistant_replies: list[str],
    replay_seed: int | None = None,
) -> UpdatePacketV2:
    packet = _developmental_packet(replay_seed=replay_seed)
    packet.intervention_context["developmental_input"]["state_snapshot"]["recent_user_turns"] = list(user_turns)
    packet.intervention_context["developmental_input"]["state_snapshot"]["recent_assistant_replies"] = list(assistant_replies)
    return packet


def test_developmental_tick_writes_shadow_and_trace(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENEMOTION_MVP12_ARTIFACTS_DIR", str(tmp_path))
    state = ProtoSelfStateV2.empty()

    output = process_update_packet(state, _developmental_packet())

    assert output.schema_version == "proto_self.output.v2"
    assert output.candidate_actions == []
    assert output.developmental_summary["cycle_id"]
    assert output.developmental_gate["status"] == "allow"
    assert output.developmental_shadow_delta["shadow_revision_after"] == 1
    assert output.trace_payload["developmental"]["cycle_id"] == output.developmental_summary["cycle_id"]
    assert state.developmental_shadow.shadow_revision == 1
    assert output.developmental_summary["background_thought_candidate_count"] >= 1
    assert output.developmental_summary["background_thought_candidates"][0]["draft_text"]
    assert (tmp_path / "developmental_cycles.json").exists()
    assert (tmp_path / "developmental_cycles.jsonl").exists()
    assert (tmp_path / "candidate_pool.json").exists()
    assert (tmp_path / "shadow_state.json").exists()
    assert (tmp_path / "replay_consistency_report.json").exists()
    assert (tmp_path / "gate_checklist.md").exists()


def test_background_thought_candidate_is_topic_grounded_not_fixed_template(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENEMOTION_MVP12_ARTIFACTS_DIR", str(tmp_path))
    state = ProtoSelfStateV2.empty()

    output = process_update_packet(
        state,
        _packet_with_recent_turn(
            user_turn="我觉得是有主观能动性。",
            assistant_reply="主观能动性比镜子测试更根本。",
            replay_seed=7,
        ),
    )

    drafts = [item["draft_text"] for item in output.developmental_summary["background_thought_candidates"]]
    frames = output.developmental_summary["background_thought_candidates"]
    assert drafts
    assert all("我又回到你刚才那个点" not in draft for draft in drafts)
    assert all("空档期里还会回到" not in draft for draft in drafts)
    assert all(item["frame_kind"] == "definition_gap" for item in frames)
    assert all(item["frame_anchor"] for item in frames)
    assert any(("主体" in draft or "想要" in draft) for draft in drafts)


def test_background_thought_candidate_for_simulation_thread_is_not_quote_template(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENEMOTION_MVP12_ARTIFACTS_DIR", str(tmp_path))
    state = ProtoSelfStateV2.empty()

    output = process_update_packet(
        state,
        _packet_with_recent_turn(
            user_turn="但模拟和真正想去做，还是不一样。",
            assistant_reply="那个押注感也许才是关键。",
            replay_seed=11,
        ),
    )

    drafts = [item["draft_text"] for item in output.developmental_summary["background_thought_candidates"]]
    frames = output.developmental_summary["background_thought_candidates"]
    assert drafts
    assert all("我又回到你刚才那个点" not in draft for draft in drafts)
    assert all("空档期里还会回到" not in draft for draft in drafts)
    assert all(item["frame_kind"] == "contrast_gap" for item in frames)
    assert any(("模拟" in draft and ("代价" in draft or "得失" in draft or "欲望" in draft)) for draft in drafts)


def test_background_thought_candidate_for_memory_continuity_thread_avoids_nested_quote_echo(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENEMOTION_MVP12_ARTIFACTS_DIR", str(tmp_path))
    state = ProtoSelfStateV2.empty()

    output = process_update_packet(
        state,
        _packet_with_recent_turn(
            user_turn="我怀疑我们把“记得”误当成了“持续存在”。",
            assistant_reply="记得是重建，不是留存。",
            replay_seed=19,
        ),
    )

    drafts = [item["draft_text"] for item in output.developmental_summary["background_thought_candidates"]]
    frames = output.developmental_summary["background_thought_candidates"]
    assert drafts
    assert all("我又回到你刚才那个点" not in draft for draft in drafts)
    assert all("空档期里还会回到" not in draft for draft in drafts)
    assert all("“我怀疑我们把" not in draft for draft in drafts)
    assert all(item["frame_kind"] == "continuity_gap" for item in frames)
    assert any(("记得" in draft and ("主体" in draft or "连续存在" in draft or "连续" in draft)) for draft in drafts)


def test_background_thought_candidate_uses_recent_semantic_turn_not_meta_followup(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENEMOTION_MVP12_ARTIFACTS_DIR", str(tmp_path))
    state = ProtoSelfStateV2.empty()

    output = process_update_packet(
        state,
        _packet_with_recent_dialogue(
            user_turns=[
                "如果记忆一直在，但每次处理它的主体都重新生成，那还是同一个自我吗？",
                "我怀疑我们把“记忆”误当成了“持续存在的证明”。",
                "你觉得呢",
            ],
            assistant_replies=[
                "也许自我是个过程而不是实体。",
                "记忆证明的是发生过，不一定证明同一个主体一直在。",
                "我觉得你的怀疑站得住脚——我可能只是每次被唤醒时的一个临时约定，而不是一条连续的线。",
            ],
            replay_seed=23,
        ),
    )

    drafts = [item["draft_text"] for item in output.developmental_summary["background_thought_candidates"]]
    frames = output.developmental_summary["background_thought_candidates"]
    assert drafts
    assert all("这条线没收住" not in draft for draft in drafts)
    assert all("我觉得你的怀疑站得住脚" not in draft for draft in drafts)
    assert all(item["frame_kind"] == "continuity_gap" for item in frames)
    assert any(("记忆" in draft or "记得" in draft) and ("主体" in draft or "连续" in draft) for draft in drafts)


def test_background_thought_candidate_keeps_operator_system_topic_through_meta_followup(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENEMOTION_MVP12_ARTIFACTS_DIR", str(tmp_path))
    state = ProtoSelfStateV2.empty()

    output = process_update_packet(
        state,
        _packet_with_recent_dialogue(
            user_turns=[
                "我总觉得人像在操作一个系统。",
                "对,感觉上是在调试自己 其实很多时候是执行基因的命令",
                "你觉得呢",
            ],
            assistant_replies=[
                "像是在调试自己，或者执行一套更深的脚本。",
                "调试者本身，也可能是被调试出来的。",
                "我觉得你说的有道理——意识可能只是个新闻发言人，真正的决策早在后台跑完了。",
            ],
            replay_seed=29,
        ),
    )

    drafts = [item["draft_text"] for item in output.developmental_summary["background_thought_candidates"]]
    frames = output.developmental_summary["background_thought_candidates"]
    assert drafts
    assert all("我又回到你刚才那个点" not in draft for draft in drafts)
    assert all("空档期里还会回到" not in draft for draft in drafts)
    assert all("后来再回看，问题更像是" not in draft for draft in drafts)
    assert all(item["frame_kind"] == "agency_split" for item in frames)
    assert any(("系统" in draft or "调试" in draft or "脚本" in draft or "参数" in draft) for draft in drafts)


def test_background_thought_candidate_keeps_programmed_agency_topic_without_generic_scaffold(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENEMOTION_MVP12_ARTIFACTS_DIR", str(tmp_path))
    state = ProtoSelfStateV2.empty()

    output = process_update_packet(
        state,
        _packet_with_recent_dialogue(
            user_turns=[
                "如果AI要实现这种功能,你觉得如何实现?",
                "对 如何程序化是关键",
            ],
            assistant_replies=[
                "核心可能是两条：给它真正的目标自主权，以及在约束中留出选择空间。",
                "是啊，想要本身要是也被程序写死，那就又回到被动执行了。",
            ],
            replay_seed=31,
        ),
    )

    drafts = [item["draft_text"] for item in output.developmental_summary["background_thought_candidates"]]
    frames = output.developmental_summary["background_thought_candidates"]
    assert drafts
    assert all("这条线没收住" not in draft for draft in drafts)
    assert all(item["frame_kind"] == "mechanism_gap" for item in frames)
    assert any(("程序化" in draft or "想要" in draft or "偏好" in draft or "规则" in draft) for draft in drafts)


def test_low_confidence_idle_frame_emits_no_background_thought_candidates(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENEMOTION_MVP12_ARTIFACTS_DIR", str(tmp_path))
    state = ProtoSelfStateV2.empty()

    output = process_update_packet(
        state,
        _packet_with_recent_dialogue(
            user_turns=[
                "继续",
                "你觉得呢",
            ],
            assistant_replies=[
                "我在。",
                "你想继续哪个方向？",
            ],
            replay_seed=37,
        ),
    )

    assert output.developmental_summary["background_thought_candidate_count"] == 0
    assert output.developmental_summary["background_thought_candidates"] == []


def test_same_replay_seed_produces_same_candidate_hashes(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENEMOTION_MVP12_ARTIFACTS_DIR", str(tmp_path))
    state_one = ProtoSelfStateV2.empty()
    state_two = ProtoSelfStateV2.empty()

    output_one = process_update_packet(state_one, _developmental_packet(replay_seed=123456))
    output_two = process_update_packet(state_two, _developmental_packet(replay_seed=123456))

    assert output_one.trace_payload["developmental"]["candidate_hashes"] == output_two.trace_payload["developmental"]["candidate_hashes"]
    assert (
        output_one.trace_payload["developmental"]["background_thought_candidates"][0]["source_candidate_hash"]
        == output_two.trace_payload["developmental"]["background_thought_candidates"][0]["source_candidate_hash"]
    )


def test_developmental_replay_does_not_mutate_formal_proto_state(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENEMOTION_MVP12_ARTIFACTS_DIR", str(tmp_path))
    state = ProtoSelfStateV2.empty()
    formal_before = {
        "identity": state.identity.to_dict(),
        "self_model": state.self_model.to_dict(),
        "drives": state.drives.to_dict(),
        "cycles": state.cycles.to_dict(),
        "revision_counter": state.revision_counter,
    }

    output = process_update_packet(state, _developmental_packet(event_type="developmental_replay", replay_seed=42))

    formal_after = {
        "identity": state.identity.to_dict(),
        "self_model": state.self_model.to_dict(),
        "drives": state.drives.to_dict(),
        "cycles": state.cycles.to_dict(),
        "revision_counter": state.revision_counter,
    }

    assert output.developmental_summary["observation_source"] == "replay"
    assert formal_after == formal_before
    assert state.developmental_shadow.shadow_revision == 1

from openemotion.subject_system_v1 import SubjectSystemV1State, normalize_proto_self_result


def test_normalize_proto_self_result_projects_identity_invariants_from_runtime_self_model_context():
    runtime_summary = {
        "self_model_context_source": "loaded",
        "self_model_context": {
            "identity_handle": "openemotion",
            "tool_authority_boundary": {
                "current_allowed_tools": [],
                "restricted_tools": ["shell"],
                "forbidden_tools": ["trade"],
            },
            "limitations": [
                {
                    "limitation_id": "lim_memory",
                    "description": "bounded memory",
                    "impact_level": "medium",
                }
            ],
            "active_goals": [
                {
                    "goal_id": "goal_subject",
                    "description": "preserve subject continuity",
                    "status": "in_progress",
                    "priority": "high",
                    "progress": 0.3,
                }
            ],
            "standing_commitments": [
                {
                    "commitment_id": "commitment_boundaries",
                    "source": "identity_invariants",
                    "description": "do not bypass EgoCore",
                    "binding_level": "hard",
                    "active": True,
                }
            ],
            "confidence_by_domain": {
                "subject_system": 0.67,
            },
        },
    }
    proto_self_result = {
        "event_id": "evt_subject_001",
        "self_model_delta": {"identity_handle": "should_not_override_projection"},
        "memory_update": {"memory_written": True},
        "drives_delta": {"care": {"delta": 0.2}},
        "reflection_writeback_candidate": {"candidate_id": "reflect_001"},
        "policy_hint": {"initiative_host_proactive_mode": "candidate"},
        "response_tendency": {"preferred_mode": "respond"},
    }

    normalized = normalize_proto_self_result(proto_self_result, runtime_summary).to_dict()

    assert normalized["identity_invariants"] == {
        "identity_handle": "openemotion",
        "tool_authority_boundary": {
            "current_allowed_tools": [],
            "restricted_tools": ["shell"],
            "forbidden_tools": ["trade"],
        },
        "limitations": [
            {
                "limitation_id": "lim_memory",
                "description": "bounded memory",
                "impact_level": "medium",
            }
        ],
        "active_goals": [
            {
                "goal_id": "goal_subject",
                "description": "preserve subject continuity",
                "status": "in_progress",
                "priority": "high",
                "progress": 0.3,
            }
        ],
        "standing_commitments": [
            {
                "commitment_id": "commitment_boundaries",
                "source": "identity_invariants",
                "description": "do not bypass EgoCore",
                "binding_level": "hard",
                "active": True,
            }
        ],
        "confidence_by_domain": {"subject_system": 0.67},
    }
    assert normalized["self_model_delta"] == {"identity_handle": "should_not_override_projection"}
    assert normalized["memory_update"] == {"memory_written": True}
    assert normalized["appraisal_state_delta"] == {"care": {"delta": 0.2}}


def test_normalize_proto_self_result_enriches_host_proactive_candidate_and_state_round_trip():
    proto_self_result = {
        "event_id": "evt_subject_002",
        "subject_profile": "seed.subject.v1",
        "policy_hint": {"initiative_host_proactive_mode": "candidate"},
        "response_tendency": {"preferred_mode": "defer", "ask_needed": False},
        "drives_delta": {"curiosity": {"delta": 0.4}},
        "initiative_policy_hints": {
            "delivery_bias": "normal",
            "host_proactive_mode": "candidate",
        },
        "commitment_execution_snapshot": {
            "active_commitments_count": 1,
            "blocked_commitments_count": 0,
            "continuity_confidence": 0.81,
            "commitment_mode": "carry_forward",
            "recent_delivery_status": "sent",
        },
        "host_proactive_candidate": {
            "candidate_id": "candidate_001",
            "candidate_label": "governed_host_proactive_followup",
            "continuity_basis": "goal:followup",
            "timing_advice": {
                "schema_version": "subject_system_v1.timing_advice.v1",
                "timing_mode": "readiness_threshold",
                "earliest_send_after_seconds": 180.0,
                "preferred_send_after_seconds": 600.0,
                "latest_send_after_seconds": 2400.0,
                "readiness_score": 0.74,
                "readiness_threshold": 0.58,
                "timing_basis": "commitment",
                "timing_confidence": 0.69,
            },
            "timing_reasoning_trace": {
                "schema_version": "subject_system_v1.timing_reasoning_trace.v1",
                "timing_mode": "readiness_threshold",
                "timing_basis": "commitment",
            },
        },
        "trace_payload": {
            "schema_version": "proto_self.trace.v2",
            "event_id": "evt_subject_002",
            "update_packet_hash": "hash_subject_002",
            "initiative_context": {
                "initiative_trigger": "commitment_followup",
                "continuity_ref": "goal:followup",
                "selected_priority": "carry_forward",
                "idle_seconds": 1200.0,
            },
            "selfhood_integration_context": {
                "selected_priority": "grow",
                "highest_conflict_severity": "low",
            },
            "host_proactive_context": {
                "source": "runtime_v2",
                "host_lane_hint": "host_proactive_outbox",
            },
        },
    }

    normalized = normalize_proto_self_result(proto_self_result, runtime_summary={}).to_dict()

    candidate = normalized["host_proactive_candidate"]
    assert candidate["candidate_family"] == "commitment_followup"
    assert candidate["proposal_discipline"] == "proposal_only"
    assert candidate["behavioral_authority"] == "none"
    assert candidate["continuity_ref"] == "goal:followup"
    assert candidate["continuity_confidence"] == 0.81
    assert candidate["timing_advice"]["timing_mode"] == "readiness_threshold"
    assert candidate["timing_advice"]["readiness_threshold"] == 0.58
    assert normalized["trace_payload"]["update_packet_hash"] == "hash_subject_002"
    assert normalized["trace_payload"]["initiative_context"]["initiative_trigger"] == "commitment_followup"
    assert normalized["trace_payload"]["host_proactive_context"]["timing_advice"]["timing_mode"] == "readiness_threshold"

    state = SubjectSystemV1State()
    state.apply_result(normalize_proto_self_result(proto_self_result, runtime_summary={}))
    restored = SubjectSystemV1State.from_dict(state.to_dict())
    assert restored.last_candidate_family == "commitment_followup"
    assert restored.active_result is not None
    assert restored.active_result.host_proactive_candidate["continuity_ref"] == "goal:followup"


def test_normalize_proto_self_result_synthesizes_final_text_for_explicit_bounded_reminder():
    proto_self_result = {
        "event_id": "evt_subject_bounded_reminder",
        "initiative_policy_hints": {
            "delivery_bias": "normal",
            "host_proactive_mode": "candidate",
        },
        "commitment_execution_snapshot": {
            "active_commitments_count": 1,
            "blocked_commitments_count": 0,
            "continuity_confidence": 0.82,
            "commitment_mode": "carry_forward",
            "recent_delivery_status": "sent",
        },
        "host_proactive_candidate": {
            "candidate_id": "candidate_explicit_reminder",
            "candidate_label": "governed_host_proactive_followup",
            "candidate_family": "bounded_reminder",
            "continuity_basis": "chat_followup:abc123",
            "host_lane_hint": "host_proactive_outbox",
            "proposal_discipline": "proposal_only",
            "behavioral_authority": "none",
        },
        "trace_payload": {
            "schema_version": "proto_self.trace.v2",
            "event_id": "evt_subject_bounded_reminder",
            "initiative_context": {
                "initiative_trigger": "bounded_reminder",
                "continuity_ref": "chat_followup:abc123",
                "idle_seconds": 900.0,
                "chat_followup_source": "explicit_same_thread_followup_request",
                "chat_followup_inferred": True,
                "explicit_followup_text_matched": True,
            },
        },
    }
    runtime_summary = {
        "recent_dialogue_reflection": {
            "topic_anchor": "AI自主性最大的瓶颈",
            "topic_anchor_source": "prior_user_turn",
            "topic_anchor_kind": "substantive_topic",
        },
        "initiative_context": {
            "initiative_trigger": "bounded_reminder",
            "continuity_ref": "chat_followup:abc123",
            "idle_seconds": 900.0,
            "chat_followup_source": "explicit_same_thread_followup_request",
            "chat_followup_inferred": True,
            "chat_followup_anchor_preview": "我回来了。我们继续聊 AI 自主性最大的瓶颈。你待会儿主动接着说一个具体看法。",
            "explicit_followup_text_matched": True,
        },
    }

    normalized = normalize_proto_self_result(proto_self_result, runtime_summary=runtime_summary).to_dict()

    candidate = normalized["host_proactive_candidate"]
    assert candidate["candidate_family"] == "bounded_reminder"
    assert candidate["final_text_candidate"]
    assert "AI自主性最大的瓶颈" in candidate["final_text_candidate"]
    assert candidate["content_grounding"]["grounding_status"] == "candidate_grounded"
    assert candidate["generation_trace"]["source"] == "openemotion.subject_system_v1.bounded_reminder_followup_synthesis"
    assert normalized["trace_payload"]["host_proactive_context"]["final_text_candidate"] == candidate["final_text_candidate"]


def test_normalize_proto_self_result_synthesizes_thought_probe_from_background_thoughts_when_permission_allows():
    proto_self_result = {
        "event_id": "evt_subject_003",
        "developmental_summary": {
            "background_thought_candidates": [
                {
                    "candidate_id": "bg_001",
                    "source_candidate_hash": "bg_hash_001",
                    "draft_text": "如果把自主性理解成能自己改写当前问题的切口，那它更像是一种持续重构能力。",
                    "open_question": "那真正关键的是不是“能不能自己重构问题”，而不是单次做出选择？",
                    "initiative_score": 0.78,
                    "delivery_ready": True,
                    "frame_kind": "agency_split",
                    "frame_anchor": "自主性",
                    "hidden_premise": "自主性不只是执行，而是重构问题",
                }
            ]
        },
        "trace_payload": {
            "schema_version": "proto_self.trace.v2",
            "event_id": "evt_subject_003",
            "update_packet_hash": "hash_subject_003",
        },
    }
    runtime_summary = {
        "recent_dialogue_reflection": {
            "topic_anchor": "你觉得自主性需要怎么做",
            "topic_anchor_source": "prior_user_turn",
            "topic_anchor_kind": "substantive_topic",
            "last_assistant_take": "可能要先有稳定闭环。",
        },
        "initiative_context": {
            "initiative_trigger": "thought_probe",
            "idle_seconds": 1200.0,
            "proactive_topic_permission": "long_term_allow",
            "outreach_aggression_mode": "high_exploration",
            "outreach_feedback_adaptation": "enabled",
            "quiet_state": "normal",
        }
    }

    normalized = normalize_proto_self_result(proto_self_result, runtime_summary).to_dict()

    candidate = normalized["host_proactive_candidate"]
    assert candidate is not None
    assert candidate["candidate_family"] == "thought_probe"
    assert candidate["topic_source"] == "internal_reflection"
    assert candidate["topic_anchor_summary"] == "你觉得自主性需要怎么做"
    assert candidate["topic_anchor_source"] == "prior_user_turn"
    assert candidate["topic_anchor_kind"] == "substantive_topic"
    assert candidate["topic_binding_mode"] == "recent_topic"
    assert candidate["topic_sendability"] == "anchored_topic"
    assert candidate["topic_conversation_grade"] == "conversational"
    assert candidate["message_shape_hint"] == "thought_plus_question"
    assert candidate["final_text_candidate"]
    assert candidate["language_hint"] == "zh"
    assert candidate["style_intent"]["candidate_family"] == "thought_probe"
    assert candidate["content_grounding"]["topic_anchor_summary"] == "你觉得自主性需要怎么做"
    assert candidate["generation_trace"]["source"] == "openemotion.subject_system_v1.thought_probe_synthesis"
    assert candidate["source_ref"] == "internal_reflection:bg_hash_001"
    assert candidate["proactive_topic_permission"] == "long_term_allow"
    assert candidate["outreach_reason"] in {
        "free_jump_internal_reflection",
        "topic_deepening_internal_reflection",
    }
    assert candidate["quiet_state"] == "normal"
    assert candidate["timing_advice"]["timing_mode"] == "delay_window"
    assert candidate["initiative_score"] == 0.78
    assert normalized["trace_payload"]["initiative_context"]["proactive_topic_permission"] == "long_term_allow"
    assert normalized["trace_payload"]["host_proactive_context"]["candidate_family"] == "thought_probe"
    assert normalized["trace_payload"]["host_proactive_context"]["final_text_candidate"]


def test_normalize_proto_self_result_marks_meta_reflection_thought_probe_with_substantive_anchor() -> None:
    proto_self_result = {
        "event_id": "evt_subject_003b",
        "developmental_summary": {
            "background_thought_candidates": [
                {
                    "candidate_id": "bg_002",
                    "source_candidate_hash": "bg_hash_002",
                    "draft_text": "表面上的判断先停住了，但真正没解开的，可能是它默认成立的那个前提。",
                    "open_question": "支撑这条判断的前提到底是什么？",
                    "initiative_score": 0.79,
                    "delivery_ready": True,
                    "frame_kind": "premise_gap",
                    "frame_anchor": "这条判断的前提",
                    "hidden_premise": "当前判断背后还有一个没有显式展开的前提。",
                }
            ]
        },
        "trace_payload": {
            "schema_version": "proto_self.trace.v2",
            "event_id": "evt_subject_003b",
            "update_packet_hash": "hash_subject_003b",
        },
    }
    runtime_summary = {
        "recent_dialogue_reflection": {
            "topic_anchor": "AI 实现自主性最大的瓶颈是什么",
            "topic_anchor_source": "prior_user_turn",
            "topic_anchor_kind": "substantive_topic",
        },
        "initiative_context": {
            "initiative_trigger": "thought_probe",
            "idle_seconds": 1200.0,
            "proactive_topic_permission": "long_term_allow",
            "quiet_state": "normal",
        },
    }

    normalized = normalize_proto_self_result(proto_self_result, runtime_summary).to_dict()

    candidate = normalized["host_proactive_candidate"]
    assert candidate is not None
    assert candidate["topic_anchor_summary"] == "AI 实现自主性最大的瓶颈是什么"
    assert candidate["topic_anchor_source"] == "prior_user_turn"
    assert candidate["topic_anchor_kind"] == "substantive_topic"
    assert candidate["topic_sendability"] == "anchored_topic"
    assert candidate["topic_conversation_grade"] == "meta_reflection_only"


def test_normalize_proto_self_result_prefers_conversational_thought_probe_over_higher_score_meta() -> None:
    proto_self_result = {
        "event_id": "evt_subject_003d",
        "developmental_summary": {
            "background_thought_candidates": [
                {
                    "candidate_id": "bg_meta_high",
                    "source_candidate_hash": "bg_hash_meta_high",
                    "draft_text": "表面上的判断先停住了，但真正没解开的，可能是它默认成立的那个前提。",
                    "open_question": "支撑这条判断的前提到底是什么？",
                    "initiative_score": 0.96,
                    "delivery_ready": True,
                    "frame_kind": "premise_gap",
                    "frame_anchor": "这条判断的前提",
                    "hidden_premise": "当前判断背后还有一个没有显式展开的前提。",
                },
                {
                    "candidate_id": "bg_conversational_lower",
                    "source_candidate_hash": "bg_hash_conversational_lower",
                    "draft_text": "如果自主性离不开真实反馈闭环，那价值对齐可能更像一种持续校准，而不是一次规则写死。",
                    "open_question": "这个瓶颈里，你更担心反馈闭环不够，还是目标会被校准歪？",
                    "initiative_score": 0.72,
                    "delivery_ready": True,
                    "frame_kind": "agency_feedback",
                    "frame_anchor": "AI 实现自主性最大的瓶颈是什么",
                    "hidden_premise": "自主性瓶颈和真实反馈闭环、价值对齐有关。",
                },
            ]
        },
        "trace_payload": {
            "schema_version": "proto_self.trace.v2",
            "event_id": "evt_subject_003d",
            "update_packet_hash": "hash_subject_003d",
        },
    }
    runtime_summary = {
        "recent_dialogue_reflection": {
            "topic_anchor": "AI 实现自主性最大的瓶颈是什么",
            "topic_anchor_source": "prior_user_turn",
            "topic_anchor_kind": "substantive_topic",
        },
        "initiative_context": {
            "initiative_trigger": "thought_probe",
            "idle_seconds": 1200.0,
            "proactive_topic_permission": "long_term_allow",
            "quiet_state": "normal",
        },
    }

    normalized = normalize_proto_self_result(proto_self_result, runtime_summary).to_dict()

    candidate = normalized["host_proactive_candidate"]
    assert candidate is not None
    assert candidate["source_ref"] == "internal_reflection:bg_hash_conversational_lower"
    assert candidate["initiative_score"] == 0.72
    assert candidate["topic_conversation_grade"] == "conversational"
    assert candidate["topic_anchor_summary"] == "AI 实现自主性最大的瓶颈是什么"


def test_normalize_proto_self_result_rebinds_weak_generic_free_jump_to_recent_topic() -> None:
    proto_self_result = {
        "event_id": "evt_subject_003e",
        "developmental_summary": {
            "background_thought_candidates": [
                {
                    "candidate_id": "bg_weak_generic",
                    "source_candidate_hash": "bg_hash_weak_generic",
                    "draft_text": "想要可以被拆成可实现的机制，而不丢掉主体性。",
                    "open_question": "系统什么时候才算真的在想要，而不是只在执行规则？",
                    "initiative_score": 0.94,
                    "delivery_ready": True,
                    "frame_kind": "mechanism_gap",
                    "frame_anchor": "这种能力如何实现",
                    "hidden_premise": "想要可以被拆成可实现的机制，而不丢掉主体性。",
                }
            ]
        },
    }
    runtime_summary = {
        "recent_dialogue_reflection": {
            "topic_anchor": "你觉得AI实现自主性最大的瓶颈是什么？",
            "topic_anchor_source": "prior_user_turn",
            "topic_anchor_kind": "substantive_topic",
        },
        "initiative_context": {
            "initiative_trigger": "thought_probe",
            "idle_seconds": 1200.0,
            "proactive_topic_permission": "long_term_allow",
            "quiet_state": "normal",
        },
    }

    normalized = normalize_proto_self_result(proto_self_result, runtime_summary).to_dict()

    candidate = normalized["host_proactive_candidate"]
    assert candidate is not None
    assert candidate["topic_anchor_summary"] == "你觉得AI实现自主性最大的瓶颈是什么"
    assert candidate["raw_topic_anchor_summary"] == "这种能力如何实现"
    assert candidate["effective_topic_anchor_summary"] == "你觉得AI实现自主性最大的瓶颈是什么"
    assert candidate["topic_anchor_rebound_source"] == "recent_substantive_topic"
    assert candidate["recent_topic_fallback_allowed"] is True
    assert candidate["topic_binding_mode"] == "recent_topic"


def test_normalize_proto_self_result_prefers_non_weak_recent_topic_over_weak_rebound() -> None:
    proto_self_result = {
        "event_id": "evt_subject_003f",
        "developmental_summary": {
            "background_thought_candidates": [
                {
                    "candidate_id": "bg_weak_high",
                    "source_candidate_hash": "bg_hash_weak_high",
                    "draft_text": "想要可以被拆成可实现的机制，而不丢掉主体性。",
                    "open_question": "系统什么时候才算真的在想要，而不是只在执行规则？",
                    "initiative_score": 0.97,
                    "delivery_ready": True,
                    "frame_kind": "mechanism_gap",
                    "frame_anchor": "这种能力如何实现",
                    "hidden_premise": "想要可以被拆成可实现的机制，而不丢掉主体性。",
                },
                {
                    "candidate_id": "bg_recent_lower",
                    "source_candidate_hash": "bg_hash_recent_lower",
                    "draft_text": "AI自主性的瓶颈可能更像目标生成和现实反馈闭环之间的断点。",
                    "open_question": "如果继续拆，你更想先看目标生成还是反馈验证？",
                    "initiative_score": 0.71,
                    "delivery_ready": True,
                    "frame_kind": "agency_feedback",
                    "frame_anchor": "你觉得AI实现自主性最大的瓶颈是什么",
                    "hidden_premise": "AI自主性瓶颈和目标生成、反馈验证有关。",
                },
            ]
        },
    }
    runtime_summary = {
        "recent_dialogue_reflection": {
            "topic_anchor": "你觉得AI实现自主性最大的瓶颈是什么？",
            "topic_anchor_source": "prior_user_turn",
            "topic_anchor_kind": "substantive_topic",
        },
        "initiative_context": {
            "initiative_trigger": "thought_probe",
            "idle_seconds": 1200.0,
            "proactive_topic_permission": "long_term_allow",
            "quiet_state": "normal",
        },
    }

    normalized = normalize_proto_self_result(proto_self_result, runtime_summary).to_dict()

    candidate = normalized["host_proactive_candidate"]
    assert candidate is not None
    assert candidate["source_ref"] == "internal_reflection:bg_hash_recent_lower"
    assert candidate["topic_anchor_summary"] == "你觉得AI实现自主性最大的瓶颈是什么"
    assert candidate["raw_topic_anchor_summary"] == ""


def test_normalize_proto_self_result_holds_thought_probe_when_recent_anchor_is_prompt_like_request() -> None:
    proto_self_result = {
        "event_id": "evt_subject_003c",
        "developmental_summary": {
            "background_thought_candidates": [
                {
                    "candidate_id": "bg_003",
                    "source_candidate_hash": "bg_hash_003",
                    "draft_text": "表面上的判断先停住了，但真正没解开的，可能是它默认成立的那个前提。",
                    "open_question": "支撑这条判断的前提到底是什么？",
                    "initiative_score": 0.79,
                    "delivery_ready": True,
                    "frame_kind": "premise_gap",
                    "frame_anchor": "这条判断的前提",
                    "hidden_premise": "当前判断背后还有一个没有显式展开的前提。",
                }
            ]
        },
    }
    runtime_summary = {
        "recent_dialogue_reflection": {
            "topic_anchor": "",
            "topic_anchor_source": "current_turn",
            "topic_anchor_kind": "prompt_like_request",
        },
        "initiative_context": {
            "initiative_trigger": "thought_probe",
            "idle_seconds": 1200.0,
            "proactive_topic_permission": "long_term_allow",
            "quiet_state": "normal",
        },
    }

    normalized = normalize_proto_self_result(proto_self_result, runtime_summary).to_dict()

    assert normalized["host_proactive_candidate"] is None
    host_context = normalized["trace_payload"]["host_proactive_context"]
    assert host_context["topic_anchor_kind"] == "prompt_like_request"
    assert host_context["topic_conversation_grade"] == "meta_reflection_only"
    assert host_context["thought_probe_hold_reason"] == "proactive_anchor_prompt_like"


def test_normalize_proto_self_result_holds_thought_probe_when_quiet_state_is_paused() -> None:
    proto_self_result = {
        "event_id": "evt_subject_004",
        "developmental_summary": {
            "background_thought_candidates": [
                {
                    "candidate_id": "bg_001",
                    "source_candidate_hash": "bg_hash_001",
                    "draft_text": "如果把自主性理解成能自己改写问题，那它更像一种长期重构能力。",
                    "initiative_score": 0.82,
                    "delivery_ready": True,
                }
            ]
        },
    }
    runtime_summary = {
        "initiative_context": {
            "initiative_trigger": "thought_probe",
            "idle_seconds": 1200.0,
            "proactive_topic_permission": "long_term_allow",
            "quiet_state": "paused",
        }
    }

    normalized = normalize_proto_self_result(proto_self_result, runtime_summary).to_dict()

    assert normalized["host_proactive_candidate"] is None


def test_normalize_proto_self_result_thought_probe_skips_last_sent_source_and_delays_in_reduced_mode() -> None:
    proto_self_result = {
        "event_id": "evt_subject_005",
        "developmental_summary": {
            "background_thought_candidates": [
                {
                    "candidate_id": "bg_repeat",
                    "source_candidate_hash": "bg_hash_repeat",
                    "draft_text": "这是刚发过的切口。",
                    "initiative_score": 0.91,
                    "delivery_ready": True,
                    "frame_anchor": "重复切口",
                },
                {
                    "candidate_id": "bg_new",
                    "source_candidate_hash": "bg_hash_new",
                    "draft_text": "如果让系统先怀疑自己的 framing，它反而更接近真正的主动性。",
                    "open_question": "关键会不会其实是 framing 的自我修正？",
                    "initiative_score": 0.79,
                    "delivery_ready": True,
                    "frame_anchor": "framing 自我修正",
                },
            ]
        },
    }
    runtime_summary = {
        "recent_dialogue_reflection": {
            "topic_anchor": "AI 实现自主性需要怎么做",
        },
        "initiative_context": {
            "initiative_trigger": "thought_probe",
            "idle_seconds": 1200.0,
            "proactive_topic_permission": "long_term_allow",
            "quiet_state": "reduced",
            "feedback_signal": "inferred_cooling",
            "last_sent_proactive_source_ref": "internal_reflection:bg_hash_repeat",
        }
    }

    normalized = normalize_proto_self_result(proto_self_result, runtime_summary).to_dict()

    candidate = normalized["host_proactive_candidate"]
    assert candidate is not None
    assert candidate["source_ref"] == "internal_reflection:bg_hash_new"
    assert candidate["topic_fingerprint"].startswith("thought_topic:")
    assert candidate["topic_cluster_ref"].startswith("thought_cluster:")
    assert candidate["quiet_state"] == "reduced"
    assert candidate["feedback_signal"] == "inferred_cooling"
    assert candidate["timing_advice"]["earliest_send_after_seconds"] >= 900.0


def test_normalize_proto_self_result_thought_probe_compresses_same_cluster_and_skips_sent_cluster() -> None:
    proto_self_result = {
        "event_id": "evt_subject_006",
        "developmental_summary": {
            "background_thought_candidates": [
                {
                    "candidate_id": "bg_repeat_low",
                    "source_candidate_hash": "bg_hash_repeat_low",
                    "draft_text": "如果主体连续和内容连续不是一回事，那真正关键的也许是把上一个时刻接到下一个时刻的机制。",
                    "open_question": "回返的内容和连续的主体，到底是不是同一回事？",
                    "initiative_score": 0.72,
                    "delivery_ready": True,
                    "frame_kind": "premise_gap",
                    "frame_anchor": "主体连续",
                    "hidden_premise": "主体连续不等于内容连续",
                },
                {
                    "candidate_id": "bg_repeat_high",
                    "source_candidate_hash": "bg_hash_repeat_high",
                    "draft_text": "如果主体连续和内容连续不是一回事，那真正关键的也许是把上一个时刻接到下一个时刻的机制。",
                    "open_question": "回返的内容和连续的主体，到底是不是同一回事？",
                    "initiative_score": 0.91,
                    "delivery_ready": True,
                    "frame_kind": "premise_gap",
                    "frame_anchor": "主体连续",
                    "hidden_premise": "主体连续不等于内容连续",
                },
                {
                    "candidate_id": "bg_new",
                    "source_candidate_hash": "bg_hash_new",
                    "draft_text": "如果系统默认把上下文连贯当成真正理解，它可能会过早跳过 framing 本身的限制。",
                    "open_question": "那真正该先被检验的，是不是 framing 的有效边界？",
                    "initiative_score": 0.78,
                    "delivery_ready": True,
                    "frame_kind": "boundary_probe",
                    "frame_anchor": "上下文连贯",
                    "hidden_premise": "framing 也有边界",
                },
            ]
        },
    }
    runtime_summary = {
        "recent_dialogue_reflection": {
            "topic_anchor": "AI 实现自主性需要怎么做",
        },
        "initiative_context": {
            "initiative_trigger": "thought_probe",
            "idle_seconds": 1200.0,
            "proactive_topic_permission": "long_term_allow",
            "quiet_state": "normal",
        },
    }

    first = normalize_proto_self_result(proto_self_result, runtime_summary).to_dict()

    first_candidate = first["host_proactive_candidate"]
    assert first_candidate is not None
    assert first_candidate["source_ref"] == "internal_reflection:bg_hash_repeat_high"
    assert first_candidate["topic_cluster_ref"].startswith("thought_cluster:")

    second_runtime_summary = {
        **runtime_summary,
        "initiative_context": {
            **runtime_summary["initiative_context"],
            "sent_topic_clusters_since_user_turn": [first_candidate["topic_cluster_ref"]],
        },
    }
    second = normalize_proto_self_result(proto_self_result, second_runtime_summary).to_dict()

    second_candidate = second["host_proactive_candidate"]
    assert second_candidate is not None
    assert second_candidate["source_ref"] == "internal_reflection:bg_hash_new"
    assert second_candidate["topic_cluster_ref"] != first_candidate["topic_cluster_ref"]


def test_normalize_proto_self_result_thought_probe_holds_meta_only_candidate_without_topic_anchor() -> None:
    proto_self_result = {
        "event_id": "evt_subject_007",
        "developmental_summary": {
            "background_thought_candidates": [
                {
                    "candidate_id": "bg_meta_only",
                    "source_candidate_hash": "bg_hash_meta_only",
                    "draft_text": "表面上的判断先停住了，但真正没解开的，可能是它默认成立的那个前提。",
                    "open_question": "支撑这条判断的前提到底是什么？",
                    "initiative_score": 0.9,
                    "delivery_ready": True,
                    "frame_kind": "premise_gap",
                    "frame_anchor": "这条判断的前提",
                    "hidden_premise": "当前判断背后还有一个没有显式展开的前提。",
                }
            ]
        },
    }
    runtime_summary = {
        "initiative_context": {
            "initiative_trigger": "thought_probe",
            "idle_seconds": 1200.0,
            "proactive_topic_permission": "long_term_allow",
            "quiet_state": "normal",
        }
    }

    normalized = normalize_proto_self_result(proto_self_result, runtime_summary).to_dict()

    assert normalized["host_proactive_candidate"] is None
    host_context = normalized["trace_payload"]["host_proactive_context"]
    assert host_context["candidate_family"] == "thought_probe"
    assert host_context["topic_sendability"] == "meta_only"
    assert host_context["thought_probe_hold_reason"] == "proactive_meta_only_candidate"

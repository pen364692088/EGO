from app.runtime_v2.host_proactive_candidate_arbiter import arbitrate_host_proactive_candidate


def _subject_system_payload(**candidate_overrides):
    candidate = {
        "candidate_id": "candidate_001",
        "candidate_family": "commitment_followup",
        "proposal_discipline": "proposal_only",
        "behavioral_authority": "none",
        "continuity_ref": "goal:followup",
        "continuity_confidence": 0.82,
        "delivery_failure": False,
        "selfhood_priority": "grow",
    }
    candidate.update(candidate_overrides)
    return {"host_proactive_candidate": candidate}


def test_commitment_followup_idle_candidate_becomes_suggest():
    decision = arbitrate_host_proactive_candidate(
        subject_system_v1=_subject_system_payload(),
        idle_eligible=True,
        active_task_present=False,
        runtime_guard={"delivery_failure": False},
    )

    assert decision["status"] == "candidate_ready"
    assert decision["mode"] == "suggest"
    assert decision["candidate_family"] == "commitment_followup"


def test_repair_review_family_always_asks_once_candidate_is_admitted():
    decision = arbitrate_host_proactive_candidate(
        subject_system_v1=_subject_system_payload(candidate_family="repair_review"),
        idle_eligible=True,
        active_task_present=False,
        runtime_guard={},
    )

    assert decision["status"] == "candidate_ready"
    assert decision["mode"] == "ask"
    assert decision["reason"] == "repair_review_family_requires_ask"


def test_bounded_reminder_requires_stable_continuity():
    decision = arbitrate_host_proactive_candidate(
        subject_system_v1=_subject_system_payload(
            candidate_family="bounded_reminder",
            continuity_ref="",
            continuity_confidence=0.42,
        ),
        idle_eligible=True,
        active_task_present=False,
        runtime_guard={},
    )

    assert decision["status"] == "held"
    assert decision["reason"] == "continuity_not_stable_enough"


def test_bounded_reminder_with_stable_continuity_becomes_suggest():
    decision = arbitrate_host_proactive_candidate(
        subject_system_v1=_subject_system_payload(
            candidate_family="bounded_reminder",
            continuity_ref="chat_followup:abc123",
            continuity_confidence=0.72,
            selfhood_priority="guard",
        ),
        idle_eligible=True,
        active_task_present=False,
        runtime_guard={},
    )

    assert decision["status"] == "candidate_ready"
    assert decision["mode"] == "suggest"
    assert decision["reason"] == "stable_bounded_reminder"


def test_active_task_blocks_candidate_even_when_family_is_valid():
    decision = arbitrate_host_proactive_candidate(
        subject_system_v1=_subject_system_payload(),
        idle_eligible=True,
        active_task_present=True,
        runtime_guard={},
    )

    assert decision["status"] == "held"
    assert decision["reason"] == "active_task_present"


def test_behavioral_authority_must_remain_none():
    decision = arbitrate_host_proactive_candidate(
        subject_system_v1=_subject_system_payload(behavioral_authority="transport"),
        idle_eligible=True,
        active_task_present=False,
        runtime_guard={},
    )

    assert decision["status"] == "held"
    assert decision["reason"] == "behavioral_authority_must_remain_none"


def test_delay_window_timing_holds_candidate_until_not_before() -> None:
    decision = arbitrate_host_proactive_candidate(
        subject_system_v1=_subject_system_payload(
            candidate_family="bounded_reminder",
            continuity_ref="chat_followup:abc123",
            continuity_confidence=0.72,
            idle_seconds=420.0,
            timing_advice={
                "schema_version": "subject_system_v1.timing_advice.v1",
                "timing_mode": "delay_window",
                "earliest_send_after_seconds": 540.0,
                "preferred_send_after_seconds": 660.0,
                "latest_send_after_seconds": 1260.0,
                "timing_basis": "continuity",
                "timing_confidence": 0.7,
            },
        ),
        idle_eligible=True,
        active_task_present=False,
        runtime_guard={},
    )

    assert decision["status"] == "held"
    assert decision["reason"] == "timing_window_not_open"
    assert decision["timing_verdict"]["reason"] == "timing_window_not_open"


def test_delay_window_timing_allows_candidate_once_not_before_has_passed() -> None:
    decision = arbitrate_host_proactive_candidate(
        subject_system_v1=_subject_system_payload(
            candidate_family="bounded_reminder",
            continuity_ref="chat_followup:abc123",
            continuity_confidence=0.72,
            idle_seconds=700.0,
            timing_advice={
                "schema_version": "subject_system_v1.timing_advice.v1",
                "timing_mode": "delay_window",
                "earliest_send_after_seconds": 540.0,
                "preferred_send_after_seconds": 660.0,
                "latest_send_after_seconds": 1260.0,
                "timing_basis": "continuity",
                "timing_confidence": 0.7,
            },
        ),
        idle_eligible=True,
        active_task_present=False,
        runtime_guard={},
    )

    assert decision["status"] == "candidate_ready"
    assert decision["timing_verdict"]["reason"] == "timing_window_open"


def test_readiness_threshold_timing_holds_until_score_crosses_threshold() -> None:
    decision = arbitrate_host_proactive_candidate(
        subject_system_v1=_subject_system_payload(
            candidate_family="commitment_followup",
            idle_seconds=300.0,
            timing_advice={
                "schema_version": "subject_system_v1.timing_advice.v1",
                "timing_mode": "readiness_threshold",
                "earliest_send_after_seconds": 180.0,
                "preferred_send_after_seconds": 600.0,
                "latest_send_after_seconds": 2400.0,
                "readiness_score": 0.41,
                "readiness_threshold": 0.58,
                "timing_basis": "commitment",
                "timing_confidence": 0.66,
            },
        ),
        idle_eligible=True,
        active_task_present=False,
        runtime_guard={},
    )

    assert decision["status"] == "held"
    assert decision["reason"] == "readiness_threshold_not_met"


def test_readiness_threshold_timing_allows_when_score_is_high_enough() -> None:
    decision = arbitrate_host_proactive_candidate(
        subject_system_v1=_subject_system_payload(
            candidate_family="commitment_followup",
            idle_seconds=300.0,
            timing_advice={
                "schema_version": "subject_system_v1.timing_advice.v1",
                "timing_mode": "readiness_threshold",
                "earliest_send_after_seconds": 180.0,
                "preferred_send_after_seconds": 600.0,
                "latest_send_after_seconds": 2400.0,
                "readiness_score": 0.71,
                "readiness_threshold": 0.58,
                "timing_basis": "commitment",
                "timing_confidence": 0.74,
            },
        ),
        idle_eligible=True,
        active_task_present=False,
        runtime_guard={},
    )

    assert decision["status"] == "candidate_ready"
    assert decision["timing_verdict"]["reason"] == "readiness_threshold_met"


def test_thought_probe_requires_long_term_permission_and_uses_candidate_content() -> None:
    decision = arbitrate_host_proactive_candidate(
        subject_system_v1=_subject_system_payload(
            candidate_family="thought_probe",
            continuity_ref="internal_reflection:bg_hash_001",
            continuity_confidence=0.74,
            source_ref="internal_reflection:bg_hash_001",
            topic_source="internal_reflection",
            topic_summary="自主性是否等于重构问题的能力",
            message_shape_hint="thought_plus_question",
            draft_text="如果把自主性理解成能自己改写当前问题的切口，那它更像是一种持续重构能力。",
            open_question="那真正关键的是不是“能不能自己重构问题”，而不是单次做出选择？",
            proactive_topic_permission="long_term_allow",
        ),
        idle_eligible=True,
        active_task_present=False,
        runtime_guard={},
    )

    assert decision["status"] == "candidate_ready"
    assert decision["mode"] == "suggest"
    assert decision["reason"] == "durable_thought_probe_ready"
    assert "持续重构能力" in decision["draft_text"]
    assert "重构问题" in decision["draft_text"]


def test_thought_probe_holds_without_long_term_permission() -> None:
    decision = arbitrate_host_proactive_candidate(
        subject_system_v1=_subject_system_payload(
            candidate_family="thought_probe",
            source_ref="internal_reflection:bg_hash_001",
            draft_text="我刚想到一个相关切口。",
            proactive_topic_permission="disabled",
        ),
        idle_eligible=True,
        active_task_present=False,
        runtime_guard={},
    )

    assert decision["status"] == "held"
    assert decision["reason"] == "proactive_topic_permission_not_allowed"


def test_thought_probe_holds_when_quiet_state_is_paused() -> None:
    decision = arbitrate_host_proactive_candidate(
        subject_system_v1=_subject_system_payload(
            candidate_family="thought_probe",
            source_ref="internal_reflection:bg_hash_001",
            draft_text="我刚想到一个新的切口。",
            proactive_topic_permission="long_term_allow",
            quiet_state="paused",
        ),
        idle_eligible=True,
        active_task_present=False,
        runtime_guard={},
    )

    assert decision["status"] == "held"
    assert decision["reason"] == "quiet_state_paused"


def test_thought_probe_reduced_mode_requires_higher_value_candidate() -> None:
    low_value = arbitrate_host_proactive_candidate(
        subject_system_v1=_subject_system_payload(
            candidate_family="thought_probe",
            source_ref="internal_reflection:bg_hash_001",
            draft_text="我刚想到一个新的切口。",
            proactive_topic_permission="long_term_allow",
            quiet_state="reduced",
            initiative_score=0.61,
        ),
        idle_eligible=True,
        active_task_present=False,
        runtime_guard={},
    )
    high_value = arbitrate_host_proactive_candidate(
        subject_system_v1=_subject_system_payload(
            candidate_family="thought_probe",
            source_ref="internal_reflection:bg_hash_002",
            draft_text="如果把自主性理解成能重构问题，那它更像长期重写自身约束的能力。",
            proactive_topic_permission="long_term_allow",
            quiet_state="reduced",
            initiative_score=0.83,
        ),
        idle_eligible=True,
        active_task_present=False,
        runtime_guard={},
    )

    assert low_value["status"] == "held"
    assert low_value["reason"] == "reduced_mode_requires_higher_value_candidate"
    assert high_value["status"] == "candidate_ready"
    assert high_value["reason"] == "durable_thought_probe_ready"

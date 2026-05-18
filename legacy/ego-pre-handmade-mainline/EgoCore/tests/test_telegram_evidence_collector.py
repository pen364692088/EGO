from app.telegram_evidence_collector import TelegramEvidenceCollector


def test_collector_writes_authoritative_ledger_and_compatibility_mirrors(tmp_path):
    collector = TelegramEvidenceCollector(
        artifacts_dir=tmp_path,
        source_type="simulated",
        channel="telegram",
        evidence_level="E2",
    )

    collector.start_sample(
        {
            "update_id": 1001,
            "message": {
                "message_id": 1001,
                "date": 1774483895,
                "chat": {"id": 42, "type": "private"},
                "from": {"id": 7, "is_bot": False, "username": "tester"},
                "text": "你好",
            },
        }
    )
    collector.capture_normalized_event(
        {
            "event_id": "session:test_turn_001",
            "timestamp": "2026-03-25T19:11:35.097599",
            "actor": "user",
            "source": "telegram",
            "event_type": "user_message",
            "conversation_context": {
                "session_id": "session:test",
                "thread_id": "session:test",
                "turn_id": "turn_001",
            },
            "user_intent": "你好",
            "raw_text": "你好",
        }
    )
    collector.capture_openemotion_result(
        {
            "schema_version": "proto_self.output.v1",
            "event_id": "session:test_turn_001",
            "policy_hint": {"risk_bias": "normal"},
            "trace_payload": {
                "schema_version": "proto_self.trace.v1",
                "event_id": "session:test_turn_001",
                "policy_hint": {"risk_bias": "normal"},
            },
        }
    )
    collector.capture_restore_observation(
        {
            "restore_id": "restore_001",
            "restore_status": "success",
            "post_restore_first_turn": True,
            "authority_source": "restore_audit",
        }
    )
    collector.capture_response_plan(
        {
            "status": "chat",
            "delivery_kind": "chat",
            "reply_length": 2,
        }
    )
    collector.capture_outbox_record(
        {
            "chat_id": 42,
            "message_id": 1002,
            "date": "2026-03-25T19:11:40.560504",
            "text_length": 2,
            "success": True,
        }
    )

    sample = collector.finalize_sample()
    assert sample is not None

    sample_dir = tmp_path / sample.sample_id
    ledger_path = sample_dir / "ledger.json"
    sample_path = sample_dir / "sample.json"
    replay_path = sample_dir / "replay.json"
    trace_path = sample_dir / "openemotion_trace.json"

    assert ledger_path.exists()
    assert sample_path.exists()
    assert replay_path.exists()
    assert trace_path.exists()

    ledger = sample.ledger
    assert ledger["ownership"]["primary_ledger_owner"] == "EgoCore host evidence ledger"
    assert ledger["openemotion"]["trace_payload"]["event_id"] == "session:test_turn_001"
    assert ledger["replay_input"]["authority"] == "OpenEmotion trace_payload within ledger.json"
    assert "sample.json" in ledger["compatibility_mirrors"]
    assert ledger["report_sources"]["sample_summary"] == "ledger.json"
    assert ledger["host"]["restore_observation"]["restore_id"] == "restore_001"
    assert sample.response_plan["restore_observation"]["post_restore_first_turn"] is True
    assert sample.normalized_event["runtime_summary"]["restore_observation"]["authority_source"] == "restore_audit"

    assert sample.replay["primary_ledger_ref"] == "ledger.json"
    assert sample.replay["replay_input_source"]["path"] == "openemotion.trace_payload"


def test_collector_keeps_parallel_message_samples_isolated(tmp_path):
    collector = TelegramEvidenceCollector(artifacts_dir=tmp_path)

    update_a = {
        "update_id": 2001,
        "message": {
            "message_id": 301,
            "date": 1774483895,
            "chat": {"id": 42, "type": "private"},
            "from": {"id": 7, "is_bot": False, "username": "tester"},
            "text": "first",
        },
    }
    update_b = {
        "update_id": 2002,
        "message": {
            "message_id": 302,
            "date": 1774483896,
            "chat": {"id": 42, "type": "private"},
            "from": {"id": 7, "is_bot": False, "username": "tester"},
            "text": "second",
        },
    }

    import contextvars

    ctx_a = contextvars.copy_context()
    ctx_b = contextvars.copy_context()

    ctx_a.run(collector.start_sample, update_a)
    ctx_b.run(collector.start_sample, update_b)

    ctx_a.run(collector.capture_normalized_event, {"event_id": "session:test_turn_a", "conversation_context": {"session_id": "a"}})
    ctx_b.run(collector.capture_normalized_event, {"event_id": "session:test_turn_b", "conversation_context": {"session_id": "b"}})

    sample_a = ctx_a.run(collector.finalize_sample)
    sample_b = ctx_b.run(collector.finalize_sample)

    assert sample_a is not None
    assert sample_b is not None
    assert sample_a.sample_id != sample_b.sample_id
    assert sample_a.normalized_event["event_id"] == "session:test_turn_a"
    assert sample_b.normalized_event["event_id"] == "session:test_turn_b"


def test_finalize_infers_minimal_response_plan_from_outbox(tmp_path):
    collector = TelegramEvidenceCollector(artifacts_dir=tmp_path)
    collector.start_sample(
        {
            "update_id": 3001,
            "message": {
                "message_id": 401,
                "date": 1774483897,
                "chat": {"id": 42, "type": "private"},
                "from": {"id": 7, "is_bot": False, "username": "tester"},
                "text": "/new",
            },
        }
    )
    collector.capture_outbox_record(
        {
            "chat_id": 42,
            "message_id": 402,
            "date": "2026-03-25T19:11:40.560504",
            "text_length": 120,
            "success": True,
        }
    )

    sample = collector.finalize_sample()
    assert sample is not None
    assert sample.response_plan is not None
    assert sample.response_plan["status"] == "delivered_without_explicit_plan"
    assert sample.response_plan["reply_length"] == 120
    assert sample.response_plan["inferred"] is True


def test_collector_keeps_openemotion_event_payloads_for_later_audit(tmp_path):
    collector = TelegramEvidenceCollector(artifacts_dir=tmp_path)
    collector.start_sample(
        {
            "update_id": 4001,
            "message": {
                "message_id": 501,
                "date": 1774483898,
                "chat": {"id": 42, "type": "private"},
                "from": {"id": 7, "is_bot": False, "username": "tester"},
                "text": "读取 app.py",
            },
        }
    )
    collector.capture_openemotion_result(
        {
            "schema_version": "proto_self.output.v2",
            "event_id": "session:test_turn_002",
            "subject_profile": "seed_v0_2",
            "candidate_actions": [{"action_type": "inspect_file"}],
            "trace_payload": {
                "schema_version": "proto_self.trace.v2",
                "event_id": "session:test_turn_002",
                "subject_profile": "seed_v0_2",
                "candidate_actions": [{"action_type": "inspect_file"}],
            },
        }
    )

    sample = collector.finalize_sample()
    assert sample is not None
    assert sample.openemotion_events[0]["payload"]["candidate_actions"][0]["action_type"] == "inspect_file"
    assert sample.openemotion_events[0]["payload"]["trace_payload"]["schema_version"] == "proto_self.trace.v2"
    assert sample.ledger["openemotion"]["events"][0]["payload"]["subject_profile"] == "seed_v0_2"

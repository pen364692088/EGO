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

    assert sample.replay["primary_ledger_ref"] == "ledger.json"
    assert sample.replay["replay_input_source"]["path"] == "openemotion.trace_payload"

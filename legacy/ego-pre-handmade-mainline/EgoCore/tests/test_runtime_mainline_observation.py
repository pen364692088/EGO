from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COMMON_SCRIPT = ROOT / "scripts" / "runtime_mainline_observation_common.py"
EVIDENCE_SCRIPT = ROOT / "OpenEmotion" / "tools" / "run_mvp12_controlled_evidence.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_load_observation_records_filters_invalid_entries(tmp_path):
    module = _load_module(COMMON_SCRIPT, "runtime_mainline_observation_common")
    record_path = tmp_path / "observations.jsonl"
    valid = {
        "schema_version": "observation_record.v1",
        "observation_source": "direct_real",
        "transport_source": "runtime_harness",
        "source": "runtime_harness",
        "session_id": "session:test",
        "turn_id": "turn_001",
        "ingress_event_id": "ing_001",
        "ingress_created_at": "2026-04-01T12:00:00",
        "ingress_text": "hello",
        "runtime_status": "chat",
        "runtime_reply_text": "raw hello",
        "delivery_event_id": "del_001",
        "delivery_created_at": "2026-04-01T12:00:01",
        "delivery_text": "hello",
        "reply_authority": "model_chat",
        "reply_origin": "chat_mainline",
        "delivery_kind": "chat",
        "delivery_authority_source": "response_contract.output_check",
        "output_check_reason": "ok",
        "intent_gate_status": "skipped",
        "intent_gate_reason": "not_applicable",
    }
    invalid = dict(valid)
    invalid["delivery_created_at"] = "not-a-timestamp"
    record_path.write_text(
        json.dumps(valid, ensure_ascii=False) + "\n" + json.dumps(invalid, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    records = module.load_observation_records(record_path)

    assert len(records) == 1
    assert records[0]["transport_source"] == "runtime_harness"


def test_extract_telegram_observation_records_normalizes_shape(tmp_path):
    module = _load_module(COMMON_SCRIPT, "runtime_mainline_observation_common")
    session_log = tmp_path / "telegram_dm_test.jsonl"
    entries = [
        {
            "event_id": "evt_ingress",
            "created_at": "2026-04-01T12:00:00",
            "kind": "telegram_ingress",
            "payload": {"text_preview": "还记得我吗", "session_key": "telegram:dm:test"},
        },
        {
            "event_id": "evt_runtime",
            "created_at": "2026-04-01T12:00:00.500000",
            "kind": "runtime_v2_result",
            "payload": {"status": "chat", "reply_text": "raw reply"},
        },
        {
            "event_id": "evt_delivery",
            "created_at": "2026-04-01T12:00:01",
            "kind": "telegram_delivery",
            "payload": {
                "text": "我在听。",
                "reply_authority": "host_degraded_fallback",
                "reply_origin": "chat_mainline",
                "delivery_kind": "chat",
                "output_check_reason": "intent_gate_fallback_applied",
                "intent_gate_status": "violation",
                "intent_gate_reason": "would_block",
            },
        },
    ]
    session_log.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in entries) + "\n", encoding="utf-8")

    records = module.extract_telegram_observation_records(session_log, limit=4)

    assert len(records) == 1
    record = records[0]
    assert record["transport_source"] == "telegram"
    assert record["observation_source"] == "direct_real"
    assert record["delivery_authority_source"] == "response_contract.output_check"
    assert record["reply_authority"] == "host_degraded_fallback"


def test_controlled_evidence_prefers_observation_log(tmp_path):
    common = _load_module(COMMON_SCRIPT, "runtime_mainline_observation_common")
    evidence = _load_module(EVIDENCE_SCRIPT, "run_mvp12_controlled_evidence")
    observation_log = tmp_path / "runtime_observations.jsonl"
    record = {
        "schema_version": "observation_record.v1",
        "observation_source": "direct_real",
        "transport_source": "runtime_harness",
        "source": "runtime_harness",
        "session_id": "session:test",
        "turn_id": "turn_001",
        "ingress_event_id": "ing_001",
        "ingress_created_at": "2026-04-01T12:00:00",
        "ingress_text": "继续说",
        "runtime_status": "chat",
        "runtime_reply_text": "raw",
        "delivery_event_id": "del_001",
        "delivery_created_at": "2026-04-01T12:00:01",
        "delivery_text": "继续展开一点。",
        "reply_authority": "model_chat",
        "reply_origin": "chat_mainline",
        "delivery_kind": "chat",
        "delivery_authority_source": "response_contract.output_check",
        "output_check_reason": "ok",
        "intent_gate_status": "skipped",
        "intent_gate_reason": "not_applicable",
    }
    common.append_observation_records(observation_log, [record])

    observations = evidence._extract_direct_real_observations(
        observation_log=observation_log,
        telegram_session_log=tmp_path / "missing.jsonl",
        limit=4,
    )

    assert len(observations) == 1
    assert observations[0]["transport_source"] == "runtime_harness"

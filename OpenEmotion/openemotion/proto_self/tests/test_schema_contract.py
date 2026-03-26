from openemotion.proto_self.schemas import (
    KernelEvent,
    kernel_event_from_payload,
    normalize_safety_context,
)


def test_normalize_safety_context_prefers_canonical_risk_level():
    safety_context = normalize_safety_context({"risk_level": "high", "risk": "low"})
    assert safety_context == {"risk_level": "high"}


def test_kernel_event_from_payload_absorbs_legacy_risk_alias():
    event = kernel_event_from_payload(
        {
            "event_id": "evt_schema_001",
            "safety_context": {"risk": "critical"},
        }
    )
    assert event.safety_context["risk_level"] == "critical"
    assert "risk" not in event.safety_context


def test_kernel_event_post_init_normalizes_direct_instantiation():
    event = KernelEvent(
        event_id="evt_schema_002",
        safety_context={"risk": "medium"},
    )
    assert event.to_dict()["safety_context"] == {"risk_level": "medium"}


def test_normalize_safety_context_absorbs_numeric_compat_value():
    safety_context = normalize_safety_context({"risk_level": 0.5})
    assert safety_context == {"risk_level": "high"}

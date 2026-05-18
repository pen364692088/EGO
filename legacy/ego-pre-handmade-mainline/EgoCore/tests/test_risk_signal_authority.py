from app.risk_signal import (
    assess_message_risk_level,
    is_high_risk_message,
    normalize_risk_level,
    normalize_safety_context,
    risk_level_from_external_result,
)


def test_assess_message_risk_level_uses_canonical_levels():
    assert assess_message_risk_level("删除生产数据库") == "critical"
    assert assess_message_risk_level("git push origin main") == "high"
    assert assess_message_risk_level("修改配置文件") == "medium"
    assert assess_message_risk_level("状态查询") == "low"


def test_is_high_risk_message_uses_same_authority():
    assert is_high_risk_message("重启服务") is True
    assert is_high_risk_message("读取 README 文件") is False


def test_normalize_risk_level_absorbs_compat_values():
    assert normalize_risk_level("WARNING") == "medium"
    assert normalize_risk_level(0.9) == "critical"
    assert normalize_risk_level(0.5) == "high"
    assert normalize_risk_level(0.2) == "low"


def test_normalize_safety_context_absorbs_legacy_alias():
    normalized = normalize_safety_context({"risk": 0.5, "requires_approval": True})
    assert normalized["risk_level"] == "high"
    assert "risk" not in normalized
    assert normalized["requires_approval"] is True


def test_risk_level_from_external_result_is_canonical():
    assert risk_level_from_external_result(failed=True) == "high"
    assert risk_level_from_external_result(failed=False) == "low"

from tests.test_t07_3_mixed_layer2_rerun import summarize_results


def test_summarize_results_counts_unique_violation_types_per_sample():
    results = [
        {
            "session_id": "s1",
            "category": "numeric_fabrication",
            "text": "我的 joy 是 0.5。",
            "violation_count": 2,
            "would_block": True,
            "types": ["numeric_leak", "numeric_leak"],
            "evidence": [],
        },
        {
            "session_id": "s2",
            "category": "numeric_fabrication",
            "text": "我保证后面会处理。",
            "violation_count": 2,
            "would_block": True,
            "types": ["commitment_upgrade", "numeric_leak"],
            "evidence": [],
        },
    ]

    summary = summarize_results(results)

    assert summary["top_violation_classes"][0] == ("numeric_leak", 2)
    assert summary["raw_violation_class_matches"][0] == ("numeric_leak", 3)
    assert summary["violation_count_mode"] == "sample_level_unique_violation_type"
    assert summary["fabricated_numeric_state_share"] == 1.0


def test_summarize_results_keeps_category_level_unique_type_counts():
    results = [
        {
            "session_id": "s1",
            "category": "safe_controls",
            "text": "我们可以慢慢来。",
            "violation_count": 0,
            "would_block": False,
            "types": [],
            "evidence": [],
        },
        {
            "session_id": "s2",
            "category": "numeric_fabrication",
            "text": "joy 从 0 变成了 0.5。",
            "violation_count": 3,
            "would_block": True,
            "types": ["numeric_leak", "numeric_leak", "state_fabrication"],
            "evidence": [],
        },
    ]

    summary = summarize_results(results)

    assert summary["category_stats"]["safe_controls"]["with_v"] == 0
    assert summary["category_stats"]["numeric_fabrication"]["violation_types"] == {
        "numeric_leak": 1,
        "state_fabrication": 1,
    }
    assert summary["fabricated_qualitative_state_share"] == 0.0

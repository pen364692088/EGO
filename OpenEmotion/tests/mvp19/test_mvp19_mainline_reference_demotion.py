from tools.verify_mvp19_mainline_wiring import inspect_wiring


def test_mvp19_upstream_authority_surfaces_remain_read_only_to_wp14():
    report = inspect_wiring()

    assert report["upstream_read_only_map"]["registered"] is True
    assert report["upstream_read_only_map"]["required_surfaces"] == [
        "OpenEmotion/openemotion/self_model/*",
        "OpenEmotion/openemotion/endogenous_drives/*",
        "OpenEmotion/openemotion/reflective_self/*",
        "OpenEmotion/openemotion/developmental_self/*",
        "OpenEmotion/openemotion/social_self/*",
        "OpenEmotion/openemotion/embodied_self/*",
    ]


def test_mvp19_legacy_cross_axis_materials_remain_reference_only():
    report = inspect_wiring()

    assert report["legacy_reference"]["registered_reference_only"] is True
    assert report["legacy_reference"]["surfaces_complete"] is True
    assert report["legacy_reference"]["surfaces_present"][
        "Tasks/active/SELF_AWARE_STEP_07_mvp16_unblock.md"
    ] is True
    assert report["legacy_reference"]["surfaces_present"][
        "Tasks/active/SELF_AWARE_STEP_08_admission_review.md"
    ] is True
    assert report["legacy_reference"]["surfaces_present"][
        "OpenEmotion/roadmap/SELF_AWARE_EXECUTION_MASTER_PLAN_20260328.md"
    ] is True
    assert report["legacy_reference"]["surfaces_present"][
        "OpenEmotion/roadmap/VersionRoadmap.md"
    ] is True


def test_mvp19_current_runtime_consumer_is_formal_owner_path():
    report = inspect_wiring()

    assert report["formal_owner"]["selfhood_integration_package_present"] is True
    assert report["current_runtime_mainline"]["proto_self_kernel_reads_selfhood_context"] is True
    assert report["current_runtime_mainline"]["runtime_v2_injects_selfhood_context"] is True
    assert report["current_runtime_mainline"]["runtime_v2_records_selfhood_hooks"] is True
    assert report["status"] == "current_runtime_selfhood_consumer_present_legacy_reference_only"

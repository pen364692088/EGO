from tools.verify_mvp16_mainline_wiring import inspect_wiring


def test_mvp16_legacy_developmental_surfaces_remain_reference_only():
    report = inspect_wiring()

    assert report["legacy_reference"]["registered_reference_only"] is True
    assert report["legacy_reference"]["surfaces_present"][
        "OpenEmotion/emotiond/developmental/__init__.py"
    ] is True
    assert report["legacy_reference"]["surfaces_present"][
        "OpenEmotion/emotiond/developmental/manager.py"
    ] is True
    assert report["legacy_reference"]["surfaces_present"][
        "OpenEmotion/tools/mvp16_daily_check.py"
    ] is True
    assert report["legacy_reference"]["surfaces_present"][
        "OpenEmotion/tools/mvp16_real_trajectory_sync.py"
    ] is True


def test_mvp16_current_runtime_consumer_is_formal_owner_path():
    report = inspect_wiring()

    assert report["formal_owner"]["developmental_self_package_present"] is True
    assert report["current_runtime_mainline"]["proto_self_kernel_reads_developmental_context"] is True
    assert report["current_runtime_mainline"]["runtime_v2_injects_developmental_context"] is True
    assert report["current_runtime_mainline"]["runtime_v2_records_developmental_hooks"] is True
    assert report["status"] == "current_runtime_developmental_consumer_present_legacy_reference_only"

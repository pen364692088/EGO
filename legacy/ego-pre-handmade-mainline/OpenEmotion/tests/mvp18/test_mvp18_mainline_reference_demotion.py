from tools.verify_mvp18_mainline_wiring import inspect_wiring


def test_mvp18_legacy_embodied_surfaces_remain_reference_or_input_only():
    report = inspect_wiring()

    assert report["legacy_reference"]["registered_reference_only"] is True
    assert report["legacy_reference"]["surfaces_complete"] is True
    assert report["legacy_reference"]["surfaces_present"][
        "OpenEmotion/roadmap/VersionRoadmap.md"
    ] is True
    assert report["legacy_reference"]["surfaces_present"][
        "OpenEmotion/emotiond/consequence.py"
    ] is True
    assert report["legacy_reference"]["surfaces_present"][
        "OpenEmotion/emotiond/science/interventions.py"
    ] is True
    assert report["legacy_reference"]["surfaces_present"][
        "OpenEmotion/emotiond/science/science_mode.py"
    ] is True


def test_mvp18_current_runtime_consumer_is_formal_owner_path():
    report = inspect_wiring()

    assert report["formal_owner"]["embodied_self_package_present"] is True
    assert report["current_runtime_mainline"]["proto_self_kernel_reads_embodied_context"] is True
    assert report["current_runtime_mainline"]["runtime_v2_injects_embodied_context"] is True
    assert report["current_runtime_mainline"]["runtime_v2_records_embodied_hooks"] is True
    assert report["status"] == "current_runtime_embodied_consumer_present_legacy_reference_only"

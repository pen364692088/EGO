from tools.verify_mvp17_mainline_wiring import inspect_wiring


def test_mvp17_legacy_social_surfaces_remain_reference_or_input_only():
    report = inspect_wiring()

    assert report["legacy_reference"]["registered_reference_only"] is True
    assert report["legacy_reference"]["surfaces_complete"] is True
    assert report["legacy_reference"]["surfaces_present"][
        "EgoCore/app/response/relationship_context.py"
    ] is True
    assert report["legacy_reference"]["surfaces_present"][
        "EgoCore/app/runtime/repair_context_manager.py"
    ] is True
    assert report["legacy_reference"]["surfaces_present"][
        "OpenEmotion/emotiond/other_minds.py"
    ] is True
    assert report["legacy_reference"]["surfaces_present"][
        "OpenEmotion/emotiond/persistence.py"
    ] is True


def test_mvp17_current_runtime_consumer_is_formal_owner_path():
    report = inspect_wiring()

    assert report["formal_owner"]["social_self_package_present"] is True
    assert report["current_runtime_mainline"]["proto_self_kernel_reads_social_context"] is True
    assert report["current_runtime_mainline"]["runtime_v2_injects_social_context"] is True
    assert report["current_runtime_mainline"]["runtime_v2_records_social_hooks"] is True
    assert report["status"] == "current_runtime_social_consumer_present_legacy_reference_only"

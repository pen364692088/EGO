from tools.verify_mvp15_mainline_wiring import inspect_wiring


def test_mvp15_static_verifier_reports_bounded_mainline_consumer():
    report = inspect_wiring()

    assert report["formal_owner"]["reflective_self_package_present"] is True
    assert report["current_runtime_mainline"]["proto_self_kernel_reads_reflective_context"] is True
    assert report["current_runtime_mainline"]["runtime_v2_injects_reflective_context"] is True
    assert report["current_runtime_mainline"]["runtime_v2_records_reflection_hooks"] is True
    assert report["current_runtime_mainline"]["bounded_consumer_present"] is True
    assert report["legacy_reference"]["registered_reference_only"] is True
    assert report["status"] == "current_runtime_reflective_consumer_present_legacy_reference_only"

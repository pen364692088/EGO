from tools.verify_mvp20_mainline_wiring import inspect_wiring


def test_mvp20_host_proactive_substrate_remains_host_substrate_only():
    report = inspect_wiring()

    assert report["host_substrate_reference"]["registered_host_substrate_only"] is True
    assert report["host_substrate_reference"]["surfaces_complete"] is True
    assert report["host_substrate_reference"]["surfaces_present"][
        "EgoCore/app/runtime_v2/initiative_arbiter.py"
    ] is True
    assert report["host_substrate_reference"]["surfaces_present"][
        "EgoCore/app/runtime_v2/proactive_telegram_cycle.py"
    ] is True
    assert report["host_substrate_reference"]["surfaces_present"][
        "EgoCore/tools/run_mvp12_host_governed_proactive_telegram_cycle.py"
    ] is True


def test_mvp20_roadmap_materials_remain_reference_only():
    report = inspect_wiring()

    assert report["roadmap_reference"]["registered_reference_only"] is True
    assert report["roadmap_reference"]["surfaces_complete"] is True
    assert report["roadmap_reference"]["surfaces_present"][
        "OpenEmotion/roadmap/SELF_AWARE_AI_ROADMAP.md"
    ] is True
    assert report["roadmap_reference"]["surfaces_present"][
        "OpenEmotion/roadmap/VersionRoadmap.md"
    ] is True


def test_mvp20_current_runtime_consumer_is_formal_owner_path():
    report = inspect_wiring()

    assert report["formal_owner"]["initiative_self_package_present"] is True
    assert report["current_runtime_mainline"]["proto_self_kernel_reads_initiative_context"] is True
    assert report["current_runtime_mainline"]["runtime_v2_injects_initiative_context"] is True
    assert report["current_runtime_mainline"]["runtime_v2_records_initiative_hooks"] is True
    assert report["status"] == "current_runtime_initiative_consumer_present_legacy_reference_only"

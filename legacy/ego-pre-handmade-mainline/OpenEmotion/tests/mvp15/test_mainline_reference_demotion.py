from pathlib import Path

from tools.verify_mvp15_mainline_wiring import inspect_wiring


REPO_ROOT = Path(__file__).resolve().parents[3]


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_mvp15_legacy_reflection_surfaces_remain_reference_only():
    report = inspect_wiring()

    assert report["legacy_reference"]["registered_reference_only"] is True
    assert report["legacy_reference"]["surfaces_present"][
        "OpenEmotion/emotiond/reflection_engine/engine.py"
    ] is True
    assert report["legacy_reference"]["surfaces_present"][
        "OpenEmotion/emotiond/reflection_adapter.py"
    ] is True
    assert report["legacy_reference"]["surfaces_present"][
        "OpenEmotion/emotiond/reflection_shadow.py"
    ] is True
    assert report["legacy_reference"]["surfaces_present"][
        "OpenEmotion/emotiond/self_counterfactual.py"
    ] is True


def test_mvp15_archive_report_tools_are_marked_historical_and_archive_only():
    verify_source = _read("OpenEmotion/tools/verify_mvp15_mainline_wiring.py")
    funnel_check_source = _read("OpenEmotion/tools/mvp15_funnel_check.py")
    funnel_tracker_source = _read("OpenEmotion/tools/mvp15_funnel_tracker.py")
    causal_experiments_source = _read("OpenEmotion/tools/causal_intervention_experiments.py")
    core_source = _read("OpenEmotion/emotiond/core.py")
    daily_validation_source = _read("OpenEmotion/tools/mvp15_daily_validation.sh")
    cron_source = _read("OpenEmotion/tools/setup_mvp15_cron.sh")
    caller_matrix = _read("docs/codex/tasks/repo-authority-cleanup/CALLER_MATRIX.md")
    file_fate = _read("docs/codex/tasks/repo-authority-cleanup/FILE_FATE_LEDGER.md")

    assert "Historical snapshot verifier for MVP15 reflective wiring" in verify_source
    assert "surface_role: archive/reference-only historical snapshot" in verify_source
    assert "Historical archive/reference-only check for the MVP15 reflection trigger funnel" in funnel_check_source
    assert "Historical archive/reference-only tracker for MVP15 reflection funnel metrics" in funnel_tracker_source
    assert "emotiond.reflection_shadow" not in funnel_check_source
    assert "emotiond.reflection_shadow" not in funnel_tracker_source
    assert "Historical archive/reference-only wrapper for funnel tracking and integrity check" in daily_validation_source
    assert "Historical archive/reference-only cron wrapper" in cron_source
    assert "Archive/reference-only historical experiment" in causal_experiments_source
    assert "Archive/reference-only reflection probe" in causal_experiments_source
    assert "from emotiond.reflection_adapter import get_reflection_adapter" not in core_source
    assert "from emotiond.reflection_shadow import get_reflection_shadow" not in core_source
    assert "from openemotion.reflective_self import ReflectiveSelfState, ReflectiveSelfStore" in core_source
    assert "OpenEmotion/tools/verify_mvp15_mainline_wiring.py" in caller_matrix
    assert "OpenEmotion/tools/mvp15_funnel_check.py" in caller_matrix
    assert "OpenEmotion/tools/mvp15_funnel_tracker.py" in caller_matrix
    assert "OpenEmotion/tools/mvp15_daily_validation.sh" in caller_matrix
    assert "OpenEmotion/tools/setup_mvp15_cron.sh" in caller_matrix
    assert "OpenEmotion/tools/causal_intervention_experiments.py" in caller_matrix
    assert "OpenEmotion/tools/verify_mvp15_mainline_wiring.py" in file_fate
    assert "OpenEmotion/tools/mvp15_funnel_check.py" in file_fate
    assert "OpenEmotion/tools/mvp15_funnel_tracker.py" in file_fate
    assert "OpenEmotion/tools/mvp15_daily_validation.sh" in file_fate
    assert "OpenEmotion/tools/setup_mvp15_cron.sh" in file_fate
    assert "OpenEmotion/tools/causal_intervention_experiments.py" in file_fate

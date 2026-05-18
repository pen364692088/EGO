from pathlib import Path

from emotiond.drives import DriveManager as LegacyDriveManager
from emotiond.drives import get_drive_manager as get_legacy_drive_manager
from emotiond.drives import reset_drive_manager as reset_legacy_drive_manager
from emotiond.drives.manager import DriveManager as LegacyManagerModuleDriveManager
from openemotion.endogenous_drives import DriveManager as FormalDriveManager
from openemotion.endogenous_drives import get_drive_manager as get_formal_drive_manager
from openemotion.endogenous_drives import reset_drive_manager as reset_formal_drive_manager

ROOT = Path(__file__).resolve().parents[3]


def test_legacy_drive_manager_reexports_formal_owner_class():
    assert LegacyDriveManager is FormalDriveManager
    assert LegacyManagerModuleDriveManager is FormalDriveManager


def test_legacy_and_formal_manager_share_singleton():
    reset_legacy_drive_manager()
    reset_formal_drive_manager()
    assert get_legacy_drive_manager() is get_formal_drive_manager()


def test_legacy_wrapper_mutations_hit_formal_owner_state():
    reset_legacy_drive_manager()
    reset_formal_drive_manager()
    legacy = get_legacy_drive_manager()
    formal = get_formal_drive_manager()

    legacy.accumulate(formal.state.active_drives["repair"].drive_type, 0.1, "legacy_wrapper")

    assert formal.state.active_drives["repair"].intensity > 0.15


def test_drive_action_bias_logic_is_single_sourced_in_formal_owner():
    core_text = (ROOT / "OpenEmotion" / "emotiond" / "core.py").read_text(encoding="utf-8")
    adapter_text = (ROOT / "OpenEmotion" / "emotiond" / "drive_adapter.py").read_text(encoding="utf-8")
    helper_text = (
        ROOT / "OpenEmotion" / "openemotion" / "endogenous_drives" / "action_bias.py"
    ).read_text(encoding="utf-8")

    assert "_FORMAL_OWNER_ACTION_WEIGHTS" not in core_text
    assert "ACTION_DRIVE_WEIGHTS =" not in adapter_text
    assert "compute_action_bias_from_priority_snapshot" in core_text
    assert "compute_action_bias_from_priority_snapshot" in adapter_text
    assert "ACTION_DRIVE_WEIGHTS" in helper_text

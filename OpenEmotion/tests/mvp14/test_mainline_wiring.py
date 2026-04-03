from emotiond.drives import DriveManager as LegacyDriveManager
from emotiond.drives import get_drive_manager as get_legacy_drive_manager
from emotiond.drives import reset_drive_manager as reset_legacy_drive_manager
from openemotion.endogenous_drives import DriveManager as FormalDriveManager
from openemotion.endogenous_drives import get_drive_manager as get_formal_drive_manager
from openemotion.endogenous_drives import reset_drive_manager as reset_formal_drive_manager


def test_legacy_drive_manager_reexports_formal_owner_class():
    assert LegacyDriveManager is FormalDriveManager


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

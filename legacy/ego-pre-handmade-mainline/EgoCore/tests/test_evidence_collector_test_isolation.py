import app.openemotion_hooks.native_hooks as native_hooks_module
import app.telegram_bot as telegram_bot_module


def test_repo_real_telegram_collector_disabled_by_default_under_pytest():
    assert telegram_bot_module._EVIDENCE_COLLECTOR_AVAILABLE is False
    assert native_hooks_module._EVIDENCE_COLLECTOR_AVAILABLE is False

from __future__ import annotations

import pytest

import app.openemotion_hooks.native_hooks as native_hooks_module
import app.telegram_bot as telegram_bot_module
import app.telegram_evidence_collector as telegram_evidence_collector_module


@pytest.fixture(autouse=True)
def _disable_repo_real_telegram_evidence_by_default(monkeypatch):
    """Keep dummy Telegram tests from polluting the canonical real_telegram artifacts."""
    monkeypatch.setattr(telegram_bot_module, "_EVIDENCE_COLLECTOR_AVAILABLE", False, raising=False)
    monkeypatch.setattr(native_hooks_module, "_EVIDENCE_COLLECTOR_AVAILABLE", False, raising=False)
    telegram_evidence_collector_module._collector = None

from __future__ import annotations

from pathlib import Path

import app.dashboard.live_api_client as module
from app.dashboard.live_api_client import DashboardLiveApiClient, DashboardLiveApiTransportError


def test_dashboard_live_api_client_prefers_python_transport(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str, str, object]] = []
    windows_curl = tmp_path / "curl.exe"
    windows_curl.write_text("", encoding="utf-8")

    def fake_python(method: str, url: str, *, payload=None, timeout: float = 15.0):
        calls.append(("python", method, url, payload))
        return {"ok": True, "url": url}

    def fake_curl(method: str, url: str, *, payload=None, timeout: float = 15.0, windows_curl_path: Path):
        calls.append(("windows_curl", method, url, payload))
        return {"ok": True, "url": url}

    monkeypatch.setattr(module, "_request_json_python", fake_python)
    monkeypatch.setattr(module, "_request_json_windows_curl", fake_curl)

    client = DashboardLiveApiClient(base_url="http://127.0.0.1:8787", windows_curl_path=windows_curl)
    response = client.create_or_select_session(name="codex-stage1-test")

    assert response.transport == "python"
    assert response.payload["ok"] is True
    assert calls == [
        ("python", "POST", "http://127.0.0.1:8787/api/dashboard/chat/sessions", {"name": "codex-stage1-test", "session_id": None})
    ]


def test_dashboard_live_api_client_falls_back_to_windows_curl_for_local_get_and_post(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str, str, object]] = []
    windows_curl = tmp_path / "curl.exe"
    windows_curl.write_text("", encoding="utf-8")

    def fake_python(method: str, url: str, *, payload=None, timeout: float = 15.0):
        calls.append(("python", method, url, payload))
        raise DashboardLiveApiTransportError("connection refused", transport="python")

    def fake_curl(method: str, url: str, *, payload=None, timeout: float = 15.0, windows_curl_path: Path):
        calls.append(("windows_curl", method, url, payload))
        return {"transport": "windows_curl", "url": url}

    monkeypatch.setattr(module, "_request_json_python", fake_python)
    monkeypatch.setattr(module, "_request_json_windows_curl", fake_curl)

    client = DashboardLiveApiClient(base_url="http://127.0.0.1:8787", windows_curl_path=windows_curl)
    get_response = client.list_sessions()
    post_response = client.send_message("dashboard:test:codex", "你好啊")

    assert get_response.transport == "windows_curl"
    assert post_response.transport == "windows_curl"
    assert ("windows_curl", "GET", "http://127.0.0.1:8787/api/dashboard/chat/sessions", None) in calls
    assert (
        "windows_curl",
        "POST",
        "http://127.0.0.1:8787/api/dashboard/chat/sessions/dashboard%3Atest%3Acodex/messages",
        {"text": "你好啊"},
    ) in calls

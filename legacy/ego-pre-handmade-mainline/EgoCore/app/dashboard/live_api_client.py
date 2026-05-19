from __future__ import annotations

import json
import subprocess
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError


WINDOWS_CURL = Path("/mnt/c/Windows/System32/curl.exe")
_HTTP_STATUS_MARKER = "__CODEX_HTTP_STATUS__:"
_LOCAL_HOSTS = {"127.0.0.1", "localhost"}


class DashboardLiveApiClientError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        error_code: str = "dashboard_live_api_error",
        status_code: int | None = None,
        transport: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code
        self.transport = transport


class DashboardLiveApiTransportError(DashboardLiveApiClientError):
    def __init__(self, message: str, *, transport: str | None = None) -> None:
        super().__init__(
            message,
            error_code="transport_error",
            status_code=None,
            transport=transport,
        )


@dataclass(frozen=True)
class DashboardLiveApiResponse:
    payload: dict[str, Any]
    transport: str


def _decode_json_body(body_text: str, *, transport: str) -> dict[str, Any]:
    try:
        payload = json.loads(body_text or "{}")
    except json.JSONDecodeError as exc:
        raise DashboardLiveApiClientError(
            f"dashboard API returned non-JSON payload via {transport}: {exc}",
            error_code="invalid_json_response",
            transport=transport,
        ) from exc
    if not isinstance(payload, dict):
        raise DashboardLiveApiClientError(
            f"dashboard API returned non-object JSON via {transport}",
            error_code="invalid_json_response",
            transport=transport,
        )
    return payload


def _error_from_http_response(status_code: int, body_text: str, *, transport: str) -> DashboardLiveApiClientError:
    payload: dict[str, Any] = {}
    if body_text.strip():
        try:
            decoded = json.loads(body_text)
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, dict):
            payload = decoded
    error_code = str(payload.get("error") or "dashboard_live_api_http_error").strip() or "dashboard_live_api_http_error"
    message = str(payload.get("message") or "").strip() or f"dashboard API returned HTTP {status_code}"
    return DashboardLiveApiClientError(
        message,
        error_code=error_code,
        status_code=int(status_code),
        transport=transport,
    )


def _request_json_python(
    method: str,
    url: str,
    *,
    payload: Mapping[str, Any] | None = None,
    timeout: float = 15.0,
) -> dict[str, Any]:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"

    request = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body_text = response.read().decode("utf-8")
    except HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise _error_from_http_response(exc.code, body_text, transport="python") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise DashboardLiveApiTransportError(str(exc) or f"{type(exc).__name__}", transport="python") from exc

    return _decode_json_body(body_text, transport="python")


def _request_json_windows_curl(
    method: str,
    url: str,
    *,
    payload: Mapping[str, Any] | None = None,
    timeout: float = 15.0,
    windows_curl_path: Path = WINDOWS_CURL,
) -> dict[str, Any]:
    if not windows_curl_path.exists():
        raise DashboardLiveApiTransportError("windows curl unavailable", transport="windows_curl")

    command = [
        str(windows_curl_path),
        "-sS",
        "-X",
        method.upper(),
        "--max-time",
        str(max(1, int(timeout))),
        "-w",
        f"\n{_HTTP_STATUS_MARKER}%{{http_code}}",
        url,
    ]
    if payload is not None:
        command.extend(
            [
                "-H",
                "Content-Type: application/json; charset=utf-8",
                "--data-binary",
                json.dumps(payload, ensure_ascii=False),
            ]
        )

    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise DashboardLiveApiTransportError(
            (completed.stderr or completed.stdout or "windows curl failed").strip(),
            transport="windows_curl",
        )

    marker = f"\n{_HTTP_STATUS_MARKER}"
    if marker not in completed.stdout:
        raise DashboardLiveApiTransportError("windows curl output missing status marker", transport="windows_curl")
    body_text, raw_status = completed.stdout.rsplit(marker, 1)
    try:
        status_code = int(raw_status.strip())
    except ValueError as exc:
        raise DashboardLiveApiTransportError("windows curl returned invalid HTTP status", transport="windows_curl") from exc

    if status_code >= 400:
        raise _error_from_http_response(status_code, body_text, transport="windows_curl")
    return _decode_json_body(body_text, transport="windows_curl")


class DashboardLiveApiClient:
    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:8787",
        timeout: float = 15.0,
        windows_curl_path: Path = WINDOWS_CURL,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = float(timeout)
        self.windows_curl_path = windows_curl_path

    def _build_url(self, path: str, *, query: Mapping[str, Any] | None = None) -> str:
        normalized_path = path if path.startswith("/") else f"/{path}"
        url = f"{self.base_url}{normalized_path}"
        if query:
            encoded = urllib.parse.urlencode(
                {key: value for key, value in query.items() if value is not None},
                doseq=True,
            )
            if encoded:
                url = f"{url}?{encoded}"
        return url

    def _should_fallback(self, url: str) -> bool:
        parsed = urllib.parse.urlparse(url)
        return parsed.hostname in _LOCAL_HOSTS and self.windows_curl_path.exists()

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> DashboardLiveApiResponse:
        url = self._build_url(path, query=query)
        try:
            response_payload = _request_json_python(method, url, payload=payload, timeout=self.timeout)
            return DashboardLiveApiResponse(payload=response_payload, transport="python")
        except DashboardLiveApiTransportError as exc:
            if not self._should_fallback(url):
                raise exc
        response_payload = _request_json_windows_curl(
            method,
            url,
            payload=payload,
            timeout=self.timeout,
            windows_curl_path=self.windows_curl_path,
        )
        return DashboardLiveApiResponse(payload=response_payload, transport="windows_curl")

    def list_sessions(self) -> DashboardLiveApiResponse:
        return self._request("GET", "/api/dashboard/chat/sessions")

    def create_or_select_session(
        self,
        *,
        name: str | None = None,
        session_id: str | None = None,
    ) -> DashboardLiveApiResponse:
        return self._request(
            "POST",
            "/api/dashboard/chat/sessions",
            payload={"name": name, "session_id": session_id},
        )

    def send_message(self, session_id: str, text: str) -> DashboardLiveApiResponse:
        encoded_session_id = urllib.parse.quote(str(session_id), safe="")
        return self._request(
            "POST",
            f"/api/dashboard/chat/sessions/{encoded_session_id}/messages",
            payload={"text": text},
        )

    def get_session(
        self,
        session_id: str,
        *,
        after_revision: int | None = None,
        wait_timeout_ms: int | None = None,
    ) -> DashboardLiveApiResponse:
        encoded_session_id = urllib.parse.quote(str(session_id), safe="")
        return self._request(
            "GET",
            f"/api/dashboard/chat/sessions/{encoded_session_id}",
            query={
                "after_revision": after_revision,
                "wait_timeout_ms": wait_timeout_ms,
            },
        )


__all__ = [
    "DashboardLiveApiClient",
    "DashboardLiveApiClientError",
    "DashboardLiveApiResponse",
    "DashboardLiveApiTransportError",
]

from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from app.dashboard.index_builder import (
    AGENCY_ROLLUP_FILE,
    BUILD_META_FILE,
    CONTINUITY_FILE,
    DASHBOARD_DIR,
    FAILURES_FILE,
    FAILURES_ROLLUP_FILE,
    GAP_SUMMARY_FILE,
    GROWTH_FILE,
    GROWTH_ROLLUP_FILE,
    RUNS_FILE,
    RUNS_ROLLUP_FILE,
    build_dashboard_indexes,
    dashboard_source_last_modified,
    load_jsonl,
)

STATIC_DIR = Path(__file__).with_name("static")


def _asset_version() -> int:
    candidates = [
        STATIC_DIR / "dashboard.js",
        STATIC_DIR / "dashboard.css",
    ]
    return int(max(path.stat().st_mtime for path in candidates if path.exists()))


class DashboardDataStore:
    def __init__(
        self,
        dashboard_dir: Path = DASHBOARD_DIR,
        *,
        build_kwargs: Optional[Dict[str, Any]] = None,
    ):
        self.dashboard_dir = Path(dashboard_dir)
        self.build_kwargs = dict(build_kwargs or {})

    def _meta_path(self) -> Path:
        return self.dashboard_dir / BUILD_META_FILE

    def _source_last_modified(self) -> float:
        meta = self.load_build_meta()
        return float(meta.get("source_last_modified") or 0.0)

    def ensure_indexes(self) -> Dict[str, Any]:
        if not self._meta_path().exists():
            return build_dashboard_indexes(output_dir=self.dashboard_dir, **self.build_kwargs).to_dict()
        current = dashboard_source_last_modified(**self.build_kwargs)
        meta = self.load_build_meta()
        if current > float(meta.get("source_last_modified") or 0.0):
            return build_dashboard_indexes(output_dir=self.dashboard_dir, **self.build_kwargs).to_dict()
        return meta

    def load_build_meta(self) -> Dict[str, Any]:
        if not self._meta_path().exists():
            return {}
        return json.loads(self._meta_path().read_text(encoding="utf-8"))

    def load_runs(self) -> list[Dict[str, Any]]:
        return load_jsonl(self.dashboard_dir / RUNS_FILE)

    def load_runs_rollup(self) -> Dict[str, Any]:
        path = self.dashboard_dir / RUNS_ROLLUP_FILE
        if not path.exists():
            return {"records": self.load_runs(), "continuity": self.load_continuity()}
        return json.loads(path.read_text(encoding="utf-8"))

    def load_growth(self) -> list[Dict[str, Any]]:
        return load_jsonl(self.dashboard_dir / GROWTH_FILE)

    def load_growth_rollup(self) -> Dict[str, Any]:
        path = self.dashboard_dir / GROWTH_ROLLUP_FILE
        if not path.exists():
            records = self.load_growth()
            return {"records": records, "summary": {"total_records": len(records)}}
        return json.loads(path.read_text(encoding="utf-8"))

    def load_failures(self) -> list[Dict[str, Any]]:
        return load_jsonl(self.dashboard_dir / FAILURES_FILE)

    def load_failures_rollup(self) -> Dict[str, Any]:
        path = self.dashboard_dir / FAILURES_ROLLUP_FILE
        if not path.exists():
            records = self.load_failures()
            return {"records": records, "gap_summary": self.load_gap_summary()}
        return json.loads(path.read_text(encoding="utf-8"))

    def load_continuity(self) -> list[Dict[str, Any]]:
        return load_jsonl(self.dashboard_dir / CONTINUITY_FILE)

    def load_gap_summary(self) -> Dict[str, Any]:
        path = self.dashboard_dir / GAP_SUMMARY_FILE
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def load_agency_rollup(self) -> Dict[str, Any]:
        path = self.dashboard_dir / AGENCY_ROLLUP_FILE
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def load_agency_records(self) -> list[Dict[str, Any]]:
        return load_jsonl(self.dashboard_dir / "agency_runs.jsonl")

    def sample_detail(self, sample_id: str) -> Optional[Dict[str, Any]]:
        sample_dir = self.dashboard_dir.parent / "real_telegram" / sample_id
        if not sample_dir.exists():
            return None
        detail = {"sample_id": sample_id, "artifacts": {}, "artifact_refs": {}}
        for name in [
            "ledger.json",
            "raw_update.json",
            "normalized_event.json",
            "openemotion_result.json",
            "openemotion_trace.json",
            "response_plan.json",
            "outbox_record.json",
            "timeline.json",
            "tape.json",
            "replay.json",
            "summary.md",
            "sample.json",
        ]:
            path = sample_dir / name
            if not path.exists():
                continue
            detail["artifact_refs"][name] = str(path)
            if path.suffix == ".json":
                detail["artifacts"][name] = json.loads(path.read_text(encoding="utf-8"))
            else:
                detail["artifacts"][name] = path.read_text(encoding="utf-8")
        runs_rollup = self.load_runs_rollup()
        growth_rollup = self.load_growth_rollup()
        failures_rollup = self.load_failures_rollup()
        run_record = next((item for item in runs_rollup.get("records", []) if item.get("sample_id") == sample_id), None)
        growth_record = next((item for item in growth_rollup.get("records", []) if item.get("sample_id") == sample_id), None)
        agency_record = next((item for item in self.load_agency_records() if item.get("sample_id") == sample_id), None)
        failure_record = next((item for item in failures_rollup.get("records", []) if item.get("sample_id") == sample_id), None)
        chosen_semantic = (
            (agency_record or {}).get("semantic")
            or (growth_record or {}).get("semantic")
            or (run_record or {}).get("semantic")
            or (failure_record or {}).get("semantic")
        )
        detail["run_record"] = run_record
        detail["related_records"] = {
            "agency": agency_record,
            "growth": growth_record,
            "failure": failure_record,
        }
        detail["semantic_summary"] = chosen_semantic
        detail["translated_summary"] = {
            "headline_code": (chosen_semantic or {}).get("headline_code", "unknown"),
            "intent_code": (chosen_semantic or {}).get("intent_code", "unknown"),
            "host_posture_code": (chosen_semantic or {}).get("host_posture_code", "not_applicable"),
            "result_state_code": (chosen_semantic or {}).get("result_state_code", "not_executed"),
            "growth_motion_code": (chosen_semantic or {}).get("growth_motion_code", "unknown"),
            "evidence_state_code": (chosen_semantic or {}).get("evidence_state_code", "partial"),
            "why_codes": (chosen_semantic or {}).get("why_codes", []),
            "focus_goal": ((agency_record or {}).get("focus_goal") or (growth_record or {}).get("focus_goal")),
            "candidate_actions": (agency_record or {}).get("candidate_actions", []),
            "final_host_action": (agency_record or {}).get("final_host_action"),
            "exec_result_type": (agency_record or {}).get("exec_result_type"),
        }
        return detail


class DashboardRequestHandler(BaseHTTPRequestHandler):
    store: DashboardDataStore

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        self.store.ensure_indexes()
        parsed = urlparse(self.path)

        if parsed.path.startswith("/api/dashboard/"):
            self._handle_api(parsed)
            return

        if parsed.path.startswith("/static/"):
            self._serve_static(parsed.path.removeprefix("/static/"))
            return

        if parsed.path in {"/", "/runs", "/growth", "/failures", "/agency"} or parsed.path.startswith("/samples/"):
            self._serve_html_shell(parsed.path)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def _handle_api(self, parsed) -> None:
        query = parse_qs(parsed.query)
        if parsed.path == "/api/dashboard/health":
            self._send_json(
                {
                    "status": "ok",
                    "build_meta": self.store.load_build_meta(),
                    "gap_summary": self.store.load_gap_summary(),
                }
            )
            return

        if parsed.path == "/api/dashboard/runs":
            payload = self.store.load_runs_rollup()
            limit = int((query.get("limit") or ["200"])[0])
            payload["records"] = payload.get("records", [])[:limit]
            payload["recent_runs"] = payload.get("recent_runs", [])[: min(limit, 50)]
            self._send_json(payload)
            return

        if parsed.path == "/api/dashboard/growth":
            payload = self.store.load_growth_rollup()
            limit = int((query.get("limit") or ["200"])[0])
            payload["records"] = payload.get("records", [])[:limit]
            payload["recent_growth"] = payload.get("recent_growth", [])[: min(limit, 50)]
            self._send_json(payload)
            return

        if parsed.path == "/api/dashboard/failures":
            self._send_json(self.store.load_failures_rollup())
            return

        if parsed.path == "/api/dashboard/agency":
            self._send_json(self.store.load_agency_rollup())
            return

        if parsed.path.startswith("/api/dashboard/samples/"):
            sample_id = parsed.path.rsplit("/", 1)[-1]
            detail = self.store.sample_detail(sample_id)
            if detail is None:
                self.send_error(HTTPStatus.NOT_FOUND, "Unknown sample_id")
                return
            self._send_json(detail)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Unknown API route")

    def _send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, static_path: str) -> None:
        target = STATIC_DIR / static_path.lstrip("/")
        if not target.exists() or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Static asset not found")
            return
        mime_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        body = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_html_shell(self, path: str) -> None:
        view = "runs"
        sample_id = ""
        if path == "/":
            view = "runs"
        elif path in {"/runs", "/growth", "/failures", "/agency"}:
            view = path.removeprefix("/")
        elif path.startswith("/samples/"):
            view = "sample"
            sample_id = path.rsplit("/", 1)[-1]

        asset_version = _asset_version()
        html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OpenEmotion Growth Dashboard v1</title>
  <link rel="stylesheet" href="/static/dashboard.css?v={asset_version}">
</head>
<body data-view="{view}" data-sample-id="{sample_id}">
  <div class="background-grid"></div>
  <main class="shell">
    <header class="hero">
      <div>
        <p class="eyebrow" id="hero-eyebrow"></p>
        <h1 id="hero-title"></h1>
        <p class="hero-copy" id="hero-copy"></p>
      </div>
      <div class="hero-side">
        <nav class="nav">
          <a href="/runs" id="nav-runs"></a>
          <a href="/agency" id="nav-agency"></a>
          <a href="/growth" id="nav-growth"></a>
          <a href="/failures" id="nav-failures"></a>
        </nav>
        <div class="locale-switch" id="locale-switch">
          <button type="button" data-locale="zh">中文</button>
          <button type="button" data-locale="en">EN</button>
        </div>
      </div>
    </header>
    <section class="meta-bar" id="meta-bar"></section>
    <section class="content" id="app"></section>
  </main>
  <script src="/static/dashboard.js?v={asset_version}"></script>
</body>
</html>"""
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_dashboard_server(
    *,
    host: str = "127.0.0.1",
    port: int = 8787,
    dashboard_dir: Path = DASHBOARD_DIR,
    build_kwargs: Optional[Dict[str, Any]] = None,
) -> None:
    store = DashboardDataStore(dashboard_dir=dashboard_dir, build_kwargs=build_kwargs)
    DashboardRequestHandler.store = store
    store.ensure_indexes()
    server = ThreadingHTTPServer((host, port), DashboardRequestHandler)
    print(f"Growth Dashboard v1 listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

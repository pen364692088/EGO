#!/usr/bin/env python3
"""Fetch recent trend_entry.json files from GitHub workflow artifacts."""

from __future__ import annotations

import argparse
import io
import json
import os
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional


def _api_get(url: str, token: str) -> Dict[str, Any]:
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _download_bytes(url: str, token: str) -> bytes:
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def _extract_trend_entry(blob: bytes) -> Optional[Dict[str, Any]]:
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        for name in zf.namelist():
            norm = name.replace("\\", "/")
            if norm.endswith("artifacts/mvp11/trends/trend_entry.json") or norm.endswith("trend_entry.json"):
                try:
                    return json.loads(zf.read(name).decode("utf-8"))
                except Exception:
                    return None
    return None


def fetch_entries(
    *,
    repo: str,
    workflow_file: str,
    branch: str,
    token: str,
    out_dir: Path,
    max_runs: int,
    max_entries: int,
) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)

    owner, name = repo.split("/", 1)
    wf = urllib.parse.quote(workflow_file, safe="")
    runs_url = f"https://api.github.com/repos/{owner}/{name}/actions/workflows/{wf}/runs?branch={urllib.parse.quote(branch)}&per_page={max_runs}"

    runs_payload = _api_get(runs_url, token)
    runs = runs_payload.get("workflow_runs") or []

    saved = 0
    checked = 0

    for run in runs:
        if saved >= max_entries:
            break
        run_id = run.get("id")
        if not run_id:
            continue
        checked += 1

        artifacts_url = f"https://api.github.com/repos/{owner}/{name}/actions/runs/{run_id}/artifacts?per_page=50"
        artifacts_payload = _api_get(artifacts_url, token)
        artifacts = artifacts_payload.get("artifacts") or []

        for art in artifacts:
            if saved >= max_entries:
                break
            if art.get("expired"):
                continue

            archive_url = art.get("archive_download_url")
            if not archive_url:
                continue

            try:
                blob = _download_bytes(archive_url, token)
                entry = _extract_trend_entry(blob)
            except Exception:
                continue

            if not entry:
                continue

            stamp = str(run.get("created_at", "")).replace(":", "-")
            out = out_dir / f"{stamp}_run{run_id}.json"
            out.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
            saved += 1
            break

    return {
        "checked_runs": checked,
        "saved_entries": saved,
        "out_dir": str(out_dir),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    ap.add_argument("--workflow-file", default="mvp11-cycle-gate-nightly.yml")
    ap.add_argument("--branch", default="feature-emotiond-mvp")
    ap.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    ap.add_argument("--out-dir", default="/tmp/mvp11_trend_entries")
    ap.add_argument("--max-runs", type=int, default=15)
    ap.add_argument("--max-entries", type=int, default=7)
    args = ap.parse_args()

    if not args.repo or "/" not in args.repo:
        print(json.dumps({"warning": "repo not set", "saved_entries": 0}, ensure_ascii=False, indent=2))
        return
    if not args.token:
        print(json.dumps({"warning": "token not set", "saved_entries": 0}, ensure_ascii=False, indent=2))
        return

    payload = fetch_entries(
        repo=args.repo,
        workflow_file=args.workflow_file,
        branch=args.branch,
        token=args.token,
        out_dir=Path(args.out_dir),
        max_runs=args.max_runs,
        max_entries=args.max_entries,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

# Proto-Self V2 Live Process Version Report

## Scope

- authority source:
  - [LIVE_TELEGRAM_PROCESS_VERSION.json](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/artifacts/proto_self_v2/LIVE_TELEGRAM_PROCESS_VERSION.json)
  - [PROTO_SELF_V2_EVIDENCE_REPORT_20260328.md](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/artifacts/proto_self_v2/PROTO_SELF_V2_EVIDENCE_REPORT_20260328.md)

## Current Live Telegram Process

- process kind:
  - `telegram`
- observed at:
  - `2026-03-28T20:02:01.493053`
- runtime pid:
  - `22136`
- launcher wrapper pid:
  - `48620`
- host:
  - `DESKTOP-SSKDNOU`
- python executable:
  - `C:\Python313\python.exe`
- cwd:
  - `D:\Project\AIProject\MyProject\Ego\EgoCore`

## Repo Version Binding

- git branch:
  - `main`
- git commit short:
  - `468d9a4`
- git commit sha:
  - `468d9a4ed5ce66aa498ec7226f9cb9eef2908b81`
- live report path:
  - [LIVE_TELEGRAM_PROCESS_VERSION.json](/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/artifacts/proto_self_v2/LIVE_TELEGRAM_PROCESS_VERSION.json)

## Decision

- result:
  - `live_telegram_process_version_bound`
- why this matters:
  - future real-channel verification no longer needs to guess which commit the running Telegram process loaded
  - the current live Telegram process has been restarted after the default-v2 mainline change landed

## Evidence Boundary

- this report proves:
  - the current live Telegram process version is repo-tracked
  - the current live Telegram process corresponds to commit `468d9a4`
- this report does not prove:
  - a new post-restart real-channel sample has already been captured
  - cross-day continuity has been reached
  - the working tree was globally clean at process start

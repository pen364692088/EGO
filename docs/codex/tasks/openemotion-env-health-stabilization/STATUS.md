# OpenEmotion Environment and Health Stabilization - STATUS

## Current milestone

- name: Milestone 2 - Remove manual health precondition from full verify
- owner: Codex
- state: completed

## Current state

- current_layer: implementation / verification
- main_chain_status: verifier now reaches real OpenEmotion execution surfaces; remaining failure is in collected OpenEmotion tests, not env bootstrap or health preconditions
- completion_class: conditionally_complete

## Completed work

- 已建立独立 long-run task slice：`docs/codex/tasks/openemotion-env-health-stabilization/`
- 已确认两个当前 blocker：
  - 当前仓库不存在 `OpenEmotion/venv` / `.venv`
  - `OpenEmotion testbot PR subset` 被 verifier 的 `/health` 预条件挡住
- `verify_repo.py` 现在会在 WSL 下用 Windows Python 自举 `OpenEmotion/.venv`
- verifier-managed OpenEmotion runtime 现在安装 `.[dev]`
- `OpenEmotion/pyproject.toml` 已补 `requests>=2.0.0`
- `OpenEmotion smoke` 已在 `fast` 模式真实通过
- `OpenEmotion testbot PR subset` 已在 `full` 模式真实通过

## Last validation results

- mode: post-fix fast + full
- result: slice goal reached; remaining failure moved to real OpenEmotion test collection
- summary:
  - `python3 scripts/codex/verify_repo.py --mode fast`:
    - `OpenEmotion simple typecheck`: success
    - `OpenEmotion smoke`: success
  - `python3 scripts/codex/verify_repo.py --mode full`:
    - `EgoCore pytest suite`: success
    - `OpenEmotion full typecheck`: success
    - `OpenEmotion testbot PR subset`: success
    - `OpenEmotion test suite`: failed with 16 real collection errors (`yaml`, `numpy`, `integrations`, `emotiond.drives` exports)
  - latest rerun confirmation:
    - `EgoCore pytest suite`: `745 passed, 1 warning`
    - `EgoCore Telegram mainline regression`: `69 passed, 1 warning`
    - `OpenEmotion testbot PR subset`: `3/3 scenarios passed`
    - verifier exit code: non-zero only because `OpenEmotion test suite` still exits `2`

## Decisions made

- 优先修 `verify_repo.py`，不在本 slice 内改 OpenEmotion 业务模块
- 采用 Windows-managed `OpenEmotion/.venv` 作为 verifier runtime，避免 WSL mounted-drive `venv/pip` I/O 卡顿
- 把 `testbot PR subset` 从错误的 `/health` 前置条件里解开；health proof 仍由 smoke 路径提供

## Open risks

- full verify 现在会稳定暴露 OpenEmotion pytest 的真实收集错误，后续需要单独 bugfix slice
- verifier 目前在 WSL 下依赖 `cmd.exe /c py -3` 能创建和维护 `OpenEmotion/.venv`

## Next step

- 单开 OpenEmotion test collection bugfix slice，修 16 个真实收集错误；不要回退当前环境/bootstrap 改动

## Commands run / evidence

- `python3 scripts/codex/new_task.py openemotion-env-health-stabilization --title "OpenEmotion Environment and Health Stabilization"`
- `python3 scripts/codex/verify_repo.py --mode fast`
- `python3 scripts/codex/verify_repo.py --mode full`
- `cmd.exe /c "cd /d D:\Project\AIProject\MyProject\Ego\OpenEmotion && .venv\Scripts\python.exe -m pip install --no-build-isolation -e .[dev]"`
- `/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/.venv/Scripts/python.exe -m pytest tests/ -q`
- `/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/.venv/Scripts/python.exe scripts/run_testbot_scenarios.py --subset pr --output artifacts/testbot/pr_summary.json`
- authority refs:
  - `scripts/codex/verify_repo.py`
  - `OpenEmotion/pyproject.toml`
  - `OpenEmotion/Makefile`
  - `OpenEmotion/scripts/run_daemon.py`
  - `OpenEmotion/scripts/eval_suite.py`

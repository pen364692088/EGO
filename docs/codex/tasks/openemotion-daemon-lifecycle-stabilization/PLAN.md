# OpenEmotion Daemon Lifecycle Stabilization - PLAN

## Task summary

这是一个实现 / 验证层的 bugfix slice。目标是只修 `test_daemon_lifecycle` 的三类直连问题：DB env 契约失配、Windows logging path 失效、以及 daemon stop 对 sqlite handle 的非合作式关闭。

## Milestones

### Milestone 1: Reproduce and repair daemon lifecycle root causes

- scope: 复现 `test_daemon_lifecycle`，定位并修复 daemon 起停相关的最小根因
- files / areas likely touched:
  - `OpenEmotion/emotiond/config.py`
  - `OpenEmotion/emotiond/db.py`
  - `OpenEmotion/emotiond/core.py`
  - `OpenEmotion/emotiond/daemon.py`
  - `OpenEmotion/tests/test_daemon_lifecycle.py`
- acceptance:
  - `OpenEmotion/tests/test_daemon_lifecycle.py` 全量通过
  - 不再出现 tempfile teardown `PermissionError`
  - `run_daemon()` 不再因 logging path 直接失败
- validation:
  - `/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/.venv/Scripts/python.exe -m pytest OpenEmotion/tests/test_daemon_lifecycle.py -q`
- rollback note: 若 cooperative shutdown 引入新 hang，回退 loop stop 逻辑，仅保留 logging/env/test 契约修复

### Milestone 2: Re-run verifier and classify remaining failures

- scope: 用 repo verifier 证明当前 slice 已收口，并把剩余失败面与本 slice 切开
- files / areas likely touched:
  - `docs/codex/tasks/openemotion-daemon-lifecycle-stabilization/*.md`
- acceptance:
  - `python3 scripts/codex/verify_repo.py --mode fast` 通过
  - 当前 slice 的结果与剩余失败面已在状态文档中分离
- validation:
  - `python3 scripts/codex/verify_repo.py --mode fast`
  - `python3 scripts/codex/verify_repo.py --mode full`
- rollback note: 若 verifier 暴露本 slice 引入的新回归，停在当前 slice 内继续修复，不跳到下一失败面

## Progress

- current_status: completed
- current_milestone: Milestone 2
- milestone_state: targeted repro、fast verify、full verify 已完成；本 slice 已与其余 OpenEmotion 失败面分离

## Decision log

- 2026-03-29: `test_daemon_lifecycle` 当前不是单一业务 bug，而是 production contract + test contract + shutdown timing 的组合失败，必须一起收口
- 2026-03-29: `EMOTIOND_DB_PATH` 是当前仓库正式 DB env 名称，但保留 `OPENEMOTION_DB_PATH` 作为 backward-compatible fallback 更稳
- 2026-03-29: daemon stop 改为 cooperative shutdown 优先，超时后才 cancel；不继续使用纯 `task.cancel()` 硬停

## Surprises / discoveries

- `test_daemon_lifecycle` 原本使用的是 `OPENEMOTION_DB_PATH`，和仓库主测试口径 `EMOTIOND_DB_PATH` 不一致
- `setup_logging()` 在 Windows 下写固定 `/tmp/emotiond.log` 会直接让 `run_daemon()` 起不来
- 仅关闭 tempfile 自身句柄还不够；核心问题是 daemon 对后台 loop 的硬 cancel 会把 sqlite 句柄释放打断

## Outcomes / retrospective

- 本轮已证明：
  - logging path、DB env 契约、以及 daemon stop 的硬 cancel 是当前失败面的真实组成部分
  - `OpenEmotion/tests/test_daemon_lifecycle.py` 已恢复到 `6 passed`
  - `python3 scripts/codex/verify_repo.py --mode fast` 已通过
  - `python3 scripts/codex/verify_repo.py --mode full` 的剩余失败面已转移到 `test_live_integration_fixture.py`、`test_outcome_capture_integration.py`、文档、token、self-report 等其他独立区域
- 还没证明：
  - OpenEmotion 全仓 full verify 已全绿
- 下一步最小闭环动作：
  - 单开下一条 pytest stabilization slice，优先处理 `tests/test_live_integration_fixture.py`

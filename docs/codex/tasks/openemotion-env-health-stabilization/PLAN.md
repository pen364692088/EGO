# OpenEmotion Environment and Health Stabilization - PLAN

## Task summary

这是一个 harness-level bugfix slice。目标层级在 `实现 / 验证`：修掉 `verify_repo.py` 对 OpenEmotion 的两个环境性 blocker，使 full verify 能命中真实 OpenEmotion 验证面，而不是卡在解释器和 `/health` 前置条件上。

## Milestones

### Milestone 1: Stabilize OpenEmotion runtime resolution

- scope: 让 verifier 在当前仓库环境下自动解析或 bootstrap 出可用的 OpenEmotion Python 运行时，不再依赖人工预建 `.venv`
- files / areas likely touched:
  - `scripts/codex/verify_repo.py`
  - `docs/codex/README.md`
  - `AGENTS.md`
- acceptance:
  - OpenEmotion runtime 解析规则能落到 repo-local `OpenEmotion/venv` 或其他可用解释器
  - 缺少 runtime modules 时，verifier 优先自举 runtime，而不是直接 `skipped`
- validation:
  - `python3 scripts/codex/verify_repo.py --mode fast`
- rollback note: 若 bootstrap 引入不稳定副作用，回退到“仅报告缺失解释器/依赖”的原始逻辑

### Milestone 2: Remove manual health precondition from full verify

- scope: 让 full verify 对 health-dependent OpenEmotion checks 做受控 daemon 托管，不再要求执行前手工起 daemon
- files / areas likely touched:
  - `scripts/codex/verify_repo.py`
  - `docs/codex/tasks/openemotion-env-health-stabilization/*.md`
- acceptance:
  - `OpenEmotion testbot PR subset` 不再因事先没有 `/health` 而 `skipped`
  - 若 verifier 临时拉起 daemon，结束后能受控退出
- validation:
  - `python3 scripts/codex/verify_repo.py --mode full`
- rollback note: 若 managed daemon 路径不稳定，回退到“明确 failed reason”而非默默 `skipped`

## Progress

- current_status: conditionally_complete
- current_milestone: Milestone 2
- milestone_state: environment slice closed; remaining full-verify failure is now real OpenEmotion test collection debt, not harness bootstrap or health preconditions

## Decision log

- 2026-03-29: 采用 `docs/codex/tasks/openemotion-env-health-stabilization/` 作为本次 slice 的唯一任务工作区；现有 `Tasks/active/*.md` 只作为 authority refs，不复制内容
- 2026-03-29: 优先修 harness 层的 OpenEmotion runtime resolution 与 managed health path，不改 OpenEmotion 业务代码
- 2026-03-29: WSL 下的 Linux-side `venv/pip` 在 `/mnt/d` 上出现不稳定 I/O 卡顿，因此 verifier 改为优先 bootstrap Windows Python 驱动的 `OpenEmotion/.venv`
- 2026-03-29: `OpenEmotion testbot PR subset` 不再绑定错误的 `/health` 前置条件；health proof 由 `OpenEmotion smoke` 承担，testbot subset 直接按脚本自身 contract 执行
- 2026-03-29: OpenEmotion verifier-managed runtime 改为安装 `.[dev]`，否则 full test suite 缺 `pytest_asyncio`

## Surprises / discoveries

- 当前仓库不存在 `OpenEmotion/venv` 或 `.venv`，所以 verifier 最终落到了 `/usr/bin/python3`
- `OpenEmotion testbot PR subset` 的当前 `skipped` 条件来自 verifier 的预检查，不是 `run_testbot_scenarios.py` 自身的 authority contract
- `OpenEmotion/pyproject.toml` 漏了 `requests`，导致 smoke/test tooling runtime 不完整；这是 bootstrap 后才显露出的真实环境缺口
- `OpenEmotion test suite` 当前仍有 16 个真实收集错误，包括缺失 `yaml` / `numpy`、`integrations` 导入，以及 `emotiond.drives` 导出不匹配；这已超出本 slice 的环境/bootstrap 范围

## Outcomes / retrospective

- 本轮已证明：
  - `fast` 已不再因 OpenEmotion runtime 依赖缺失而静默 `skipped`
  - `full` 中的 `OpenEmotion testbot PR subset` 已从 health precondition `skipped` 升为真实执行并成功
  - `full` 中 `OpenEmotion test suite` 现在暴露的是 16 个真实测试收集错误，不再是环境 bootstrap 问题
  - 最新 `full` rerun 已复证上述结论，未出现环境回退
- 还没证明：OpenEmotion 全量 pytest 是否可在当前 Windows-managed `.venv` 下收敛到通过
- 下一步最小闭环动作：单开一个 OpenEmotion test-collection bugfix slice，专门处理 `yaml/numpy/integrations` 缺失与 `emotiond.drives` 导出不匹配

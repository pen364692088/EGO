# Codex Harness Hardening - PLAN

## Task summary

当前任务是 Codex long-run harness 的一次真实 hardening slice，目标层级是实现 + 验证 + 收口。范围固定为：补稳定 lint、统一 OpenEmotion 验证环境、并把这 3 项工作本身按 long-run task 路径推进完。

## Milestones

### Milestone 1: Stable repo lint entry

- scope:
  - 新增稳定、轻量、repo-tracked 的 lint 入口
  - 接入 `scripts/codex/verify_repo.py`
- files / areas likely touched:
  - `scripts/codex/lint_repo.py`
  - `scripts/codex/verify_repo.py`
  - `AGENTS.md`
  - `docs/codex/README.md`
- acceptance:
  - `python3 scripts/codex/lint_repo.py` 可执行
  - `python3 scripts/codex/verify_repo.py --mode fast` 能探测并运行 lint
- validation:
  - `python3 scripts/codex/lint_repo.py`
  - `python3 scripts/codex/verify_repo.py --mode fast`
- rollback note:
  - 若 lint 入口引入过多噪声或误报，回退到更小的 control-surface 检查范围

### Milestone 2: Unified OpenEmotion verification environment

- scope:
  - 去掉 OpenEmotion smoke/typecheck 对 `.venv` 的硬编码依赖
  - 在 `verify_repo.py` 中统一解释器解析与 skipped reason
- files / areas likely touched:
  - `scripts/codex/verify_repo.py`
  - `OpenEmotion/test_smoke.py`
  - `docs/codex/README.md`
  - `AGENTS.md`
- acceptance:
  - OpenEmotion checks 使用同一解释器解析规则
  - 缺依赖时给出明确 `skipped reason`，而不是仅因 `.venv` 路径不存在失败
- validation:
  - `python3 scripts/codex/verify_repo.py --mode fast`
  - `python3 scripts/codex/verify_repo.py --mode full`
- rollback note:
  - 若统一解释器逻辑引入误判，回退到单一当前解释器策略，不恢复 `.venv` 硬编码

### Milestone 3: Real long-run loop replay

- scope:
  - 用本任务目录本身完成一次 `SPEC -> PLAN -> IMPLEMENT -> STATUS -> verify` 闭环
  - 记录真实使用摩擦、验证结果、风险和下一步
- files / areas likely touched:
  - `docs/codex/tasks/codex-harness-hardening/SPEC.md`
  - `docs/codex/tasks/codex-harness-hardening/PLAN.md`
  - `docs/codex/tasks/codex-harness-hardening/IMPLEMENT.md`
  - `docs/codex/tasks/codex-harness-hardening/STATUS.md`
- acceptance:
  - 任务目录被真实使用，而不是空模板
  - 至少完成一轮 fast 验证；closeout 时给出 full 验证结果或 blocker
- validation:
  - `python3 scripts/codex/new_task.py codex-harness-hardening --title "Codex Harness Hardening"`
  - `python3 scripts/codex/verify_repo.py --mode fast`
  - `python3 scripts/codex/verify_repo.py --mode full`
- rollback note:
  - 若 long-run task 目录字段设计不顺手，仅回退任务文档内容，不回退 harness 脚手架

## Progress

- current_status: conditional_complete
- current_milestone: Milestone 3
- milestone_state: closeout_complete_with_repo_test_blockers

## Decision log

- 2026-03-29: 这 3 项 hardening 工作本身作为一轮真实 long-run task 来跑，而不是另挑一个业务任务。原因是它能直接暴露 harness 的真实使用摩擦，且不扩大业务 scope。
- 2026-03-29: lint 入口采用无第三方依赖的轻量 Python 脚本，而不是引入 `ruff`/`mypy`。原因是当前仓库没有稳定 lint 工具链，先建立可持续入口比新造框架更重要。
- 2026-03-29: OpenEmotion 验证统一走 `OPENEMOTION_PYTHON -> .venv -> venv -> 当前解释器` 解析链。原因是当前仓库没有稳定虚拟环境路径，不能继续把 `.venv` 当硬前提。
- 2026-03-29: `EgoCore pytest suite` 在 harness 中注入 repo-local `PYTHONPATH=EgoCore:EgoCore/modules:OpenEmotion` 并加 `-s`。原因是 full verify 回放证明此前失败主要是 shell 环境与 pytest capture 摩擦，不是 harness 逻辑本身。

## Surprises / discoveries

- 当前环境下 `OpenEmotion/.venv/bin/python` 和 `OpenEmotion/venv/bin/python` 都不存在
- 现有 `verify_repo.py --mode fast` 会被 `verify_typecheck_simple.py` 的 `fastapi` 缺依赖直接打成 failed
- `new_task.py` 的重复执行行为符合预期：会 `kept existing`，不会误覆盖任务目录
- full verify 在环境摩擦清掉后，进一步暴露出当前仓库已有的 `EgoCore pytest` 失败面；这些失败与本次 harness 改动不直接相关

## Outcomes / retrospective

- 本轮已证明：
  - 稳定 lint 入口已经存在，并接入 `verify_repo.py`
  - OpenEmotion smoke/typecheck 不再依赖 `.venv` 硬编码
  - 本任务目录真实完成了一轮 `SPEC -> PLAN -> IMPLEMENT -> STATUS -> verify` 闭环
  - `verify_repo.py --mode fast` 在当前环境下可成功完成，并把缺依赖的 OpenEmotion 检查降为明确 `skipped`
  - `verify_repo.py --mode full` 不再因 `EgoCore` 的 shell/`PYTHONPATH`/capture 摩擦提前失真，而是能暴露真实 pytest failure surface
- 还没证明：
  - 当前仓库 full verify 绿色通过
  - 当前 Linux 环境具备运行 OpenEmotion runtime-backed smoke/typecheck 的依赖集
- 下一步最小闭环动作：
  - 单独开一个 bugfix slice，专门清理 `EgoCore pytest suite` 当前暴露出的 25 个现有失败用例，再回到 full verify 复跑

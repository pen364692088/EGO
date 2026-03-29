# OpenEmotion Environment and Health Stabilization - IMPLEMENT

## Source of truth

- `SPEC.md`
- `PLAN.md`
- `STATUS.md`
- `scripts/codex/verify_repo.py`
- `OpenEmotion/pyproject.toml`
- `OpenEmotion/Makefile`
- `OpenEmotion/scripts/run_daemon.py`
- `OpenEmotion/scripts/eval_suite.py`
- `OpenEmotion/scripts/run_testbot_scenarios.py`

## Execution rules

- 先读 `SPEC.md -> PLAN.md -> IMPLEMENT.md -> STATUS.md`
- 每次只推进 `STATUS.md` 中的 `Current milestone`
- 现有 `Tasks/active/*.md` 只作为 authority refs，不复制成第二真相源
- 不改 OpenEmotion 业务行为；只改 harness、runtime resolution、daemon 托管、文档记账

## Scope control

- 只改当前 milestone 需要的文件
- 不顺手推进下一个 milestone
- 保持 diff scoped
- 不把环境自举写成新的外部服务管理器
- 不把 health endpoint 的手工前置条件继续留在 full verify 主线里

## Validation strategy

- 每个 milestone 完成后运行：
  - `python3 scripts/codex/verify_repo.py --mode fast`
- 收口或高风险改动时运行：
  - `python3 scripts/codex/verify_repo.py --mode full`
- 代码级最低预检：
  - `python3 -m py_compile scripts/codex/verify_repo.py`
  - `git diff --check`

## Failure handling

- 验证失败先修复
- 修不动就记录 blocker、降级完成口径、停止推进
- 不跳过失败验证直接进入下一 milestone
- 若 bootstrap 失败，明确记录是依赖/环境 blocker，不把 `skipped` 伪装成通过
- 若 health 托管失败，给出端口占用或 daemon 启动失败的明确原因

## Stopping rule

- 当前 milestone 未验证通过，不进入下一 milestone
- 缺少外部凭据/审批、authority source 冲突、或 slice 无法闭环时停止
- 若 full verify 进入新的真实业务失败面，本 slice 到“环境 blocker 已清除”为止，不顺手修业务失败

## Final handoff checklist

- [ ] `PLAN.md` 已更新进度与决策
- [ ] `STATUS.md` 已更新验证结果与 next step
- [ ] commands run / evidence 已记录
- [ ] risks / rollback notes 已记录

# Codex Harness Hardening - IMPLEMENT

## Source of truth

- `SPEC.md`
- `PLAN.md`
- `STATUS.md`
- `AGENTS.md`
- `docs/codex/README.md`
- `OpenEmotion/Makefile`
- `OpenEmotion/pyproject.toml`

## Execution rules

- 先读 `SPEC.md -> PLAN.md -> IMPLEMENT.md -> STATUS.md`
- 每次只推进 `STATUS.md` 中的 `Current milestone`
- 现有 `Tasks/active/*.md` 只作为 authority refs，不复制成第二真相源
- 对 OpenEmotion 相关验证，优先统一解释器选择逻辑，而不是继续在各脚本里散落 `.venv` 假设

## Scope control

- 只改当前 milestone 需要的文件
- 不顺手推进下一个 milestone
- 保持 diff scoped
- 不为了补 lint 而引入新依赖或全面重构现有验证体系

## Validation strategy

- 每个 milestone 完成后运行：
  - `python3 scripts/codex/verify_repo.py --mode fast`
- 收口或高风险改动时运行：
  - `python3 scripts/codex/verify_repo.py --mode full`
- 关键脚本同时跑最小直接验证：
  - `python3 scripts/codex/lint_repo.py`
  - `python3 -m py_compile ...`

## Failure handling

- 验证失败先修复
- 修不动就记录 blocker、降级完成口径、停止推进
- 不跳过失败验证直接进入下一 milestone
- 如果 full 模式失败但失败点是现有仓库环境缺依赖或外部服务未就绪，记录为验证限制，不回滚当前 harness 逻辑

## Stopping rule

- 当前 milestone 未验证通过，不进入下一 milestone
- 缺少外部凭据/审批、authority source 冲突、或 slice 无法闭环时停止
- 当前 3 个 milestone 全部有验证结果并回写 `PLAN.md / STATUS.md` 后停止

## Final handoff checklist

- [ ] `PLAN.md` 已更新进度与决策
- [ ] `STATUS.md` 已更新验证结果与 next step
- [ ] commands run / evidence 已记录
- [ ] risks / rollback notes 已记录

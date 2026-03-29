# OpenEmotion Test Collection Stabilization - IMPLEMENT

## Source of truth

- `SPEC.md`
- `PLAN.md`
- `STATUS.md`
- `scripts/codex/verify_repo.py`
- `OpenEmotion/pyproject.toml`
- `OpenEmotion/emotiond/drives/__init__.py`
- `OpenEmotion/emotiond/drives.py`

## Execution rules

- 先读 `SPEC.md -> PLAN.md -> IMPLEMENT.md -> STATUS.md`
- 每次只推进 `STATUS.md` 中的 `Current milestone`
- 现有 `Tasks/active/*.md` 只作为 authority refs，不复制成第二真相源
- 优先修 import/collection 根因；不为这些错误做 workaround runner

## Scope control

- 只改当前 milestone 需要的文件
- 不顺手推进下一个 milestone
- 保持 diff scoped
- 不把本 slice 扩大成 OpenEmotion 全量 green 任务

## Validation strategy

- 每个 milestone 完成后运行：
  - `python3 scripts/codex/verify_repo.py --mode fast`
- 收口或高风险改动时运行：
  - `python3 scripts/codex/verify_repo.py --mode full`

## Failure handling

- 验证失败先修复
- 修不动就记录 blocker、降级完成口径、停止推进
- 不跳过失败验证直接进入下一 milestone
- 若兼容层影响 MVP14 package tests，优先回退兼容方式，不改现代主线 owner

## Stopping rule

- 当前 milestone 未验证通过，不进入下一 milestone
- 缺少外部凭据/审批、authority source 冲突、或 slice 无法闭环时停止
- 如果 full verify 不再出现这 16 个 collection/import 错误，本 slice 即可收口；剩余更深失败单开后续 slice

## Final handoff checklist

- [x] `PLAN.md` 已更新进度与决策
- [x] `STATUS.md` 已更新验证结果与 next step
- [x] commands run / evidence 已记录
- [x] risks / rollback notes 已记录

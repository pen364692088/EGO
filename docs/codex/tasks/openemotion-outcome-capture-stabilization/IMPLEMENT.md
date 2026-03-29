# OpenEmotion Outcome Capture Stabilization - IMPLEMENT

## Source of truth

- `SPEC.md`
- `PLAN.md`
- `STATUS.md`
- `OpenEmotion/tests/test_outcome_capture_integration.py`
- `OpenEmotion/tests/conftest.py`
- `OpenEmotion/tests/fixtures/mock_emotiond.py`
- `OpenEmotion/emotiond/api.py`
- `OpenEmotion/emotiond/security.py`

## Execution rules

- 先读 `SPEC.md -> PLAN.md -> IMPLEMENT.md -> STATUS.md`
- 每次只推进 `STATUS.md` 中的 `Current milestone`
- 现有 `Tasks/active/*.md` 只作为 authority refs，不复制成第二真相源

## Scope control

- 只改 outcome capture 集成测试的 fixture、测试文件和必要兼容桥
- 不放宽 `emotiond` 生产安全校验
- 不顺手修其他 OpenEmotion 失败面

## Validation strategy

- 每个 milestone 完成后运行：
  - `python3 scripts/codex/verify_repo.py --mode fast`
- 目标守门：
  - `/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/.venv/Scripts/python.exe -m pytest OpenEmotion/tests/test_outcome_capture_integration.py -q`
- 收口或高风险改动时运行：
  - `python3 scripts/codex/verify_repo.py --mode full`

## Failure handling

- 验证失败先修复
- 修不动就记录 blocker、降级完成口径、停止推进
- 不跳过失败验证直接进入下一 milestone

## Stopping rule

- 当前 milestone 未验证通过，不进入下一 milestone
- 缺少外部凭据/审批、authority source 冲突、或 slice 无法闭环时停止

## Final handoff checklist

- [x] `PLAN.md` 已更新进度与决策
- [x] `STATUS.md` 已更新验证结果与 next step
- [x] commands run / evidence 已记录
- [x] risks / rollback notes 已记录

# OpenEmotion Daemon Lifecycle Stabilization - IMPLEMENT

## Source of truth

- `SPEC.md`
- `PLAN.md`
- `STATUS.md`
- `OpenEmotion/tests/test_daemon_lifecycle.py`
- `OpenEmotion/emotiond/daemon.py`
- `OpenEmotion/emotiond/core.py`
- `OpenEmotion/emotiond/config.py`
- `OpenEmotion/emotiond/db.py`

## Execution rules

- 先读 `SPEC.md -> PLAN.md -> IMPLEMENT.md -> STATUS.md`
- 每次只推进 `STATUS.md` 中的 `Current milestone`
- 当前 slice 只修 daemon lifecycle，不扩到 live fixture / outcome capture

## Scope control

- 只动 daemon lifecycle 的直连代码和必要测试契约
- 不顺手清理其他 OpenEmotion pytest 失败面
- 保持 diff scoped，优先 root-cause fix

## Validation strategy

- 当前 slice 的决定性验证：
  - `/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/.venv/Scripts/python.exe -m pytest OpenEmotion/tests/test_daemon_lifecycle.py -q`
- 每个 milestone 完成后运行：
  - `python3 scripts/codex/verify_repo.py --mode fast`
- 收口时运行：
  - `python3 scripts/codex/verify_repo.py --mode full`

## Failure handling

- 如果 `test_daemon_lifecycle` 仍失败，优先继续收缩到 daemon stop / logging / DB env 三个直接点
- 如果 verifier 暴露新回归，先修当前 slice 引入的回归
- 不因仓库里其他现存失败面而误报本 slice 未完成

## Stopping rule

- `test_daemon_lifecycle` 未全绿，不进入下一失败面
- 当前 slice targeted 验证通过且 verifier 已补最小收口后停止

## Final handoff checklist

- [x] `PLAN.md` 已更新进度与决策
- [x] `STATUS.md` 已更新验证结果与 next step
- [x] commands run / evidence 已记录
- [x] risks / rollback notes 已记录

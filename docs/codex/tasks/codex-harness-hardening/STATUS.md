# Codex Harness Hardening - STATUS

## Current milestone

- name: Milestone 3 - Real long-run loop replay
- owner: Codex
- state: completed_with_blockers

## Current state

- current_layer: closure
- main_chain_status: harness hardening implemented; long-run loop replayed end-to-end
- completion_class: conditional_complete

## Completed work

- 已创建并真实使用 `docs/codex/tasks/codex-harness-hardening/`
- 已新增 `scripts/codex/lint_repo.py` 并接入 `scripts/codex/verify_repo.py`
- 已统一 OpenEmotion 解释器解析规则，去掉 `.venv` 硬依赖
- 已把 `EgoCore pytest suite` 的 repo-local `PYTHONPATH` 与 `-s` 稳定化接入 full verify
- 已验证 `new_task.py` 对已有任务目录不会误覆盖

## Last validation results

- mode: fast + full closeout
- result: mixed
- summary:
  - `python3 scripts/codex/lint_repo.py` 通过
  - `python3 scripts/codex/verify_repo.py --mode fast` 通过
  - `python3 scripts/codex/verify_repo.py --mode full` 失败，但失败面已收敛为现有 `EgoCore pytest suite` 的 25 个失败用例
  - full verify 同时显示：`720 passed, 25 failed, 1 warning`，且 `EgoCore Telegram mainline regression` 通过 `69 passed`
  - OpenEmotion runtime-backed checks在当前解释器缺 `fastapi` 时被明确降级为 `skipped`

## Decisions made

- 这次用本任务本身回放 long-run harness，而不是另挑业务任务
- lint 入口先走零依赖轻量脚本
- OpenEmotion 解释器解析统一收在 `verify_repo.py`，脚本内部尽量复用当前解释器或 `OPENEMOTION_PYTHON`
- `EgoCore pytest suite` 在 harness 中补 repo-local `PYTHONPATH` 和 `-s`

## Open risks

- 当前 Linux 解释器仍缺 `OpenEmotion` 的 `fastapi` 运行依赖，所以 OpenEmotion runtime-backed checks 只能 `skipped`
- 当前仓库的 `EgoCore pytest suite` 仍存在 25 个失败用例，full verify 暂不能宣称绿色通过

## Next step

- 以 `ego-bugfix-root-cause` 单独收一个 slice，清理 `EgoCore pytest suite` 当前暴露出的现有失败面

## Commands run / evidence

- `python3 scripts/codex/new_task.py codex-harness-hardening --title "Codex Harness Hardening"`
- `python3 scripts/codex/new_task.py codex-harness-hardening --title "Codex Harness Hardening"`（重复执行：kept existing）
- `python3 -m py_compile scripts/codex/lint_repo.py scripts/codex/verify_repo.py OpenEmotion/test_smoke.py`
- `python3 scripts/codex/lint_repo.py`
- `python3 scripts/codex/verify_repo.py --mode fast`
- `python3 scripts/codex/verify_repo.py --mode full`
- `PYTHONPATH=/mnt/d/Project/AIProject/MyProject/Ego/EgoCore:/mnt/d/Project/AIProject/MyProject/Ego/EgoCore/modules:/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion python3 -m pytest tests/ --collect-only -q -s`

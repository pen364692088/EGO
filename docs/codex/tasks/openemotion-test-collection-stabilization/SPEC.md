# OpenEmotion Test Collection Stabilization

## Goal

清掉 `python3 scripts/codex/verify_repo.py --mode full` 中 `OpenEmotion test suite` 当前暴露的 16 个真实 collection/import 错误，让 full verify 的失败面从“测试无法收集”收敛到更真实的行为或断言层。

## Non-goals

- 不在本任务内做 OpenEmotion 业务行为重构
- 不顺手推进新的 MVP 功能或清理历史测试风格
- 不在本任务内追求 OpenEmotion 全量 pytest 必然全绿；只处理当前 16 个 collection/import blocker

## Constraints

- 边界约束：只修 collection/import 层根因，不引入旁路主化
- 仓库/子仓约束：保持 `emotiond.drives` 当前 MVP14 owner 语义；若需要兼容层，只做最小兼容，不改主线 owner
- 环境约束：继续沿用 `OpenEmotion/.venv` verifier runtime，不回退到环境/bootstrap slice
- 发布约束：只提交本 slice touched files；用 `cmd.exe /c git commit` 与 `cmd.exe /c git push origin main`

## Acceptance criteria

- [x] `OpenEmotion test suite` 不再因 `yaml` / `numpy` / `integrations` 缺失或 `emotiond.drives` 兼容导出缺失而在 collection 阶段失败
- [x] 与这 16 个错误对应的最小回归验证通过
- [x] `python3 scripts/codex/verify_repo.py --mode full` 已复跑，且不再出现这 16 个 collection/import 错误

## Known risks / dependencies

- 风险：`emotiond.drives` 同时承载 MVP10 legacy tests 与 MVP14 package exports，兼容补丁如果过大容易破坏现代主线
- 依赖：`OpenEmotion/.venv` 已由上一 slice 自举完成；本 slice 依赖该 runtime 继续执行 full verify
- 外部 blocker：无外部服务 blocker；若 full verify 继续失败，应视为新的仓内真实失败面，而不是本 slice 外部阻塞

## Authority refs

- `PROJECT_MEMORY.md`
- `docs/AGENT_DEVELOPMENT_PLAYBOOK.md`
- `docs/codex/tasks/openemotion-env-health-stabilization/STATUS.md`
- `scripts/codex/verify_repo.py`
- `OpenEmotion/pyproject.toml`
- `OpenEmotion/emotiond/drives/__init__.py`
- `OpenEmotion/emotiond/drives.py`
- `OpenEmotion/tests/mvp10/test_drives_generation.py`
- `OpenEmotion/tests/mvp10/test_intervention_freeze_valence.py`
- `OpenEmotion/tests/mvp10/test_valence_policy_chain.py`
- `OpenEmotion/tests/test_user_affect.py`

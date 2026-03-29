# OpenEmotion Daemon Lifecycle Stabilization

## Goal

只修 `OpenEmotion/tests/test_daemon_lifecycle.py` 的 daemon 起停失败面，重点清理 Windows 下的 sqlite/tempfile handle teardown 错误，并保证 `run_daemon()` 在当前环境可正常启动。

## Non-goals

- 不处理 `tests/test_live_integration_fixture.py`
- 不处理 `tests/test_outcome_capture_integration.py`
- 不顺手清理其他 OpenEmotion 文档、reflection、self-report、token 失败面

## Constraints

- 边界约束：只动 daemon lifecycle、其直接依赖的 config/db/core，以及必要的测试契约
- 仓库/子仓约束：不引入新依赖，不重写 daemon 架构
- 环境约束：当前主验证口径以 Windows Python + repo 现有 `.venv` 为准
- 发布约束：先过 targeted repro，再跑至少 `python3 scripts/codex/verify_repo.py --mode fast`

## Acceptance criteria

- [x] `OpenEmotion/tests/test_daemon_lifecycle.py` 全量通过
- [x] 不再出现 Windows sqlite/tempfile teardown `PermissionError`
- [x] `run_daemon()` 在当前测试环境不再因 logging path 直接失败
- [x] 变更不扩到其他失败面；剩余问题已在状态文档中单独归类

## Known risks / dependencies

- 风险：daemon stop 可能依赖 cooperative shutdown；如果做错会影响其他后台 loop
- 风险：DB 路径 env alias 改动可能影响旧验证脚本
- 依赖：`emotiond.config.get_db_path()`、`emotiond.db.get_db_path()`、`emotiond.daemon.DaemonManager`
- 外部 blocker：无

## Authority refs

- `PROJECT_MEMORY.md`
- `docs/AGENT_DEVELOPMENT_PLAYBOOK.md`
- `OpenEmotion/tests/test_daemon_lifecycle.py`
- `OpenEmotion/emotiond/daemon.py`
- `OpenEmotion/emotiond/core.py`
- `OpenEmotion/emotiond/config.py`
- `OpenEmotion/emotiond/db.py`

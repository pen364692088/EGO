# OpenEmotion Outcome Capture Stabilization - PLAN

## Task summary

这是一个测试稳定化 bugfix slice。当前层级是实现/验证层，目标是在不放宽生产安全契约的前提下，修复 outcome capture 集成测试的隔离与兼容问题。

## Milestones

### Milestone 1: Reproduce and isolate root cause

- scope: 复现目标测试失败，区分 fixture、路径兼容和真实 API gate
- files / areas likely touched:
  - `OpenEmotion/tests/test_outcome_capture_integration.py`
  - `OpenEmotion/tests/conftest.py`
  - `OpenEmotion/tests/fixtures/mock_emotiond.py`
- acceptance:
  - 明确失败是否来自生产主链还是测试隔离层
- validation:
  - `/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/.venv/Scripts/python.exe -m pytest OpenEmotion/tests/test_outcome_capture_integration.py -q`
- rollback note:
  - 若判断错误，不进入生产逻辑修改

### Milestone 2: Apply minimal compatibility and isolation patch

- scope: 修复 Python fixture 启动、Node 路径转义、动态端口注入与兼容桥
- files / areas likely touched:
  - `OpenEmotion/tests/conftest.py`
  - `OpenEmotion/tests/fixtures/mock_emotiond.py`
  - `OpenEmotion/tests/test_outcome_capture_integration.py`
  - `OpenEmotion/integrations/openclaw/hooks/emotiond-bridge/outcomeCapture.js`
- acceptance:
  - 目标测试从红转绿
  - 生产 `forbidden_event` contract 不变
- validation:
  - `/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/.venv/Scripts/python.exe -m pytest OpenEmotion/tests/test_outcome_capture_integration.py -q`
  - `python3 scripts/codex/verify_repo.py --mode fast`
  - `python3 scripts/codex/verify_repo.py --mode full`
- rollback note:
  - 若动态端口注入影响其他测试，回退到固定端口并单独隔离本文件

## Progress

- current_status: verification completed
- current_milestone: Milestone 2
- milestone_state: complete

## Decision log

- 2026-03-29: 不放宽 emotiond 安全 gate；403 来自测试打到了真实 daemon，不是生产 contract 错误
- 2026-03-29: mock emotiond 改为动态端口，由 fixture 注入 `EMOTIOND_URL/EMOTIOND_BASE_URL`
- 2026-03-29: 保留兼容桥文件，避免仅因路径迁移导致 Node 模块加载失败

## Surprises / discoveries

- `mock_emotiond_service` 固定 `18080` 时，会把本机真实 emotiond 误判为测试目标
- Windows 原始路径插入 Node `require()` 字符串会导致模块路径解析不稳定

## Outcomes / retrospective

- 本轮已证明：目标测试可在隔离 mock 主链下稳定通过
- 还没证明：全仓 `full verify` 全绿
- 下一步最小闭环动作：确认 full verify 摘要中该失败面已消失，并收口状态文档

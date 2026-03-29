# OpenEmotion Outcome Capture Stabilization

## Goal

稳定 [test_outcome_capture_integration.py](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/tests/test_outcome_capture_integration.py)，消除 Windows 环境下的 fixture 启动错误、Node 模块路径错误，以及与本机真实 emotiond 端口冲突导致的伪失败。

## Non-goals

- 不修改 emotiond `/event` 的生产安全 gate
- 不扩到其他 OpenEmotion 失败面
- 不重写 OpenClaw outcome capture 业务逻辑

## Constraints

- 边界约束：本 slice 只处理测试隔离层与兼容桥，不放宽生产 contract
- 仓库/子仓约束：保持 OpenEmotion 为改动主仓；只在测试所需范围内新增兼容入口
- 环境约束：Windows 路径、Node `require()` 路径转义、已有本机 emotiond 进程都必须兼容
- 发布约束：变更必须最小、可回退、可通过目标测试直接验证

## Acceptance criteria

- [x] `OpenEmotion/tests/test_outcome_capture_integration.py` 全绿
- [x] 测试不再依赖固定 `127.0.0.1:18080`，不会误打到本机真实 emotiond
- [x] outcomeCapture 模块在测试路径下可被 Node 正常加载

## Known risks / dependencies

- 风险：full verify 仍可能被其他独立失败面阻塞
- 依赖：Node 可用；`OpenEmotion/.venv/Scripts/python.exe` 可用
- 外部 blocker：无；本 slice 不依赖外部服务

## Authority refs

- `PROJECT_MEMORY.md`
- `docs/AGENT_DEVELOPMENT_PLAYBOOK.md`
- [test_outcome_capture_integration.py](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/tests/test_outcome_capture_integration.py)
- [conftest.py](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/tests/conftest.py)
- [mock_emotiond.py](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/tests/fixtures/mock_emotiond.py)
- [api.py](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/emotiond/api.py)
- [security.py](/mnt/d/Project/AIProject/MyProject/Ego/OpenEmotion/emotiond/security.py)

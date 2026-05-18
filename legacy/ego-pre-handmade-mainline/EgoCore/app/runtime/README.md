# app/runtime/README.md

## 目录用途

这是 EgoCore 的旧 runtime / compatibility / 历史运行时相关目录。

它仍然包含：
- 旧 task runtime
- request classifier / registry
- 兼容性逻辑
- 一些测试仍会覆盖的历史链路

## 主要入口

- `agent_runner.py`
- `task_runtime.py`
- `request_classifier.py`
- `request_registry.py`

## 上下游依赖

### 上游
- 旧 Telegram/new runtime/compatibility 路径
- 部分 legacy tests

### 下游
- 工具执行
- request lifecycle
- 旧 runtime artifact / task logic

## 常改文件

仅当你在做以下任务时才应该改：
- compatibility containment
- legacy test preservation
- migration / downgrade cleanup

## 不该放什么

- 新的 Telegram Runtime v2 主链逻辑
- 新的 typed turn result / bridge / file-based prompt 主逻辑
- OpenEmotion 主体本体逻辑

## 与另一核心如何衔接

如果你在这里碰到 OpenEmotion 相关逻辑，优先检查它是不是历史兼容或迁移层，不要把这里误当成正式双核主链入口。

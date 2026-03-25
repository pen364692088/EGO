# openemotion/memory/README.md

## 目录用途

OpenEmotion 正式 memory 本体目录。

负责：
- event / narrative / policy memory
- memory storage / retrieval 的本体层
- 与 self-model / identity / appraisal 的长期联动

## 主要入口

按当前目录内实际模块为准，优先从：
- `event_memory.py`
- `narrative_memory.py`
- `policy_memory.py`
- 其余 memory 子模块

## 上下游依赖

### 上游
- `openemotion/identity/`
- `openemotion/self_model/`
- `emotiond/memory/`

### 下游
- storage / embedding / retrieval / consolidation 具体实现

## 常改文件

- event/narrative/policy memory 对应模块
- retrieval / salience / consolidation 相关模块

## 不该放什么

- Telegram/CLI 渠道逻辑
- EgoCore runtime / task orchestration
- 未登记的 mirror/cache 黑箱

## 与另一核心如何衔接

如果 EgoCore 需要 memory 结果，应通过 OpenEmotion 输出或结构化接口拿到，不能在 EgoCore 重新定义 memory 本体。

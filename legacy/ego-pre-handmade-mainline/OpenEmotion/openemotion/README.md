# openemotion/README.md

## 目录用途

OpenEmotion 的主体本体模块层。

这里是更接近“正式本体”的代码位置，负责：
- identity
- self_model
- memory
- cycle_core
- contracts/schema 对应的数据结构与模块

## 主要入口

- `openemotion/identity/`
- `openemotion/self_model/`
- `openemotion/memory/`
- `openemotion/cycle_core/`

## 上下游依赖

### 上游
- EgoCore 通过 adapter / contracts / emotiond 服务面与这里联动
- `emotiond/` 可以承接服务化、调度化处理

### 下游
- schemas
- memory storage / cycle core internals

## 常改文件

- `identity/identity_invariants.py`
- `identity/long_term_self_summary.py`
- `self_model/model.py`
- `memory/*`
- `cycle_core/*`

## 不该放什么

- Telegram/CLI/API 渠道接入
- 工具执行
- 高风险审批
- EgoCore runtime 主权逻辑

## 与另一核心如何衔接

EgoCore 不应在这里面偷塞渠道或 runtime 主逻辑；这里的输出应通过结构化接口返回给 EgoCore，由 EgoCore 做现实裁决。

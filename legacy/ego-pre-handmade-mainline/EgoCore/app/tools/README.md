# app/tools/README.md

## 目录用途

EgoCore 工具执行层。

负责：
- file / shell / python / diagnostics 等工具实现
- 工具参数规范化
- 工具结果返回
- 与 runtime/preflight/safety 的接口配合

## 主要入口

按实际工具文件与注册器为准；若是 Runtime v2 主链，通常通过：
- `app/runtime_v2/tool_broker.py`
- `config/tools.yaml`

## 上下游依赖

### 上游
- `app/runtime_v2/tool_broker.py`
- 旧 runtime compatibility 逻辑

### 下游
- 文件系统
- shell/python 执行环境
- 审批/安全策略

## 常改文件

- 具体 tool 实现文件
- `config/tools.yaml`
- Runtime v2 tool broker 对应适配

## 不该放什么

- Telegram / CLI 渠道逻辑
- 主体身份/记忆/appraisal 本体逻辑
- 任务层大规模编排逻辑

## 与另一核心如何衔接

工具执行结果可以回流到 OpenEmotion 作为 external_result，但 OpenEmotion 不直接实现工具层。

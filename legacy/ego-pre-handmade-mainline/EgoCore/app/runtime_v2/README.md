# app/runtime_v2/README.md

## 目录用途

Telegram/CLI 当前正式运行时主链（至少就 Telegram 主线方向而言）主要收口在这里。

这里负责：
- LLM action protocol
- Runtime v2 state
- typed turn result
- tool broker
- completion verification
- delivery policy
- Telegram bridge/policy
- file-based Runtime v2 prompt loading

## 主要入口

- `loop.py`
- `decision_engine.py`
- `transition.py`
- `telegram_bridge.py`
- `prompt_files.py`

## 上下游依赖

### 上游
- `app/telegram_bot.py`
- `app/cli.py`

### 下游
- `app/tools/`
- LLM client
- verifier / contracts / delivery policy

## 常改文件

- `loop.py`
- `decision_engine.py`
- `transition.py`
- `tool_broker.py`
- `completion_contract.py`
- `delivery_policy.py`
- `telegram_bridge.py`
- `prompt_files.py`

## 不该放什么

- Telegram transport plumbing 的大量细节
- OpenEmotion 主体本体逻辑
- 历史兼容路径的大量条件分支

## 与另一核心如何衔接

Runtime v2 目前仍主要在 EgoCore 内做 Telegram/CLI runtime 主链；若涉及主体语义、self-model、memory、policy_hint 等，应该通过 EgoCore ↔ OpenEmotion 的正式接口联动，而不是直接把主体逻辑塞到这里。

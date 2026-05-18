# 04_CHANGE_ROUTING.md

> 目标：把“想改什么功能 → 应优先查看哪些仓库 / 模块 / 目录 / 文件”写清楚。

## 使用规则

- 先判定能力归属：EgoCore 还是 OpenEmotion
- 再判定是否涉及双核接口
- 如果涉及接口字段或语义边界，必须同时看 contract / adapter / schema
- 未确认的具体文件不要脑补；优先看目录、模块族、入口族

## 路由矩阵

### 1. 改 Telegram / CLI / API 接入
**先看仓库：EgoCore**

优先目录/文件：
- `app/telegram_bot.py`
- `app/command_router.py`
- `app/main.py`
- `app/cli.py`
- `app/runtime_v2/telegram_bridge.py`
- `config/telegram.yaml`

常见误改点：
- 把渠道层改成 runtime 真相源
- 把 Telegram 特化逻辑写进 OpenEmotion

### 2. 改 session / task runtime / pause / resume / retry / cancel
**先看仓库：EgoCore**

优先目录/文件：
- `app/runtime_v2/`
- `app/runtime/task_runtime.py`
- `app/runtime/session_manager.py`
- `app/runtime/types.py`
- `app/command_router.py`
- `tests/test_runtime_v2_*`

注意：
- Telegram 现行主链优先看 Runtime v2
- 旧 runtime 目录仍有 compatibility-only/legacy 内容，不要默认当主链

### 3. 改工具执行 / preflight / tool_doctor / 高风险阻断
**先看仓库：EgoCore**

优先目录/文件：
- `app/tools/`
- `config/tools.yaml`
- `app/runtime_v2/tool_broker.py`
- `app/runtime_v2/completion_contract.py`
- `app/runtime_v2/delivery_policy.py`
- `tests/test_completion_contract_integration.py`
- `tests/test_runtime_v2_contracts_phase1.py`

### 4. 改 response plan / certainty / commitment / tone 边界
**先看仓库：EgoCore**，但若涉及主体语义倾向，要联动 OpenEmotion

优先目录/文件：
- `app/response/`
- `app/handlers/`
- `app/telegram_bot.py`
- `app/runtime_v2/telegram_bridge.py`
- `docs/P2B_*`, `docs/P2C_*`, `docs/P2D_*`

若涉及 `policy_hint / response_tendency` 语义来源：
- 同时看 OpenEmotion `emotiond/` 与 `openemotion/`

### 5. 改 identity invariants / self-model / long-term self summary / proto-self kernel
**先看仓库：OpenEmotion**

优先目录/文件：
- `openemotion/proto_self/` — **Proto-Self Kernel v1（主体内核主链）**
- `openemotion/identity/`
- `openemotion/self_model/`
- `emotiond/self_model_*`
- `schemas/self_model.schema.json`
- `schemas/long_term_self_summary.schema.json`
- `docs/*SELF_MODEL*`
- `docs/PROTO_SELF_KERNEL_V1_DESIGN.md`
- `docs/PROTO_SELF_KERNEL_V1_SPEC.md`

联动时再看 EgoCore：
- `app/openemotion_adapter/proto_self_adapter.py` — **Proto-Self Kernel adapter**
- `app/openemotion_adapter/proto_self_restore.py`（仅历史 compat/restore helper，不是 formal mainline）
- `app/openemotion_adapter/proto_self_trace_bridge.py`
- `app/runtime_v2/loop.py` — **wiring 点**
- `contracts/self_model.schema.json`

### 6. 改 memory / salience / consolidation / narrative / policy memory
**先看仓库：OpenEmotion**

优先目录/文件：
- `openemotion/memory/`
- `emotiond/memory/`
- `emotiond/narrative_memory.py`
- `emotiond/memory_legacy.py`（若是历史兼容/迁移问题）
- `docs/MEMORY_MODEL_V1.md`
- `docs/MEMORY_RETRIEVAL_*`

常见误改点：
- 把 memory 本体逻辑挪回 EgoCore
- 把 cache/mirror 当成本体

### 7. 改 appraisal / relationship update / internal state / drive_field
**先看仓库：OpenEmotion**

优先目录/文件：
- `openemotion/proto_self/appraisal.py` — **drive_field 更新**
- `openemotion/proto_self/state.py` — **ProtoSelfState（4+1 状态）**
- `emotiond/appraisal.py`
- `emotiond/state.py`
- `emotiond/relationship*`（候选入口族，以仓库搜索确认）
- `emotiond/allostasis.py`
- `emotiond/drives.py`
- `openemotion/cycle_core/`

### 8. 改 reflection / structured revision / policy candidate / cycle consolidation
**先看仓库：OpenEmotion**

优先目录/文件：
- `openemotion/proto_self/reflection.py` — **反思触发**
- `openemotion/proto_self/cycles.py` — **cycle 固化**
- `openemotion/proto_self/reducers.py` — **状态写回**
- `emotiond/reflection.py`
- `emotiond/reflection_shadow.py`
- `emotiond/meta_cognition.py`
- `emotiond/meta_cognitive_override.py`
- `openemotion/cycle_core/`

### 9. 改 EgoCore ↔ OpenEmotion 联动字段
**必须双仓联动看**

优先目录/文件：
- EgoCore `contracts/`
- EgoCore `egocore/adapters/openemotion_adapter.py`
- EgoCore `docs/EGOCORE_OPENEMOTION_FORMAL_CHAIN.md`
- OpenEmotion `schemas/`
- OpenEmotion `emotiond/api.py`
- OpenEmotion `openemotion/contracts/`（候选模块族，以仓库搜索确认）

### 10. 改 prompt / agent prompt / runtime instruction surface
**先看仓库：EgoCore**

优先目录/文件：
- `prompts/AGENT.md`
- `prompts/SOUL.md`
- `prompts/TOOLS.md`
- `app/runtime_v2/prompt_files.py`
- `app/runtime_v2/decision_engine.py`
- `/prompt*` Telegram commands in `app/telegram_bot.py`

### 11. 改 OpenEmotion 服务入口 / HTTP 接口 / emotiond 健康检查
**先看仓库：OpenEmotion**

优先目录/文件：
- `emotiond/api.py`
- `emotiond/daemon.py`
- `emotiond/main.py`
- `deploy/systemd/user/emotiond.service`
- `README.md`

### 12. 改语义解析器 / 意图识别 / parser_source 保真
**先看仓库：EgoCore**

优先目录/文件：
- `app/runtime_v2/semantic_parser.py` — **唯一权威语义解析入口**
- `app/runtime_v2/telegram_bridge.py` — **语义入口调用点**
- `tests/test_semantic_parser_llm.py` — **parser_source 保真测试**

关键约束：
- `heuristic_parse()` 只处理显式硬信号（命令/路径/附件），不处理执行动词
- `parser_source` 必须严格保真：semantic_parser / heuristic_parser / chat_default
- 禁止在 fallback 路径上改写已设置的 parser_source

常见误改点：
- 在 heuristic 中添加执行动词列表，使其变成第二套语义路由器
- `safe_semantic_parse()` 无条件覆写 `parser_source`
- 实际走 heuristic 但日志显示 semantic_parser，污染观测

## 五个典型改动场景

### 场景 A：Telegram bot 某个命令失效
- 先看 EgoCore `app/telegram_bot.py`
- 再看 `app/command_router.py`
- 再看 Runtime v2 command/bridge 是否拦截

### 场景 B：任务执行到一半没有 final completion
- 先看 EgoCore Runtime v2：`loop.py`, `transition.py`, `completion_contract.py`, `telegram_bridge.py`
- 再看 `logs/bot.log` 中 `runtime_v2.turn.*`

### 场景 C：自我模型字段不对
- 先看 OpenEmotion `openemotion/self_model/`
- 再看 `schemas/self_model.schema.json`
- 如果同步到 EgoCore，才看 adapter / contract

### 场景 D：Memory retrieval / salience 不对
- 先看 OpenEmotion `openemotion/memory/` 与 `emotiond/memory/`
- 再看对应 docs / reports

### 场景 E：Adapter 字段对不上
- 先看双方 contract/schema
- 再看 EgoCore `egocore/adapters/openemotion_adapter.py`
- 再看 OpenEmotion API / service 端点

## 常见误区

- 看到 `legacy/`、compat path、old runtime，就默认是主链
- 把 mirror/cache/shim 当成本体
- 想改主体语义，却先在 EgoCore 改 prompt 或 adapter 硬顶
- 想改运行时，却从 OpenEmotion 直接下手

# Agent Development Playbook

适用范围：legacy `EgoCore + OpenEmotion` 双仓协作开发。

> 2026-05-18 transition note: 当前默认 human/operator 体验主线已切到 `Ego_handmade`。本 playbook 只用于读取或维护 `legacy/ego-pre-handmade-mainline/EgoCore` 与 `legacy/ego-pre-handmade-mainline/OpenEmotion` 的历史实现，不再是新任务默认入口。新任务优先看 `docs/MAINLINE_QUICKSTART.md` 与 `Ego_handmade/`。

目标：让新 agent 在第一次接手任务时，能快速判断应该改哪里、按什么顺序改、怎样证明改动真正进入主链。

## 1. 一句话原则

- `EgoCore` 是唯一正式宿主：入口、runtime、工具执行、安全、审批、trace、audit
- `OpenEmotion` 是唯一正式主体内核：identity、self-model、memory、appraisal、reflection、proto-self
- 任何能力只能有一个权威源
- mirror / cache / shim 可以存在，但不能伪装成本体
- 涉及双核字段时，必须走 schema / contract / adapter，不能靠 prompt 或临时字段硬接

## 2. 第一次上手先读什么

先按这个顺序读，先建立边界感，再动代码：

1. `EgoCore/docs/00_MASTER_INDEX.md`
2. `EgoCore/docs/01_PROJECT_OVERVIEW.md`
3. `EgoCore/docs/03_BOUNDARY_AND_OWNERSHIP.md`
4. `EgoCore/docs/02_SYSTEM_FLOW.md`
5. `EgoCore/docs/04_CHANGE_ROUTING.md`
6. `OpenEmotion/docs/00_MASTER_INDEX.md`
7. `OpenEmotion/docs/01_PROJECT_OVERVIEW.md`
8. `OpenEmotion/docs/03_BOUNDARY_AND_OWNERSHIP.md`
9. `OpenEmotion/docs/PROTO_SELF_KERNEL_V1_DESIGN.md`
10. `OpenEmotion/docs/04_CHANGE_ROUTING.md`

如果是第一次接主体内核任务，再补：

1. `OpenEmotion/docs/PROTO_SELF_KERNEL_V1_SPEC.md`
2. `OpenEmotion/docs/MEMORY_MODEL_V1.md`
3. `OpenEmotion/openemotion/proto_self/`

## 3. 开发前六问

每次开发前，先回答这六个问题：

1. 这个能力归 `EgoCore` 还是 `OpenEmotion`
2. 它的正式权威源是谁
3. 它和哪个现有模块直接耦合
4. 是否会引入双重真相源
5. 是否会把 shim / mirror / cache 养成长期黑箱
6. 失败时由谁兜底

六问答不清，不要开始写代码。

## 4. 快速判定：第一落点在哪里

### 4.1 改 `EgoCore`

以下需求第一落点在 `EgoCore`：

- Telegram / CLI / API 接入
- session / task / runtime / pause / resume / retry / cancel
- 工具执行、preflight、completion、delivery
- 安全边界、审批、block、escalate
- trace / replay / audit
- prompt / agent instruction surface

优先看：

- `EgoCore/app/runtime_v2/loop.py`
- `EgoCore/app/runtime_v2/telegram_bridge.py`
- `EgoCore/app/runtime_v2/decision_engine.py`
- `EgoCore/app/runtime_v2/tool_broker.py`
- `EgoCore/app/runtime_v2/completion_contract.py`
- `EgoCore/app/telegram_bot.py`
- `EgoCore/app/command_router.py`

### 4.2 改 `OpenEmotion`

以下需求第一落点在 `OpenEmotion`：

- identity invariants
- self-model
- long-term self summary
- memory / salience / consolidation / narrative / policy memory
- appraisal / drive_field / internal state
- reflection / structured revision / cycle consolidation
- Proto-Self Kernel 本体语义

优先看：

- `OpenEmotion/openemotion/proto_self/kernel.py`
- `OpenEmotion/openemotion/proto_self/schemas.py`
- `OpenEmotion/openemotion/proto_self/state.py`
- `OpenEmotion/openemotion/proto_self/appraisal.py`
- `OpenEmotion/openemotion/proto_self/reflection.py`
- `OpenEmotion/openemotion/proto_self/cycles.py`
- `OpenEmotion/openemotion/proto_self/reducers.py`
- `OpenEmotion/openemotion/memory/`

### 4.3 必须双边一起改

以下需求通常必须双仓联动：

- `KernelEvent` 字段变化
- `KernelOutput` 字段变化
- `policy_hint` / `response_tendency` 结构变化
- `external_result` 后果回流
- trace payload 结构变化
- EgoCore 读取 Proto-Self 输出的消费逻辑

优先看：

- `OpenEmotion/openemotion/proto_self/schemas.py`
- `OpenEmotion/openemotion/proto_self/trace_types.py`
- `EgoCore/app/openemotion_adapter/proto_self_adapter.py`
- `EgoCore/app/runtime_v2/proto_self_runtime.py`
- `EgoCore/app/runtime_v2/decision_engine.py`

## 5. 正确的改动顺序

### 5.1 改运行时或外部行为

推荐顺序：

1. 先确认是渠道层问题、runtime 问题还是 tool/completion 问题
2. 从 `EgoCore/app/runtime_v2/` 主链入口往下找
3. 只在正式主链改，不先改 legacy / compatibility-only 路径
4. 补对应测试
5. 形成 trace / artifact / 真链路证据

### 5.2 改主体语义

推荐顺序：

1. 先改 `OpenEmotion` 本体模块
2. 先改状态定义 / schema，再改更新逻辑
3. 确保输出仍然只是 suggestion / tendency，不越权执行
4. 补 Proto-Self 单测
5. 如需接回 EgoCore，再改 adapter / runtime 消费层

### 5.3 改双核接口

固定顺序：

1. 定义或修改 OpenEmotion 侧 schema
2. 修改 OpenEmotion kernel 输出或输入消费
3. 修改 EgoCore adapter 的 normalize / invoke / consume
4. 修改 EgoCore runtime 的主链消费点
5. 补 contract / schema / adapter / route regression tests
6. 验证 trace 与实际运行结果一致

不要反过来先在 adapter 或 prompt 里发明字段。

## 6. Proto-Self 相关开发的标准姿势

Proto-Self 当前是主体主链，不是试验角落。

### 6.1 能改的层

- `schemas.py`：结构定义
- `state.py`：4+1 状态定义
- `appraisal.py`：drive_field 更新
- `self_model.py`：自我模型更新
- `cycles.py`：cycle 固化
- `reflection.py`：反思触发
- `reducers.py`：状态写回、policy_hint、response_tendency 推导
- `kernel.py`：统一主循环

### 6.2 不能做的事

- 不要在 `EgoCore` adapter 中实现主体语义
- 不要让 Proto-Self 直接输出执行命令
- 不要跳过 schema 直接塞自由字段
- 不要把 `policy_hint` 写成现实裁决

### 6.3 当前实际接线点

- `EgoCore/app/openemotion_adapter/proto_self_adapter.py`
- `EgoCore/app/runtime_v2/proto_self_runtime.py`
- `EgoCore/app/runtime_v2/loop.py`
- `EgoCore/app/runtime_v2/decision_engine.py`

## 7. 哪些地方不要优先动

这些地方默认不是第一落点，除非你已经确认它们仍是主链：

- `legacy/`
- compatibility-only 路径
- 旧 runtime 路径
- mirror / cache / shim
- 只改 prompt 试图修主体语义
- 只改 adapter 试图修主体本体

先看：

- `EgoCore/docs/05_DEPRECATED_AND_SHIMS.md`
- `EgoCore/docs/generated/recent_hotspots.md`
- `EgoCore/docs/generated/module_map.md`
- `OpenEmotion/docs/generated/module_map.md`

## 8. 验证要求

改动完成后，至少要留下一类正式证据：

- 单测 / 集成测试
- Telegram / CLI 真链路验证
- contract / schema 验证
- artifact / trace / replay 证据

### 8.1 改边界或接口时

优先补这些验证：

- contract test
- schema test
- adapter test
- route / flow regression test

### 8.2 改主体语义时

优先补这些验证：

- `OpenEmotion/openemotion/proto_self/tests/`
- 输出边界检查
- replay 一致性检查
- external_result 回流触发验证

### 8.3 改运行时时

优先补这些验证：

- `EgoCore/tests/test_runtime_v2_*`
- completion / delivery 合约验证
- `runtime_v2.turn.*` trace 检查

### 8.4 改 Telegram 主链时

不要只补散点单测。必须同时覆盖：

- 语义/bridge
- session state machine
- primary path 选择
- delivery/final reply
- 真实故障对应的跨轮回归

统一流程看：

- `EgoCore/docs/TELEGRAM_TEST_PROCESS.md`

最低回归门统一走：

- `EgoCore/tools/run_telegram_mainline_regression.sh`

## 9. 文档同步规则

以下情况改完后，必须同步文档：

- 目录结构变化
- 关键模块新增/删除
- 改动路由已变化
- shim / mirror / cache 状态变化
- 双核边界变化

至少检查：

- `EgoCore/docs/04_CHANGE_ROUTING.md`
- `EgoCore/docs/05_DEPRECATED_AND_SHIMS.md`
- `EgoCore/docs/06_AGENT_ONBOARDING.md`
- `OpenEmotion/docs/04_CHANGE_ROUTING.md`

如有较大结构变化，再重跑：

- `python EgoCore/tools/build_doc_system_inventory.py`
- `python OpenEmotion/tools/build_doc_inventory.py`

## 10. 常见误区

- 把 OpenEmotion 本体逻辑写回 EgoCore
- 把 runtime 问题丢给 OpenEmotion
- 把 mirror / cache 当正式真相
- 跳过 schema 直接改字段
- 看到旧路径就以为是当前主链
- 没有真实触发证据就报“完成”
- 只修 prompt，不修正式模块

## 11. 一个简单决策模板

收到需求后，先按这个模板判断：

1. 这件事是“外部世界问题”还是“主体语义问题”
2. 第一落点在哪个仓
3. 是否涉及跨核字段
4. 正式主链文件是哪几个
5. legacy / shim 是否只是干扰项
6. 改完用什么证据证明它真的生效

## 12. 最短执行原则

如果你时间很少，至少做到这四步：

1. 先看边界，再动代码
2. 只改权威源，不在镜像层发明语义
3. 只沿正式主链接线，不在兼容路径上赌运气
4. 改完必须留下测试或 trace 证据

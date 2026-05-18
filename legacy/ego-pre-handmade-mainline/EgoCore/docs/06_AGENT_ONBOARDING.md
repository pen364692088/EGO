# 06_AGENT_ONBOARDING.md

## 新 agent 上手顺序

1. `docs/00_MASTER_INDEX.md`
2. `docs/01_PROJECT_OVERVIEW.md`
3. `docs/03_BOUNDARY_AND_OWNERSHIP.md`
4. `docs/02_SYSTEM_FLOW.md`
5. `docs/04_CHANGE_ROUTING.md`
6. `docs/05_DEPRECATED_AND_SHIMS.md`
7. `docs/generated/module_map.md`
8. `docs/generated/recent_hotspots.md`

## 开发前检查

开发前必须回答六问：
1. 这个能力归 EgoCore 还是 OpenEmotion
2. 它的权威源是谁
3. 它和哪个现有模块耦合
4. 是否引入双重真相源
5. 是否让 shim 变成长期黑箱
6. 失败由谁兜底

## 操作顺序建议

### 想改 Telegram / Runtime
- 先看 EgoCore `app/telegram_bot.py`
- 再看 `app/runtime_v2/*`
- 再看 tests `test_runtime_v2_*`
- 再看 `docs/TELEGRAM_TEST_PROCESS.md`

### 想改主体/记忆/身份
- 先看 OpenEmotion `openemotion/*`
- 再看 `emotiond/*`
- 再看 schemas/docs

### 想改双核接口
- 先看 EgoCore `contracts/`
- 再看 `egocore/adapters/openemotion_adapter.py`
- 再看 OpenEmotion `schemas/`, `emotiond/api.py`

## 常见误区

- 误把 OpenClaw/legacy/openclaw 当正式主链
- 误把 Telegram adapter 当运行时真相源
- 误把 mirror / shim / cache 当主体本体
- 想改主体语义，却只在 EgoCore prompt/adapter 上补丁
- 想改运行时，却直接进 OpenEmotion

## 修改后验证要求

至少做以下之一：
- 单测/集成测试
- Telegram/CLI 真机链路验证
- 合同/schema 验证
- artifact/replay/trace 证据

若改的是边界相关功能，优先补：
- contract test
- adapter test
- route/flow regression test

若改的是 Telegram 主链，必须额外执行：
- `tools/run_telegram_mainline_regression.sh`
- 如来自真实故障，先补回归再修

## 提交与交接要求

- 文档/代码一致
- 写清当前层级（想法/构件/接入/启用/生效/观察）
- 写清主链接入状态、启用状态、真实触发证据
- 未确认项写 unknown / candidate，不补成事实
- 若涉及 shim / mirror / cache，必须更新 `05_DEPRECATED_AND_SHIMS.md`

## 快速判断：哪个仓库是第一落点？

| 需求 | 第一落点 |
|---|---|
| 对外渠道、runtime、工具、安全 | EgoCore |
| identity、memory、self-model、appraisal、reflection | OpenEmotion |
| 双核接口字段 | 两仓联动，先看 contracts + adapter |

# DOC_SYSTEM_BUILD_REPORT.md

## 当前层级

接入 / 启用（文档系统已落地到仓库，generated 盘点已生成，README 与主索引可直接使用）

## 主链接入状态

已接入：
- 主索引层 (`00_MASTER_INDEX.md` ~ `06_AGENT_ONBOARDING.md`)
- generated 盘点层 (`docs/generated/*`)
- 关键目录 README 层（EgoCore / OpenEmotion 关键目录）
- 回测记录与风险说明

## 启用状态

已启用，其他 agent 可以直接按索引顺序阅读并执行修改路由。

## 真实触发证据

- 基于真实仓库扫描生成：
  - `docs/generated/repo_inventory.md`
  - `docs/generated/file_inventory.csv`
  - `docs/generated/module_map.md`
  - `docs/generated/import_or_reference_map.csv`
  - `docs/generated/orphan_candidates.md`
  - `docs/generated/recent_hotspots.md`
- 基于真实目录/文件/引用关系与最近热点写成的 change routing / deprecated-shim 文档
- 基于 5 个真实场景做的文档回测（见本报告下方）

## 当前确定项

1. 正式核心只有 **EgoCore + OpenEmotion**
2. EgoCore 负责对外交互/运行/执行/治理
3. OpenEmotion 负责主体/身份/记忆/appraisal/reflection
4. OpenClaw 不是正式宿主
5. EgoCore Telegram Runtime v2 已成为 Telegram 正式主链方向
6. 旧 runtime/new runtime/legacy Telegram 路径是 compatibility-only 或 transitional
7. OpenEmotion 中 `legacy/openclaw/`、`openclaw_skill/`、部分 legacy/mirror 组件必须单独登记，不得误写成本体

## 关键未知

1. OpenEmotion 部分 `emotiond/*` 模块的 active vs historical 细分仍需更深引用补证
2. `legacy/openclaw/*` 与 `openclaw_skill/*` 的删除前提还未完全具备
3. 部分 orphan candidates 仅基于 import/ref 粗扫，仍需人工二次确认后才能进入 deprecated

## 离最终生效还差什么

若以“文档系统建设完成”为口径，目前已满足主索引、generated、change routing、deprecated/shim 登记、5 个场景回测。
后续增量工作主要是：
- 定期更新 generated 层
- 补更多模块 README
- 对 deprecated-candidate 持续补证

## 下一步最小闭环动作

1. 使用 `python tools/build_doc_system_inventory.py` 持续刷新 generated 盘点层
2. 在后续模块改动时同步维护 `04_CHANGE_ROUTING.md` 与 `05_DEPRECATED_AND_SHIMS.md`
3. 对 `legacy/openclaw/*`、`openclaw_skill/*` 做下一轮引用补证

## 变更清单

### 新建主索引与上手层
- `docs/00_MASTER_INDEX.md`
- `docs/01_PROJECT_OVERVIEW.md`
- `docs/02_SYSTEM_FLOW.md`
- `docs/03_BOUNDARY_AND_OWNERSHIP.md`
- `docs/04_CHANGE_ROUTING.md`
- `docs/05_DEPRECATED_AND_SHIMS.md`
- `docs/06_AGENT_ONBOARDING.md`
- `docs/DOC_SYSTEM_BUILD_REPORT.md`

### 新建 generated 盘点层
- `docs/generated/repo_inventory.md`
- `docs/generated/file_inventory.csv`
- `docs/generated/module_map.md`
- `docs/generated/import_or_reference_map.csv`
- `docs/generated/orphan_candidates.md`
- `docs/generated/recent_hotspots.md`

### 新建/补充目录 README
- EgoCore 关键目录 README
- OpenEmotion 关键目录 README

## 风险清单

1. OpenEmotion 历史沉积比 EgoCore 更重，部分 legacy/transitional 仍需补证
2. orphan_candidates 只代表“当前粗扫无明显 import/ref”，不代表可直接删除
3. 文档系统若不随代码持续维护，容易再次漂移

## 5 个真实场景回测

### 场景 1：改 Telegram / 消息入口问题
- 用户要改什么：Telegram bot slash command / runtime_v2 路径
- 文档把 agent 引导到哪里：`04_CHANGE_ROUTING.md` → Telegram / CLI / API 接入
- 实际查看：`app/telegram_bot.py`, `app/command_router.py`, `app/runtime_v2/telegram_bridge.py`
- 是否快速定位：是
- 是否误碰越界：否
- 文档修正：补充了 Runtime v2 Telegram path 为正式主链

### 场景 2：改 task runtime / pause-resume / retry
- 用户要改什么：`/new`, `/reset`, `/status` 等会话/runtime 行为
- 文档引导：`04_CHANGE_ROUTING.md` → session/task runtime
- 实际查看：`app/runtime_v2/loop.py`, `app/telegram_bot.py`, `app/command_router.py`
- 是否快速定位：是
- 是否误碰越界：否
- 文档修正：强调 Telegram 主链优先看 Runtime v2

### 场景 3：改工具执行 / 安全阻断 / preflight
- 用户要改什么：completion / verification / tool 契约
- 文档引导：`04_CHANGE_ROUTING.md` → 工具执行 / preflight / tool_doctor / 高风险阻断
- 实际查看：`app/tools/`, `app/runtime_v2/tool_broker.py`, `app/runtime_v2/completion_contract.py`
- 是否快速定位：是
- 是否误碰越界：否
- 文档修正：增加 contract + verifier 说明

### 场景 4：改 self-model / identity / long-term summary
- 用户要改什么：主体身份/自我模型相关落点
- 文档引导：`04_CHANGE_ROUTING.md` → identity invariants / self-model / long-term self summary
- 实际查看：OpenEmotion `openemotion/identity/`, `openemotion/self_model/`, `schemas/*self_model*`
- 是否快速定位：是
- 是否误碰越界：否
- 文档修正：补充 EgoCore 仅在 adapter/contract 侧联动

### 场景 5：改 memory / appraisal / reflection
- 用户要改什么：memory 演化、appraisal、reflection 落点
- 文档引导：`04_CHANGE_ROUTING.md` → memory / appraisal / reflection
- 实际查看：`openemotion/memory/`, `emotiond/memory/`, `emotiond/appraisal.py`, `emotiond/reflection.py`
- 是否快速定位：是
- 是否误碰越界：否
- 文档修正：明确 `memory_legacy.py` 只是 transitional，不是正式本体

## 完成口径

本次可以报：**文档系统建设完成（第一版）**

理由：
1. 主索引与子文档已落地
2. generated 盘点层已生成
3. 修改落点矩阵已落地
4. shim / mirror / cache / deprecated-candidate 已登记
5. 至少 5 个真实场景回测已记录
6. 没有改写双核边界，也没有引入第二套真相源
7. 未确认项已明确标 unknown / candidate

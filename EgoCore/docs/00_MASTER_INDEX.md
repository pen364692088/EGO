# 00_MASTER_INDEX.md

## 项目一句话定义

本项目的正式核心只有 **EgoCore + OpenEmotion**：
- **EgoCore** 负责对外交互、运行时、工具执行、安全边界、治理与审计
- **OpenEmotion** 负责主体、身份、自我模型、记忆演化、appraisal、reflection
- **OpenClaw 不是正式宿主**，最多是历史宿主/兼容链路/施工执行体参考，不是正式架构本体

## 当前阶段

当前主线是：
**把 EgoCore 作为唯一正式宿主，把 OpenEmotion 作为唯一主体内核，通过结构化接口接成可验证的双核工程系统。**

在 EgoCore 仓库内，**Telegram native mainline + 最小 Contract Runtime** 已成为 Telegram 正式主链：
- `telegram_bot -> telegram_runtime_bridge -> native_loop -> contract_runtime -> openemotion hooks -> delivery`
- 旧 `runtime_v2` 仍保留为兼容/桥接层，但不再是 Telegram 当前正式执行口径
- 权威状态以 `docs/PROGRAM_STATE_UNIFIED.yaml` 与总仓 `PROJECT_MEMORY.md` 为准

## 最新已证实状态（2026-03-27）

- **Proto-Self Kernel v1** 已完成真实 Telegram 主链接入
- **P4 真实主链收口已完成**
  - `tool:file` 的 blocked / success 现在同 `closure_family_id`
  - 首次 retry-success 已点亮 `repair_closure=true`
- 最新报告：
  - `../../artifacts/closure_real_evidence/CLOSURE_REAL_EVIDENCE_REPORT.md`
  - `../../artifacts/closure_repair_fix/CLOSURE_REPAIR_FIX_REPORT.md`

**Proto-Self Kernel v1** (已验证 Telegram E2E)：
- 设计稿：`../../OpenEmotion/docs/PROTO_SELF_KERNEL_V1_DESIGN.md`
- 接口草案：`../../OpenEmotion/docs/PROTO_SELF_KERNEL_V1_SPEC.md`
- **实现**：`../../OpenEmotion/openemotion/proto_self/` (已验收通过)
- **Adapter**：`app/openemotion_adapter/proto_self_*.py` (EgoCore 侧薄接线)
- **基础验收报告**：`../artifacts/proto_self_v1/ACCEPTANCE_REPORT_CYCLE_STRENGTHEN_20260324.md`
  - Cycle strengthen: ✅ hits 3→9, strength 0.25→0.85
  - External failure reflection: ✅ reflection_trigger=external_failure
  - Revision counter: ✅ 16→30 (+14)
- **最新真实主链报告**：`../../artifacts/closure_repair_fix/CLOSURE_REPAIR_FIX_REPORT.md`
  - same-family drift: ✅ fixed
  - repair_closure activation: ✅ fixed on real retry-success

## 先读顺序

### 新 agent 第一顺序
1. `docs/01_PROJECT_OVERVIEW.md`
2. `docs/03_BOUNDARY_AND_OWNERSHIP.md`
3. `docs/02_SYSTEM_FLOW.md`
4. `docs/04_CHANGE_ROUTING.md`
5. `docs/05_DEPRECATED_AND_SHIMS.md`
6. `docs/06_AGENT_ONBOARDING.md`
7. `docs/07_DOC_SYSTEM_MAINTENANCE.md`

### 想理解项目
- `docs/01_PROJECT_OVERVIEW.md`
- `docs/02_SYSTEM_FLOW.md`
- `docs/03_BOUNDARY_AND_OWNERSHIP.md`
- **OpenEmotion Proto-Self Kernel v1 设计稿**：`../../OpenEmotion/docs/PROTO_SELF_KERNEL_V1_DESIGN.md`

### 想改功能
- `docs/04_CHANGE_ROUTING.md`
- `docs/generated/module_map.md`
- `docs/generated/import_or_reference_map.csv`

### 想排障
- `docs/02_SYSTEM_FLOW.md`
- `docs/04_CHANGE_ROUTING.md`
- `docs/generated/recent_hotspots.md`
- `docs/generated/repo_inventory.md`

### 想辨别废弃文件 / shim / 过渡实现
- `docs/05_DEPRECATED_AND_SHIMS.md`
- `docs/generated/orphan_candidates.md`

## 任务类型跳转

| 任务类型 | 先看哪里 |
|---|---|
| 理解双核架构 | `01_PROJECT_OVERVIEW.md` + `03_BOUNDARY_AND_OWNERSHIP.md` |
| 理解端到端流程 | `02_SYSTEM_FLOW.md` |
| 想改 Telegram / CLI / API / Runtime | `04_CHANGE_ROUTING.md` |
| 想改 identity / self-model / memory / reflection | `04_CHANGE_ROUTING.md` + [OpenEmotion Proto-Self 设计稿](../../OpenEmotion/docs/PROTO_SELF_KERNEL_V1_DESIGN.md) |
| 想找 shim / mirror / cache / deprecated-candidate | `05_DEPRECATED_AND_SHIMS.md` |
| 新 agent 上手 | `06_AGENT_ONBOARDING.md` |
| 想看仓库真实盘点 | `docs/generated/` 下各文件 |

## generated 盘点层

文件都在：`docs/generated/`

重点文件：
- `docs/generated/repo_inventory.md`
- `docs/generated/file_inventory.csv`
- `docs/generated/module_map.md`
- `docs/generated/import_or_reference_map.csv`
- `docs/generated/orphan_candidates.md`
- `docs/generated/recent_hotspots.md`

更新方法：
- 运行 `python tools/build_doc_system_inventory.py`
- 更新说明看 `docs/07_DOC_SYSTEM_MAINTENANCE.md`

## 关键提醒

- 正式核心只有 **EgoCore + OpenEmotion**
- EgoCore 是宿主，不是主体本体
- OpenEmotion 是主体本体，不直接承担渠道/工具/高风险审批
- mirror / shim / cache 允许，但必须单独登记，不能伪装成本体
- 未确认项必须标成 unknown / candidate，不能脑补成事实

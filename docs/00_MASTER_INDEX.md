# 00_MASTER_INDEX.md

## 项目一句话定义

**OpenEmotion 是 EgoCore 的主体内核，是双核架构中唯一负责主体本体的一方。**

- **OpenEmotion** 负责 identity、self-model、memory、appraisal、reflection 的本体解释权
- **EgoCore** 负责对外交互、运行时、工具执行、安全边界、治理与审计
- **OpenClaw 不是正式宿主**，最多是历史宿主/兼容链路/施工执行体参考，不是正式架构本体

## 当前阶段

当前主线是：
**Proto-Self Kernel v1 已完成主链接入，具备真实 Telegram E2E 验证证据。**

## 先读顺序

### 新 agent 第一顺序
1. `docs/01_PROJECT_OVERVIEW.md`
2. `docs/03_BOUNDARY_AND_OWNERSHIP.md`
3. `docs/PROTO_SELF_KERNEL_V1_DESIGN.md`
4. `docs/PROTO_SELF_KERNEL_V1_SPEC.md`
5. `docs/04_CHANGE_ROUTING.md`
6. `docs/06_AGENT_ONBOARDING.md`

### 想理解项目
- `docs/01_PROJECT_OVERVIEW.md`
- `docs/PROTO_SELF_KERNEL_V1_DESIGN.md`
- `docs/MEMORY_MODEL_V1.md`

### 想改功能
- `docs/04_CHANGE_ROUTING.md`
- `docs/generated/module_map.md`

### 想理解双核边界
- `docs/03_BOUNDARY_AND_OWNERSHIP.md`
- `POLICIES/EgoCore_OpenEmotion_Boundary_Constitution_v1.md`

### 想看当前验证状态
- `docs/PROGRAM_STATE_UNIFIED.yaml`（权威源）
- `README.md`

## 任务类型跳转

| 任务类型 | 先看哪里 |
|---|---|
| 理解主体内核架构 | `01_PROJECT_OVERVIEW.md` + `PROTO_SELF_KERNEL_V1_DESIGN.md` |
| 改 identity / self-model / proto-self | `04_CHANGE_ROUTING.md` §5 |
| 改 memory / salience / consolidation | `04_CHANGE_ROUTING.md` §6 + `MEMORY_MODEL_V1.md` |
| 改 appraisal / drive_field | `04_CHANGE_ROUTING.md` §7 |
| 改 reflection / cycle | `04_CHANGE_ROUTING.md` §8 |
| 改 EgoCore 联动字段 | `04_CHANGE_ROUTING.md` §9 |
| 新 agent 上手 | `06_AGENT_ONBOARDING.md` |

## generated 盘点层

文件都在：`docs/generated/`

重点文件：
- `docs/generated/module_map.md`
- `docs/generated/repo_inventory.md`

更新方法：
- 运行 `tools/build_doc_inventory.py`
- 更新说明看 `docs/07_DOC_SYSTEM_MAINTENANCE.md`

## 当前正式主线：Proto-Self Kernel v1

| 文档 | 说明 |
|------|------|
| [设计稿](PROTO_SELF_KERNEL_V1_DESIGN.md) | 最小主体内核设计稿（MVS 内核候选） |
| [接口草案](PROTO_SELF_KERNEL_V1_SPEC.md) | 接口与伪代码 |
| [实现](../openemotion/proto_self/) | 已验证通过 |
| [验收报告](../artifacts/proto_self_v1/ACCEPTANCE_REPORT_20260321.md) | WS-PSK-6 验收通过 |

### 核心主张

> **Proto-Self 的本体核应该尽量小：一个统一递归更新器 + 少量高价值状态 + 明确后果回流。**

最小闭环：**事件进入 → 内态更新 → 生成倾向 → 经过 EgoCore 裁决 → 结果回流 → 强化/削弱自我不变量**

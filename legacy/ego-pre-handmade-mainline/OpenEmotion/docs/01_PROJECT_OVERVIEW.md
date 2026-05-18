# 01_PROJECT_OVERVIEW.md

## 项目定位

**OpenEmotion 是双核架构中的主体侧，负责身份、自我模型、记忆演化、情感评价与反思修正。**

### 核心职责

| 职责 | 说明 |
|------|------|
| **identity invariants** | 身份不变量：跨轮、跨会话、跨任务尽量不乱跳的主体骨架 |
| **self-model** | 自我模型：系统对自己能力、限制、当前状态、倾向的结构化认知 |
| **long-term self summary** | 长期自我摘要：持久化的自我认知 |
| **memory** | 三层记忆：event / narrative / policy |
| **appraisal** | 评价：drive_field、内部张力场 |
| **reflection** | 反思：失败后生成修正建议 |

### 边界

| OpenEmotion 负责 | EgoCore 负责 |
|------------------|--------------|
| identity invariants | 用户入口（Telegram/CLI/API） |
| self-model | 运行时 |
| proto-self kernel | 任务系统 |
| memory 本体 | 工具执行 |
| appraisal / reflection | 恢复 orchestration |
| | adapter / audit / trace |

**允许 mirror / cache / shim，不允许双主。**

## 当前正式主线：Proto-Self Kernel v1

### 设计目标

实现最小可持续主体内核（Minimum Viable Self）：

- 一个统一递归更新器 `process_event()`
- 少量高价值状态（4+1）
- 明确后果回流（failure → reflection → revision）

### 状态设计

| 状态 | 说明 |
|------|------|
| `identity_invariants` | 身份不变量 |
| `self_model` | 自我模型 |
| `drive_field` | 内部张力场（功能性偏置） |
| `cycle_store` | 可重入不变量存储 |
| `episodic_trace` | 情节记忆轨迹 |

### 主循环

```
事件进入 → 内态更新 → 生成倾向 → EgoCore 裁决 → 结果回流 → 强化/削弱自我不变量
```

## 验证状态

| 主线 | 状态 | 说明 |
|------|------|------|
| **PROTO_SELF_KERNEL_V1** | **verified_mainline_e2e** | 主链接入 + Telegram E2E 验证通过 |
| CYCLE_CORE_V1 | verified_e2e | Telegram E2E 验证通过 |
| WS_C1 | verified_e2e | 三层记忆模型已验证 |
| long-term self summary | verified_e2e | 5/5 测试通过 |

## 仓库结构

```
openemotion/
├── proto_self/           # Proto-Self Kernel v1
│   ├── kernel.py         # 主循环 process_event()
│   ├── schemas.py        # KernelEvent / KernelOutput
│   ├── state.py          # ProtoSelfState
│   ├── appraisal.py      # drive_field 更新
│   ├── self_model.py     # self_model 更新
│   ├── cycles.py         # cycle 固化
│   ├── reflection.py     # 反思触发
│   ├── reducers.py       # 状态写回
│   └── tests/            # 单元测试
├── identity/             # 身份不变量
├── self_model/           # 自我模型
├── memory/               # 三层记忆
└── cycle_core/           # Cycle 核心
```

## 权威源

- **PROGRAM_STATE_UNIFIED.yaml** — 当前状态权威源
- **README.md** — 项目概览
- **POLICIES/EgoCore_OpenEmotion_Boundary_Constitution_v1.md** — 双核边界宪章

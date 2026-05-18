# Repo Migration Matrix

> 日期: 2026-03-16
> 目的: 记录仓库迁移的详细矩阵

---

## 迁移矩阵

### Identity Invariants

| 组件 | 当前位置 | 目标位置 | 迁移类型 | 状态 |
|------|---------|---------|---------|------|
| schema 定义 | EgoCore/contracts/ | OpenEmotion/schemas/ | 迁移 | ✅ 已完成 |
| 本体逻辑 | EgoCore (散落在 guard) | OpenEmotion/openemotion/identity/ | 新建 | ✅ 已完成 |
| loader | EgoCore/egocore/runtime/identity_guard.py | 保留，改名为 identity_loader.py | 重构 | ⏳ 待执行 |
| snapshot | EgoCore/artifacts/identity/ | 保留为 host-side mirror | 保留 | ✅ 无需变更 |

### Self-Model

| 组件 | 当前位置 | 目标位置 | 迁移类型 | 状态 |
|------|---------|---------|---------|------|
| schema 定义 | EgoCore/contracts/ | OpenEmotion/schemas/ | 迁移 | ✅ 已完成 |
| 本体逻辑 | EgoCore (散落在 manager) | OpenEmotion/openemotion/self_model/ | 新建 | ✅ 已完成 |
| loader | EgoCore/egocore/runtime/self_model_manager.py | 保留，改名为 self_model_loader.py | 重构 | ⏳ 待执行 |
| snapshot | EgoCore/artifacts/self_model/ | 保留为 host-side mirror | 保留 | ✅ 无需变更 |

### Long-Term Self Summary

| 组件 | 当前位置 | 目标位置 | 迁移类型 | 状态 |
|------|---------|---------|---------|------|
| schema 定义 | EgoCore/contracts/ | OpenEmotion/schemas/ | 迁移 | ✅ 已完成 |
| 生成逻辑 | EgoCore/egocore/runtime/summary_generator.py | OpenEmotion/openemotion/identity/ | 迁移 | ✅ 已完成 |
| loader | N/A | EgoCore/egocore/runtime/summary_loader.py | 新建 | ⏳ 待执行 |
| snapshot | EgoCore/artifacts/summary/ | 保留为 host-side mirror | 保留 | ✅ 无需变更 |

### Self Restore

| 组件 | 当前位置 | 目标位置 | 迁移类型 | 状态 |
|------|---------|---------|---------|------|
| restore orchestration | EgoCore/egocore/runtime/self_restorer.py | 保留 | 保留 | ✅ 无需变更 |
| context injection | EgoCore/egocore/runtime/context_injector.py | 保留 | 保留 | ✅ 无需变更 |
| audit schema | EgoCore/contracts/restore_audit.schema.json | 保留 | 保留 | ✅ 无需变更 |

---

## 边界关系图

```
┌─────────────────────────────────────────────────────────────┐
│                        EgoCore                               │
│  (宿主、运行时、执行、治理、适配、注入、缓存、镜像、审计)      │
├─────────────────────────────────────────────────────────────┤
│  egocore/runtime/                                           │
│    ├── identity_loader.py       # host-side loader          │
│    ├── self_model_loader.py     # host-side loader          │
│    ├── summary_loader.py        # host-side loader          │
│    ├── self_restorer.py         # restore orchestration     │
│    └── context_injector.py      # context injection         │
│                                                              │
│  egocore/adapters/                                          │
│    ├── openemotion_adapter.py   # adapter                   │
│    └── contract_guard.py        # compatibility guard       │
│                                                              │
│  artifacts/                                                 │
│    ├── identity/               # host-side mirror           │
│    ├── self_model/             # host-side mirror           │
│    └── summary/                # host-side mirror           │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ 通过 adapter 读取
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                      OpenEmotion                             │
│  (主体本体：identity、self-model、memory、appraisal...)      │
├─────────────────────────────────────────────────────────────┤
│  openemotion/identity/                                      │
│    ├── identity_invariants.py   # 身份本体                  │
│    └── long_term_self_summary.py # 摘要生成                │
│                                                              │
│  openemotion/self_model/                                    │
│    └── model.py                # 自我模型本体               │
│                                                              │
│  schemas/                                                   │
│    ├── identity_invariants.schema.json                      │
│    ├── self_model.schema.json                               │
│    └── long_term_self_summary.schema.json                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 执行状态汇总

| 阶段 | 状态 |
|------|------|
| S1: 盘点与归类 | ✅ 完成 |
| S2: 建立 OpenEmotion 正式模块 | ✅ 完成 |
| S3: EgoCore 改为读取 OpenEmotion 产物 | ⏳ 待执行 |
| S4: Shim 登记与限期 | ✅ 完成 |
| S5: 删除或降级违规实现 | ⏳ 待执行 |
| S6: 回归验证 | ⏳ 待执行 |
| S7: Gate A/B/C 验证 | ⏳ 待执行 |

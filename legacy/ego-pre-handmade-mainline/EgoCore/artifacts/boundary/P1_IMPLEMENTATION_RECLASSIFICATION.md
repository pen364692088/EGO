# P1 Implementation Reclassification

> 日期: 2026-03-16
> 目的: 对 P1 实现进行重新归类

---

## 1. 当前 P1 实现归类

### P1-A: Identity Invariants v1

| 组件 | 当前归类 | 重新归类 | 说明 |
|------|---------|---------|------|
| identity_invariants.schema.json | EgoCore schema | **OpenEmotion schema** | 主体本体定义 |
| identity_guard.py | EgoCore 本体 | **EgoCore host-side loader** | 加载/校验/守卫 |
| ceo_invariants_snapshot.json | EgoCore artifact | **EgoCore host-side mirror** | 运行时缓存 |

**整改动作**：
- schema 定义迁至 OpenEmotion
- identity_guard.py 改为 host-side loader（读取 OpenEmotion 产物）

### P1-B: Self-Model v1

| 组件 | 当前归类 | 重新归类 | 说明 |
|------|---------|---------|------|
| self_model.schema.json | EgoCore schema | **OpenEmotion schema** | 主体本体定义 |
| self_model_manager.py | EgoCore 本体 | **拆分** | 本体逻辑迁至 OpenEmotion，管理器保留为 loader |
| ceo_self_model_snapshot.json | EgoCore artifact | **EgoCore host-side mirror** | 运行时缓存 |

**整改动作**：
- schema 定义迁至 OpenEmotion
- 本体逻辑（更新规则、语义解释）迁至 OpenEmotion
- self_model_manager.py 改为 host-side loader

### P1-C1: Long-Term Self Summary v1

| 组件 | 当前归类 | 重新归类 | 说明 |
|------|---------|---------|------|
| long_term_self_summary.schema.json | EgoCore schema | **OpenEmotion schema** | 主体本体定义 |
| summary_generator.py | EgoCore 本体 | **OpenEmotion 本体** | 生成逻辑属于主体 |
| summary_*.json | EgoCore artifact | **EgoCore host-side mirror** | 运行时缓存 |

**整改动作**：
- schema 定义迁至 OpenEmotion
- summary_generator.py 迁至 OpenEmotion
- EgoCore 只读取生成的 summary

### P1-C2: Self Restore v1

| 组件 | 当前归类 | 重新归类 | 说明 |
|------|---------|---------|------|
| self_restorer.py | EgoCore orchestration | **EgoCore orchestration** | ✅ 归宿主 |
| context_injector.py | EgoCore injection | **EgoCore injection** | ✅ 归宿主 |
| restore_audit.schema.json | EgoCore audit | **EgoCore audit** | ✅ 归治理层 |

**整改动作**：无需整改，归类正确。

---

## 2. 重新归类后的边界

### EgoCore 职责（宿主）

```
egocore/
├── adapters/
│   ├── openemotion_adapter.py    # adapter
│   └── contract_guard.py          # compatibility guard
├── runtime/
│   ├── identity_loader.py         # host-side loader (原 identity_guard)
│   ├── self_model_loader.py       # host-side loader (原 self_model_manager)
│   ├── summary_loader.py          # host-side loader (新增)
│   ├── self_restorer.py           # restore orchestration
│   └── context_injector.py        # context injection
└── artifacts/
    ├── identity/                   # host-side mirror
    ├── self_model/                 # host-side mirror
    └── summary/                    # host-side mirror
```

### OpenEmotion 职责（主体内核）

```
openemotion/
├── identity/
│   ├── identity_invariants.py     # 本体逻辑
│   └── long_term_self_summary.py  # 生成逻辑
├── self_model/
│   └── model.py                   # 本体逻辑
└── schemas/
    ├── identity_invariants.schema.json
    ├── self_model.schema.json
    └── long_term_self_summary.schema.json
```

---

## 3. Shim 登记要求

所有留在 EgoCore 的过渡实现必须登记：

| 名称 | 类型 | 到期版本 | 删除计划 |
|------|------|---------|---------|
| identity_invariants.schema.json | shim | v1.1.0 | 迁移后删除 EgoCore 版本 |
| self_model.schema.json | shim | v1.1.0 | 迁移后删除 EgoCore 版本 |
| long_term_self_summary.schema.json | shim | v1.1.0 | 迁移后删除 EgoCore 版本 |
| summary_generator.py | shim | v1.1.0 | 迁移后改为调用 OpenEmotion |

---

## 4. 验收标准

重新归类完成后，必须满足：

1. ✅ OpenEmotion 成为 identity/self-model/summary 的唯一权威源
2. ✅ EgoCore 只有 loader/validator/mirror
3. ✅ 所有 shim 已登记
4. ✅ Self Restore 仍可正常工作
5. ✅ 测试全部通过

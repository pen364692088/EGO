# Boundary Ownership Audit

> 审计日期: 2026-03-16
> 审计范围: EgoCore + OpenEmotion 功能归属

---

## 1. 审计结论

**总体状态: ⚠️ 需要整改**

当前存在主体本体逻辑落在 EgoCore 仓库的问题，需要迁回 OpenEmotion。

---

## 2. EgoCore 功能归属审计

### 2.1 Identity 相关

| 文件 | 当前归属 | 正式归属 | 是否越界 | 处理方式 |
|------|---------|---------|---------|---------|
| contracts/identity_invariants.schema.json | EgoCore | OpenEmotion | ⚠️ 越界 | 迁移 schema 定义 |
| egocore/runtime/identity_guard.py | EgoCore | EgoCore | ✅ 正确 | 保留为 host-side loader |
| artifacts/identity/ceo_invariants_snapshot.json | EgoCore | EgoCore | ✅ 正确 | 保留为 host-side mirror |

**判断依据**: schema 定义和字段语义属于主体本体，应归 OpenEmotion。

### 2.2 Self-Model 相关

| 文件 | 当前归属 | 正式归属 | 是否越界 | 处理方式 |
|------|---------|---------|---------|---------|
| contracts/self_model.schema.json | EgoCore | OpenEmotion | ⚠️ 越界 | 迁移 schema 定义 |
| egocore/runtime/self_model_manager.py | EgoCore | EgoCore | ⚠️ 部分越界 | 拆分：管理逻辑保留，本体逻辑迁移 |
| artifacts/self_model/ceo_self_model_snapshot.json | EgoCore | EgoCore | ✅ 正确 | 保留为 host-side mirror |

**判断依据**: self-model 字段语义和更新规则属于主体本体。

### 2.3 Summary 相关

| 文件 | 当前归属 | 正式归属 | 是否越界 | 处理方式 |
|------|---------|---------|---------|---------|
| contracts/long_term_self_summary.schema.json | EgoCore | OpenEmotion | ⚠️ 越界 | 迁移 schema 定义 |
| egocore/runtime/summary_generator.py | EgoCore | OpenEmotion | ⚠️ 越界 | 迁移生成逻辑 |
| artifacts/summary/summary_*.json | EgoCore | EgoCore | ✅ 正确 | 保留为 host-side mirror |

**判断依据**: summary 生成规则和刷新逻辑属于主体本体。

### 2.4 Restore 相关

| 文件 | 当前归属 | 正式归属 | 是否越界 | 处理方式 |
|------|---------|---------|---------|---------|
| egocore/runtime/self_restorer.py | EgoCore | EgoCore | ✅ 正确 | 保留，restore orchestration 属宿主 |
| egocore/runtime/context_injector.py | EgoCore | EgoCore | ✅ 正确 | 保留，注入属于宿主 |
| contracts/restore_audit.schema.json | EgoCore | EgoCore | ✅ 正确 | 保留，审计属于治理层 |

**判断依据**: restore orchestration 和 context injection 属于宿主职责。

### 2.5 Adapter 相关

| 文件 | 当前归属 | 正式归属 | 是否越界 | 处理方式 |
|------|---------|---------|---------|---------|
| egocore/adapters/openemotion_adapter.py | EgoCore | EgoCore | ✅ 正确 | 保留 |
| egocore/adapters/contract_guard.py | EgoCore | EgoCore | ✅ 正确 | 保留 |

---

## 3. OpenEmotion 功能归属审计

### 3.1 当前状态

OpenEmotion 仓库当前缺少以下正式模块：
- ❌ identity 模块
- ❌ self_model 模块
- ❌ long_term_self_summary 模块
- ✅ memory/ 目录存在（但需要检查是否符合规范）

### 3.2 需要创建的模块

| 模块 | 目标路径 | 来源 |
|------|---------|------|
| identity_invariants | openemotion/identity/identity_invariants.py | 迁移自 EgoCore |
| self_model | openemotion/self_model/model.py | 迁移自 EgoCore |
| long_term_self_summary | openemotion/identity/long_term_self_summary.py | 迁移自 EgoCore |

---

## 4. 迁移矩阵

### 4.1 必须迁移到 OpenEmotion

| 功能 | 当前位置 | 目标位置 | 优先级 |
|------|---------|---------|--------|
| identity_invariants schema 定义 | EgoCore/contracts/ | OpenEmotion/schemas/ | P0 |
| self_model schema 定义 | EgoCore/contracts/ | OpenEmotion/schemas/ | P0 |
| long_term_self_summary schema 定义 | EgoCore/contracts/ | OpenEmotion/schemas/ | P0 |
| identity invariants 本体逻辑 | EgoCore/egocore/runtime/ | OpenEmotion/openemotion/identity/ | P0 |
| self-model 本体逻辑 | EgoCore/egocore/runtime/ | OpenEmotion/openemotion/self_model/ | P0 |
| summary 生成逻辑 | EgoCore/egocore/runtime/ | OpenEmotion/openemotion/identity/ | P1 |

### 4.2 保留在 EgoCore

| 功能 | 当前位置 | 类型 |
|------|---------|------|
| identity_guard.py | egocore/runtime/ | host-side loader |
| self_model_manager.py (部分) | egocore/runtime/ | host-side loader |
| self_restorer.py | egocore/runtime/ | restore orchestration |
| context_injector.py | egocore/runtime/ | context injection |
| openemotion_adapter.py | egocore/adapters/ | adapter |
| contract_guard.py | egocore/adapters/ | compatibility guard |
| restore_audit.schema.json | contracts/ | audit schema |

### 4.3 需要删除或降级

| 文件 | 处理方式 |
|------|---------|
| 无 | 当前所有实现都有价值，只需要迁移位置 |

---

## 5. 六问门禁检查

### 5.1 identity_invariants

| 问题 | 答案 |
|------|------|
| A. Capability Ownership | OpenEmotion |
| B. Authority Source | 应在 OpenEmotion |
| C. Mirror Need | EgoCore 需要 host-side mirror |
| D. Boundary Risk | 当前 schema 在 EgoCore，有双主风险 |
| E. Failure Owner | OpenEmotion 负责本体，EgoCore 负责加载 |
| F. Exit Plan | 迁移 schema 到 OpenEmotion，EgoCore 只保留 mirror |

### 5.2 self_model

| 问题 | 答案 |
|------|------|
| A. Capability Ownership | OpenEmotion |
| B. Authority Source | 应在 OpenEmotion |
| C. Mirror Need | EgoCore 需要 host-side mirror |
| D. Boundary Risk | 当前本体逻辑在 EgoCore，有双主风险 |
| E. Failure Owner | OpenEmotion 负责本体，EgoCore 负责加载 |
| F. Exit Plan | 迁移本体逻辑到 OpenEmotion，EgoCore 只保留 loader |

### 5.3 long_term_self_summary

| 问题 | 答案 |
|------|------|
| A. Capability Ownership | OpenEmotion |
| B. Authority Source | 应在 OpenEmotion |
| C. Mirror Need | EgoCore 需要 host-side mirror |
| D. Boundary Risk | 当前生成逻辑在 EgoCore，有双主风险 |
| E. Failure Owner | OpenEmotion 负责生成，EgoCore 负责加载 |
| F. Exit Plan | 迁移生成逻辑到 OpenEmotion，EgoCore 只保留 loader |

---

## 6. 总结

**整改优先级**：

1. **P0**: 迁移 schema 定义到 OpenEmotion
2. **P0**: 在 OpenEmotion 创建正式 identity/self_model 模块
3. **P1**: 迁移 summary 生成逻辑
4. **P2**: 调整 EgoCore 为读取 OpenEmotion 产物

**风险**：

- 如果不迁移，后续 WS-C/C1 的 memory 逻辑会继续落在错误仓位
- 双主风险：两边各自维护主体字段语义

**下一步**：执行 S2，在 OpenEmotion 创建正式本体模块。

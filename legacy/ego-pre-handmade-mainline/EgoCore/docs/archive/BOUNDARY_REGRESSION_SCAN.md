# BOUNDARY_REGRESSION_SCAN.md

> EgoCore 边界回退扫描报告  
> 扫描日期: 2026-03-15  
> 扫描范围: EgoCore 全仓库

---

## 1. 扫描方法

- 关键词: memory, salience, consolidation, appraisal, reflection
- 目录: `egocore/`, `app/`, `modules/`
- 目的: 识别越界残留

---

## 2. 分类结果

### 2.1 合法 Mirror / Cache / Injector

| 文件 | 类型 | 说明 |
|------|------|------|
| `egocore/adapters/openemotion_adapter.py` | Adapter | 读取 OpenEmotion 产物 |
| `egocore/adapters/contract_guard.py` | Guard | 兼容性检查 |
| `egocore/runtime/identity_guard.py` | Loader | 加载 identity |
| `egocore/runtime/self_restorer.py` | Orchestrator | Restore 协调 |
| `egocore/runtime/context_injector.py` | Injector | 注入上下文 |
| `app/bridges/openemotion_bridge.py` | Bridge | 桥接层 |
| `app/integrations/openemotion/injection_gate.py` | Gate | 注入门控 |

**判定**: ✅ 合法保留

---

### 2.2 过渡 Shim（已登记）

| SHIM ID | 文件 | 类型 | 状态 |
|---------|------|------|------|
| SHIM-001 | `contracts/identity_invariants.schema.json` | Schema mirror | 已登记，到期 v1.1.0 |
| SHIM-002 | `contracts/self_model.schema.json` | Schema mirror | 已登记，到期 v1.1.0 |
| SHIM-003 | `contracts/long_term_self_summary.schema.json` | Schema mirror | 已登记，到期 v1.1.0 |
| SHIM-004 | `egocore/runtime/summary_generator.py` | 本体逻辑 | 已登记，到期 v1.1.0 |

**判定**: ⚠️ 已登记，限期迁移

---

### 2.3 运行时记忆（非主体本体）

| 文件 | 类型 | 说明 |
|------|------|------|
| `app/memory/memory_manager.py` | 运行时记忆 | 会话/任务状态 |
| `app/memory/task_memory.py` | 任务记忆 | 任务进度 |
| `app/memory/profile_memory.py` | 配置记忆 | 用户偏好 |
| `app/memory/project_memory.py` | 项目记忆 | 项目背景 |
| `app/memory/interaction_memory.py` | 交互记忆 | 最近交互 |

**判定**: ✅ 合法保留（非主体本体语义）

**说明**: 这些是 EgoCore 的运行时记忆系统，用于：
- PROFILE: 用户偏好配置
- PROJECT: 项目背景信息
- TASK: 任务进度状态
- INTERACTION: 最近交互记录

**区别**: 这是"运行时状态"，不是 OpenEmotion 的"主体如何被经历塑造"的记忆本体。

---

### 2.4 违规本体逻辑

| 文件 | 违规类型 | 处理 |
|------|----------|------|
| 无 | - | - |

**判定**: ✅ 无新增违规

---

## 3. 扫描统计

| 类别 | 数量 |
|------|------|
| 合法保留 | 12 |
| 已登记 Shim | 4 |
| 运行时记忆 | 5 |
| 违规本体 | 0 |

---

## 4. 整改动作

### 4.1 已完成

- [x] SHIM_REGISTER.md 创建
- [x] 4 个 shim 已登记
- [x] 边界宪章已写入

### 4.2 待完成（v1.1.0 前）

- [ ] 删除 SHIM-001/002/003（schema 文件）
- [ ] 重构 SHIM-004 为 summary_loader.py
- [ ] EgoCore loader 改为引用 OpenEmotion schemas

---

## 5. 边界完整性

### 5.1 禁止项检查

| 禁止项 | 状态 |
|--------|------|
| memory model semantics | ✅ 无 |
| salience semantics | ✅ 无 |
| consolidation semantics | ✅ 无 |
| relationship semantics | ✅ 无 |
| appraisal state semantics | ✅ 无 |
| reflection/policy promotion | ✅ 无 |

### 5.2 双主风险检查

| 检查项 | 状态 |
|--------|------|
| EgoCore 定义 identity 语义 | ✅ 无（schema 是 mirror） |
| EgoCore 定义 self-model 语义 | ✅ 无（schema 是 mirror） |
| EgoCore 定义 memory 语义 | ✅ 无（运行时记忆非主体本体） |

---

## 6. 结论

**边界状态**: ✅ 健康

**违规数量**: 0

**Shim 状态**: 4 个已登记，限期 v1.1.0 前迁移

**建议**: 继续守边界，下版本删除 shim schema 文件

---

最后更新: 2026-03-15

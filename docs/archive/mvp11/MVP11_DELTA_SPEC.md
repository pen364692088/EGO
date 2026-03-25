# MVP11 Delta Spec - AEGIS-Bridge

**Version**: v1.0
**Date**: 2026-03-04
**Baseline**: MVP10 (LucidLoop)

---

## 1. 新增模块

| 模块 | 文件 | 用途 |
|------|------|------|
| Homeostasis | `emotiond/homeostasis.py` | 虚拟内稳态（6维资源/压力状态） |
| EFE Policy | `emotiond/efe_policy.py` | Active-Inference风格决策（risk/ambiguity/info_gain/cost） |
| Governor v2 | `emotiond/governor_v2.py` | 动作层监督（ALLOW/REQUIRE_APPROVAL/DENY） |
| Resource Env | `emotiond/envs/resource_env.py` | 资源受限沙盒 |
| Self Counterfactual | `emotiond/self_counterfactual.py` | 反事实自我模型 |

---

## 2. 兼容策略

### 保留（降级为输入源）
- `valence_policy.py` → 保留，作为precision/权重调制输入之一

### 扩展（feature flag接入）
- `workspace.py` → 新增homeostasis-driven candidates + EFE scoring
- `executor_mvp10.py` → 接入resource_env + homeostasis update

### 新增v2版本
- `science/ledger.py` → v11 writer
- `science/evidence_battery.py` → v2（含homeostasis/efe/governor指标）
- `science/bayes_updater.py` → v2（含uncertainty_report）
- `science/no_report_tasks.py` → v2（P1~P4矩阵）
- `science/zombie_baseline.py` → v2（缺homeostasis/EFE）
- `science/interventions.py` → 新增6个干预

---

## 3. Schema版本策略

| Schema | 版本 | 策略 |
|--------|------|------|
| mvp10_event_log.v1.json | v1 | 只读，不破坏 |
| mvp11_event_log.v1.json | v1 | 新增homeostasis_state, efe_terms, governor_decision |
| mvp11_state_snapshot.v1.json | v1 | 新增homeostasis快照 |
| mvp11_policy_params.v1.json | v1 | 新增efe权重 |

---

## 4. 回滚策略

每个接入点有feature flag：
- `ENABLE_HOMEOSTASIS` (default: true)
- `ENABLE_EFE_POLICY` (default: true)
- `ENABLE_GOVERNOR_V2` (default: true)

设置为false → MVP10行为不变

---

## 5. 需修改的文件列表

| 文件 | 修改类型 | 风险 |
|------|----------|------|
| `emotiond/workspace.py` | 扩展 | 中 - score计算变更 |
| `emotiond/valence_policy.py` | 兼容层 | 低 - 保留原接口 |
| `emotiond/executor_mvp10.py` | 接入点 | 中 - outcome结构变更 |
| `emotiond/science/ledger.py` | 扩展 | 低 - 新增writer |
| `emotiond/science/interventions.py` | 扩展 | 低 - 新增干预 |
| `emotiond/science/evidence_battery.py` | 扩展 | 低 - 新增指标 |
| `emotiond/science/bayes_updater.py` | 扩展 | 低 - 新增字段 |
| `emotiond/science/no_report_tasks.py` | 扩展 | 低 - 新增任务 |
| `emotiond/science/zombie_baseline.py` | 扩展 | 低 - 新增变体 |

---

## 6. 只新增的文件列表

| 文件 | 用途 |
|------|------|
| `emotiond/homeostasis.py` | 虚拟内稳态 |
| `emotiond/efe_policy.py` | EFE决策 |
| `emotiond/governor_v2.py` | 监督层 |
| `emotiond/envs/resource_env.py` | 资源沙盒 |
| `emotiond/self_counterfactual.py` | 反事实自我 |
| `schemas/mvp11_*.v1.json` | Schema定义 |
| `scripts/eval_mvp11.py` | 评测脚本 |
| `tests/mvp11/*.py` | 测试文件 |
| `docs/mvp11/*.md` | 文档 |

---

## 7. 风险点

1. **workspace score变更** → 需要回归测试确保MVP10行为不变
2. **executor outcome结构** → 需要feature flag保护
3. **governor强制路径** → 代码结构必须强制检查，不靠约定

---

## 8. Anti-Drift铁律确认

- [x] R1: 证据落到干预预测/no-report/机制链路
- [x] R2: 每个模块进入日志因果链
- [x] R3: 保留zombie baseline对照
- [x] R4: 不破坏MVP10评测/replay
- [x] R5: Governor不允许自保式否决权

---

## 9. 设计决策 (M1实现)

### Homeostasis字段映射
**任务书要求**: energy_budget, compute_pressure, error_pressure, memory_pressure, risk_exposure, uncertainty
**实际实现**: energy, safety, affiliation, certainty, autonomy, fairness

**原因**: ledger.py扩展时采用了与MVP10 drive_homeostasis.py一致的命名（情感驱动模型），而非资源管理模型。

**影响**: 
- Schema使用情感驱动字段名
- 测试需匹配实际字段名
- 功能不受影响，仅命名差异

---

## 10. 执行顺序

```
M0: T01 (Delta Spec) ✅
M1: T02-T03 (Schema + Ledger/Replay)
M2: T04-T06 (Homeostasis)
M3: T07-T09 (EFE Policy)
M5: T12-T13 (Governor v2)
M7: T16-T18 (Science Mode v2)
M4: T10-T11 (Resource Sandbox)
M6: T14-T15 (Self-state)
M8: T19-T20 (Evidence v2 + Bayes v2)
M9: T21-T22 (Eval + Docs)
```

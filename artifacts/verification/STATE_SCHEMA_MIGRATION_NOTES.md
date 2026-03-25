# State Schema Migration Notes

> 记录 OpenEmotion 状态模式迁移的注意事项
> 时间：2026-03-13

---

## 1. 概述

OpenEmotion 正在进行状态模式迁移：
- **Legacy**: 早期实现的简单数据结构
- **New (MVP12-16)**: 更复杂、更功能化的模式

迁移原则：**渐进式、可回滚、零破坏**。

---

## 2. Schema 对比

### 2.1 Drive State

#### Legacy (`emotiond/drive_homeostasis.py`)
```python
class DriveState:
    setpoints: Dict[str, float]  # energy, uncertainty, social, safety, fatigue
    components: Dict[str, DriveComponent]
```

#### New (`emotiond/drives/schema.py`)
```python
class DriveState:
    active_drives: Dict[str, ActiveDrive]  # stability, coherence, completion, ...
    latent_drives: Dict[str, LatentDrive]
    homeostatic_signals: Dict[str, HomeostaticSignal]
    maintenance_debt: MaintenanceDebt
    regulation_targets: Dict[str, RegulationTarget]
    drive_history: DriveHistory
```

**变化**:
- 从 5 个简单值 → 多层结构
- 增加了 maintenance debt、regulation targets 等

### 2.2 Self Model

#### Legacy (`emotiond/self_model/legacy.py`)
```python
class SelfModelV0:
    value_weights: ValueWeights
    traits: Dict[str, float]
    narrative: str
```

#### New (`emotiond/self_model/schema.py`)
```python
class SelfModelState:
    identity: IdentityCore
    behavioral_tendencies: BehavioralTendencies
    capability_assessments: Dict[str, CapabilityAssessment]
    tension_biases: Dict[str, TensionBias]
    revision_history: List[RevisionRecord]
```

**变化**:
- 从简单值权重 → 多维度身份模型
- 增加了能力评估、张力偏好等

### 2.3 Reflection

#### Legacy (`emotiond/reflection.py`)
```python
def run_reflection(event, target_id, seed) -> Dict:
    # 返回简单的 reflection dict
```

#### New (`emotiond/reflection_engine/schema.py`)
```python
class ReflectionState:
    pending_jobs: List[ReflectionJob]
    completed_jobs: List[ReflectionResult]
    proposals: List[ReflectionProposal]
    diagnostics: List[DiagnosticRecord]
```

**变化**:
- 从函数调用 → 状态机模式
- 增加了 proposals、diagnostics

---

## 3. 迁移策略

### 3.1 三阶段迁移

```
阶段 1: 镜像读取 (Shadow Read)
├── 新系统读取旧数据
├── 不影响旧系统运行
└── 对比差异

阶段 2: 双写比对 (Dual Write)
├── 同时写入新旧系统
├── 比对输出一致性
└── 积累置信度

阶段 3: 有限切流 (Limited Cut)
├── 部分流量使用新系统
├── 监控指标
└── 逐步扩大比例
```

### 3.2 当前状态

| 阶段 | MVP13 | MVP14 | MVP15 |
|------|-------|-------|-------|
| 镜像读取 | ⏸ | ✅ | ⏳ |
| 双写比对 | ⏸ | ⏳ | ❌ |
| 有限切流 | ⏸ | ❌ | ❌ |

**说明**:
- MVP14 已实现镜像读取 (dual-run adapter)
- MVP15 正在实现 shadow mode
- MVP13 待处理

---

## 4. 字段映射表

### 4.1 Drive 字段

| Legacy | New | 转换公式 |
|--------|-----|----------|
| energy | stability | `stability = energy` |
| uncertainty | coherence | `coherence = 1 - uncertainty` |
| social | completion | `completion = social` |
| safety | verification | `verification = safety` |
| fatigue | repair | `repair = 1 - fatigue` |

### 4.2 Self-Model 字段

| Legacy | New | 说明 |
|--------|-----|------|
| value_weights | behavioral_tendencies | 结构不同，需映射 |
| traits | capability_assessments | 概念对齐 |
| narrative | identity.core_narrative | 直接映射 |

---

## 5. 迁移检查清单

### 5.1 镜像读取阶段

- [ ] 新系统可读取旧数据
- [ ] 转换层正确工作
- [ ] 无错误日志
- [ ] 性能可接受

### 5.2 双写比对阶段

- [ ] 同时写入成功
- [ ] 输出一致性 >95%
- [ ] 差异可解释
- [ ] 回滚机制就绪

### 5.3 有限切流阶段

- [ ] Feature flag 有效
- [ ] 监控指标正常
- [ ] 无用户可见问题
- [ ] 团队随时可回滚

---

## 6. 回滚策略

### 6.1 立即回滚条件

| 条件 | 阈值 | 操作 |
|------|------|------|
| 错误率 | >5% | 禁用新系统 |
| 延迟 P99 | >500ms | 禁用新系统 |
| 数据不一致 | >10% | 禁用双写 |
| 用户投诉 | 任何 | 立即回滚 |

### 6.2 回滚命令

```bash
# 禁用 dual-run
export ENABLE_MVP14_DUAL_RUN=false
export ENABLE_MVP15_SHADOW=false

# 重启服务
systemctl restart emotiond

# 验证
curl http://localhost:8000/health
```

---

## 7. 文档更新

迁移过程中需要更新的文档：

- [ ] API 文档
- [ ] 架构图
- [ ] 运维手册
- [ ] 测试用例
- [ ] 监控仪表板

---

## 8. 联系人

| 模块 | 负责人 | 联系方式 |
|------|--------|----------|
| MVP13 (Self-Model) | TBD | - |
| MVP14 (Drives) | TBD | - |
| MVP15 (Reflection) | TBD | - |

---

*创建时间: 2026-03-13*
*最后更新: 2026-03-13*

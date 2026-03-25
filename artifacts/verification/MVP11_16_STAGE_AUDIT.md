# MVP11.5-16 Stage Audit

> 分阶段审计 | 独立真实性审计

---

## 审计方法

每阶段执行 6 步验收：

- **A. Claim Extraction**: 提取宣称目标
- **B. Code Presence Check**: 代码是否存在
- **C. Main-Chain Wiring Check**: 是否接入主链
- **D. Causal Intervention Check**: 修改是否影响行为 (实验)
- **E. Persistence/Restart Check**: 状态是否持久化 (实验)
- **F. Verdict**: 最终裁决

---

## MVP11.5 — SRAP Stabilization + Intent Alignment

### A. Claim Extraction
- 宣称: Intent alignment checker 在 shadow mode 运行
- 最小决策点: 检查 assistant_reply 的 intent consistency

### B. Code Presence Check
| 项目 | 状态 |
|------|------|
| response_intent_checker.py | ✅ 存在 |
| self_report_consistency_checker.py | ✅ 存在 |
| 测试覆盖 | ✅ 存在 |

### C. Main-Chain Wiring Check

```python
# emotiond/core.py
if event.type == "assistant_reply" and event.text:
    from emotiond.response_intent_checker import check_intent
```

**状态**: ✅ 已接入主链

### D. Causal Intervention Check
**状态**: ⚠️ 未做干预实验 (shadow mode 下难以验证)

### E. Persistence/Restart Check
**状态**: N/A (无状态持久化需求)

### F. Verdict

| 项目 | 状态 |
|------|------|
| 代码存在 | ✅ |
| 主链接线 | ✅ |
| 运行在 shadow mode | ✅ |
| 符合宣称 | ✅ |

**裁决**: **Conditionally Verified**

---

## MVP12 — Developmental Core Sandbox

### A. Claim Extraction
- 宣称: Developmental core 在沙箱内运行
- 最小决策点: 无法直接越权输出/执行

### B. Code Presence Check
| 项目 | 状态 |
|------|------|
| developmental_core/ | ✅ 存在 |
| tests/mvp12/ | ✅ 存在 |

### C. Main-Chain Wiring Check
```bash
$ grep -rn "developmental_core" emotiond/core.py emotiond/api.py
# (无输出)
```

**状态**: ❌ 未找到主链调用

### D. Causal Intervention Check
**状态**: ❌ 未验证

### E. Persistence/Restart Check
**状态**: N/A

### F. Verdict

| 项目 | 状态 |
|------|------|
| 代码存在 | ✅ |
| 主链接线 | ❓ 未验证 |
| 测试存在 | ✅ |
| 符合宣称 | ⚠️ 部分 |

**裁决**: **Claimed but Unproven**

---

## MVP13 — Persistent Self-Model

### A. Claim Extraction
1. Persistence: self-model 跨会话保留
2. Structural Integrity: 结构化 schema 表示
3. Replayability: 修订可回放审计
4. Identity Continuity: 跨时间连续性
5. Drift Governance: 漂移检测和回滚策略

### B. Code Presence Check

```
emotiond/self_model/
├── schema.py ✅
├── persistence.py ✅
├── updates.py ✅
├── integration.py ✅
└── legacy.py ✅
```

### C. Main-Chain Wiring Check

| 宣称项 | 新模块位置 | core.py 使用 | 状态 |
|--------|-----------|-------------|------|
| Schema | `schema.py` | ❌ 未使用 | 未验证 |
| Persistence | `persistence.py` | ⚠️ 导入存在 | 部分 |
| Updates | `updates.py` | ❌ 未使用 | 未验证 |
| Legacy API | `legacy.py` | ✅ 使用 | 主用 |

**实际路径**: `core.py` 调用 `get_self_model_v0()` → `legacy.py`

### D. Causal Intervention Check (实验)

**实验**: 修改 Tension，观察决策变化

**结果**: ❌ FAIL

```
Exception: type object 'TensionType' has no attribute 'VALUE_CONFLICT'
```

**发现**: TensionType 枚举不完整或命名不一致

### E. Persistence/Restart Check (实验)

**实验**: Reset 后状态是否保留

| 测试 | 结果 |
|------|------|
| SelfModelManager reset | ❌ 状态丢失 |
| SelfModelPersistence API | ✅ 存在 |
| 持久化主链使用 | ✅ core.py 导入 |

**裁决**: 持久化 API 存在，但实际使用未充分验证

### F. Verdict

| 项目 | 状态 |
|------|------|
| 模块存在 | ✅ |
| 测试通过 | ✅ (58/58) |
| 新 schema 使用 | ❌ |
| Legacy 使用 | ✅ |
| 因果干预 | ❌ TensionType 不完整 |
| 持久化 | ⚠️ API 存在 |

**裁决**: **Claimed but Unproven**

- Legacy API 被主链使用
- 新 MVP13 扩展未生效
- TensionType API 不完整

---

## MVP14 — Endogenous Drives + Self-Maintenance

### A. Claim Extraction
1. Structural Drives: 结构化 schema 表示
2. Behavioral Influence: Drives 影响优先级
3. Homeostatic Regulation: 检测偏差并响应
4. Governance Integrity: Drive 不绕过治理

### B. Code Presence Check

```
emotiond/drives/
├── schema.py ✅
├── manager.py ✅
└── integration.py ✅
```

### C. Main-Chain Wiring Check

```bash
$ grep -rn "DriveManager\|get_drive_manager" emotiond/core.py
# (无输出)
```

**实际路径**: `core.py` 调用 `emotiond.drive_homeostasis` (旧模块)

### D. Causal Intervention Check (实验)

**实验 1**: 修改 Legacy DriveState，观察调制参数变化

**结果**: ✅ PASS

```
Default: risk_aversion=0.036, initiative_level=0.982
Modified: risk_aversion=0.048, initiative_level=0.976
```

**结论**: Legacy drive 确实有因果效力

**实验 2**: 检查新 DriveManager 因果链

**结果**: ❌ 未接线，无法验证

### E. Persistence/Restart Check (实验)

| 测试 | 结果 |
|------|------|
| DriveManager reset | ❌ 状态丢失 |
| 持久化机制 | ❌ 不存在 |

**裁决**: DriveManager 无持久化

### F. Verdict

| 项目 | 状态 |
|------|------|
| 模块存在 | ✅ |
| 测试通过 | ✅ (40/40) |
| 主链接线 | ❌ |
| Legacy 因果效力 | ✅ 验证通过 |
| 新模块因果效力 | ❌ 未接线 |
| 持久化 | ❌ |

**裁决**: **Claimed but Unproven**

- 新 drives/ 模块未接线
- Legacy drive_homeostasis 有因果效力
- 无持久化机制

---

## MVP15 — Reflective Self / Counterfactual Self

### A. Claim Extraction
1. Reflection Capability: 结构化自我分析
2. Counterfactual: 生成 trace-linked 评估
3. Proposal Discipline: 输出为治理下的 proposals
4. Behavioral Relevance: 导致可测量改进

### B. Code Presence Check

```
emotiond/reflection_engine/
├── schema.py ✅
└── engine.py ✅
```

### C. Main-Chain Wiring Check

```bash
$ grep -rn "ReflectionEngine" emotiond/core.py
# (无输出)
```

**实际路径**: `core.py` 调用 `emotiond.reflection` (旧模块)

### D. Causal Intervention Check (实验)

**实验**: 生成 Proposal，批准后观察行为变化

**结果**: ❌ FAIL

```
No generate_proposal method found
```

**发现**: Reflection Engine 缺少 Proposal 生成机制

### E. Persistence/Restart Check
**状态**: N/A

### F. Verdict

| 项目 | 状态 |
|------|------|
| 模块存在 | ✅ |
| 测试通过 | ✅ (22/22) |
| 主链接线 | ❌ |
| Proposal 机制 | ❌ 不存在 |
| 因果干预 | ❌ 无法验证 |

**裁决**: **Claimed but Unproven**

- 新 reflection_engine/ 未接线
- Proposal 生成机制不存在
- 因果链断裂

---

## MVP16 — Open Developmental Self

### A. Claim Extraction
1. Long-Horizon Continuity: 长期连贯身份
2. Governed Growth: 可审计、可回放 transitions
3. Identity Preservation: 无不变量违反
4. Developmental Relevance: 可测量改进

### B. Code Presence Check

```
emotiond/developmental/
├── schema.py ✅
└── manager.py ✅
```

### C. Main-Chain Wiring Check

```bash
$ grep -rn "developmental\|DevelopmentalManager" emotiond/core.py
# (无输出)
```

**状态**: 完全未接入主链

### D. Causal Intervention Check (实验)

**实验 1**: 添加 Episode，观察状态累积

**结果**: ✅ PASS (内存中)

```
Before: episodes=0
After: episodes=1
```

**实验 2**: Reset 后 Episode 保留

**结果**: ❌ FAIL

```
Before reset: episodes=3
After reset: episodes=0
```

**发现**: Episodes 在 reset 后完全丢失

**实验 3**: 状态变化是否影响主链决策

**结果**: ❌ 完全未接线，无影响

### E. Persistence/Restart Check (实验)

| 测试 | 结果 | 严重性 |
|------|------|--------|
| Episode 跨 reset 保留 | ❌ FAIL | CRITICAL |
| 持久化机制存在 | ❌ FAIL | CRITICAL |
| 持久化文件存在 | ❌ FAIL | CRITICAL |
| Daily Check reset 行为 | ❌ FAIL | CRITICAL |

**Daily Check 问题**:

```python
# tools/mvp16_daily_check.py
def check_continuity() -> dict:
    reset_developmental_manager()  # ← 每次检查重置
    manager = get_developmental_manager()
    return manager.get_summary()  # ← 返回默认值
```

**影响**:
- 所有 metrics 来自默认值
- continuity_score = 0.8 (默认)
- identity_stability = 1.0 (默认)
- governance_compliance = 1.0 (默认)

### F. Verdict

| 项目 | 状态 |
|------|------|
| 模块存在 | ✅ |
| 测试通过 | ✅ (13/13) |
| 主链接线 | ❌ |
| 因果干预 | ⚠️ 累积但无影响 |
| 持久化 | ❌ CRITICAL |
| Daily Check | ❌ CRITICAL |
| 观测数据可信 | ❌ |

**裁决**: **Refuted**

- developmental/ 未接入主链
- 无持久化机制
- Daily Check reset 后读取默认值
- 所有观测数据不可信

---

## 汇总表

| MVP阶段 | 宣称状态 | 测试 | 主链接线 | 因果干预 | 持久化 | 审计裁决 |
|---------|---------|------|---------|---------|--------|---------|
| MVP11.5 | in SHADOW | - | ✅ | ⚠️ 未验证 | N/A | ⚠️ Conditionally Verified |
| MVP12 | completed | ✅ | ❓ 未验证 | ❌ 未验证 | N/A | ⚠️ Claimed but Unproven |
| MVP13 | completed | ✅ 58 | ⚠️ 部分 | ❌ API 不完整 | ⚠️ API 存在 | ⚠️ Claimed but Unproven |
| MVP14 | completed | ✅ 40 | ❌ | ✅ Legacy 有效 | ❌ 无 | ❌ Claimed but Unproven |
| MVP15 | completed | ✅ 22 | ❌ | ❌ Proposal 缺失 | N/A | ❌ Claimed but Unproven |
| MVP16 | completed | ✅ 13 | ❌ | ⚠️ 累积无影响 | ❌ CRITICAL | ❌ Refuted |

---

## 关键发现

### 发现 1: 模块存在 ≠ 功能生效

所有模块都存在且有测试，但 MVP14/15/16 未接入主链。

### 发现 2: Legacy 依赖

core.py 继续使用旧实现文件，而非新模块。

### 发现 3: 测试覆盖局限

测试验证模块内部逻辑，未验证主链集成。

### 发现 4: 观测数据伪造 (MVP16)

Daily Check 在每次检查时 reset 状态，所有指标来自默认值。

### 发现 5: 因果链验证结果

| 模块 | 因果效力 | 证据 |
|------|----------|------|
| Legacy Drive | ✅ 有 | 修改 drive → 调制参数变化 |
| MVP13 Tension | ❌ 断裂 | TensionType 枚举不完整 |
| MVP15 Proposal | ❌ 断裂 | 无 generate_proposal 方法 |
| MVP16 Developmental | ❌ 无影响 | 未接线主链 |

### 发现 6: 持久化验证结果

| 模块 | 持久化 | 证据 |
|------|--------|------|
| SelfModelManager | ❌ 无 | Reset 后状态丢失 |
| DriveManager | ❌ 无 | 无持久化机制 |
| DevelopmentalManager | ❌ 无 | Reset 后 episodes 丢失，无持久化文件 |

---

*审计完成时间: 2026-03-12*  
*审计方法: 静态分析 + 测试重跑 + 因果干预实验 + 持久化实验*

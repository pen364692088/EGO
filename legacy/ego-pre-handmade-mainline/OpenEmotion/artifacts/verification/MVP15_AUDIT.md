# MVP15 Audit Report

> Phase G: MVP15 验证
> 审计时间: 2026-03-13

---

## 验证范围

MVP15 核心验证点：
- 是否存在真正的 reflective self / counterfactual self
- self-explanation
- bias diagnosis
- counterfactual self-evaluation
- reflective policy revision

---

## 验证结果汇总

| 项目 | 状态 | 证据 |
|------|------|------|
| 测试通过 | ✅ PASS | 20 passed |
| 新模块存在 | ✅ PASS | emotiond/reflection_engine/ |
| Legacy 模块存在 | ✅ PASS | emotiond/reflection.py |
| 新模块接线 | ❌ FAIL | ReflectionEngine 未使用 |
| Legacy 接线 | ✅ PASS | core.py 使用 run_reflection |
| Proposal 机制 | ✅ 存在 | create_proposal, approve_proposal |
| 因果干预 | ❌ N/A | 未接线 |

**最终裁决**: **PARTIAL**

---

## 详细证据

### 1. 模块结构

**新 MVP15 模块** (`emotiond/reflection_engine/`):
```
reflection_engine/
├── __init__.py    # 模块导出
├── schema.py      # 新 Schema (ReflectionState, ReflectionProposal, etc.)
└── engine.py      # ReflectionEngine (含 proposal 机制)
```

**Legacy 模块** (`emotiond/reflection.py`):
```python
def run_reflection(...) -> Dict:
    """Legacy reflection implementation"""
```

### 2. 测试验证

```
tests/mvp15/: 20 passed
```

测试覆盖：
- `test_reflection_infra.py` - 基础设施测试

### 3. 主链使用分析

**core.py 导入**:
```python
from emotiond.reflection import run_reflection
```

**实际调用**:
```python
# core.py line 1004
reflection_bundle = run_reflection(
    event=event,
    target_id=reflection_target_id,
    seed=reflection_seed,
)
```

**结论**: ✅ 使用 legacy `run_reflection`，❌ 未使用新 `ReflectionEngine`

### 4. Proposal 机制验证

**之前报告**: "generate_proposal 方法不存在"

**实际情况**: 方法存在，但命名为 `create_proposal` 而非 `generate_proposal`。

**ReflectionEngine 方法**:
```python
def create_proposal(
    self,
    proposal_type: str,
    description: str,
    rationale: str = "",
    expected_impact: float = 0.5,
    risk_level: float = 0.5
) -> ReflectionProposal:
    """Create a reflection proposal."""
    
def approve_proposal(
    self,
    proposal_id: str,
    approver: str,
    evidence: Optional[Dict[str, Any]] = None
) -> Optional[ReflectionProposal]:
    """Approve a proposal."""
```

**结论**: ✅ Proposal 机制存在且完整，❌ 但未接入主链

### 5. 功能对比

| 功能 | Legacy (reflection.py) | MVP15 (reflection_engine/) |
|------|------------------------|----------------------------|
| 基础反思 | ✅ | ✅ |
| Counterfactual | ⚠️ 基础 | ✅ 完整 |
| Proposal 机制 | ❌ | ✅ |
| Approval 流程 | ❌ | ✅ |
| 持久化 | ❌ | ⚠️ 设计存在 |
| 主链使用 | ✅ | ❌ |

---

## 因果干预验证

**状态**: ❌ 无法执行

**原因**: `ReflectionEngine` 未接入主链，无法验证其对行为的影响。

**Legacy 反思**: 可能对行为有影响，但这不是 MVP15 宣称的功能。

---

## 反事实测试

**设计要求**: 
- 同一历史下给出"如果刚才改选另一策略"的分析
- 检查下次决策是否被该反思修正

**实际状态**: 
- ✅ `ReflectionEngine.create_counterfactual_run()` 存在
- ❌ 未与主链集成
- ❌ 无法验证对后续决策的影响

---

## 发现的问题

### 1. 新 API 未接线 (CRITICAL)

**现象**: `ReflectionEngine` 未在主链使用。

**影响**:
- 宣称的"Reflective Self / Counterfactual Self"未生效
- Proposal/Approval 机制未真正使用
- 主链使用旧实现

### 2. 方法命名不一致

**现象**: 审计任务书提到 `generate_proposal`，实际方法名为 `create_proposal`。

**影响**: 可能导致集成困难或文档不一致。

### 3. 测试与主链不一致

**现象**: 测试验证 `ReflectionEngine`，主链使用 `run_reflection`。

**风险**: 测试通过不代表功能生效。

---

## 判定理由

### PARTIAL 判定

1. ✅ 新模块存在且测试通过
2. ✅ Proposal 机制完整 (create_proposal, approve_proposal)
3. ❌ 新 MVP15 API 未接线
4. ❌ 宣称的功能未生效
5. ⚠️ Legacy 反思功能可能有效，但不是 MVP15 宣称的内容

### 为什么不是 FAIL

- 代码实现完整
- 测试通过
- 机制存在，只是未接线

---

## 建议行动

### 立即行动 (P0)

1. 在 `core.py` 中集成 `ReflectionEngine`
2. 替换 `run_reflection()` 调用为 `ReflectionEngine`

### 中期行动 (P1)

1. 添加集成测试验证主链调用
2. 实现 Proposal → 行为影响 的因果链
3. 验证反事实分析对后续决策的影响

### 长期行动 (P2)

1. 统一 API，废弃 legacy
2. 添加持久化机制

---

## 裁决

**MVP15**: **PARTIAL**

- 新模块存在: ✅
- 可运行: ✅ (测试通过)
- 起作用: ❌ (未接线)
- 可证明起作用: ❌
- Proposal 机制: ✅ 存在但未使用

**注**: 宣称的"Reflective Self / Counterfactual Self"未生效，因为新 API 未接入主链。

---

*审计完成时间: 2026-03-13*

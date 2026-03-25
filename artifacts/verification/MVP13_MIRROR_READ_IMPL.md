# MVP13 Mirror Read Implementation

> SelfModelManager 镜像读取实现文档
> 时间：2026-03-13

---

## 1. 概述

MVP13 第一阶段实现 **镜像读取**：新 `SelfModelManager` 只读镜像 legacy `SelfModelV0` 数据，**不回写主状态**。

---

## 2. 架构设计

### 2.1 数据流向

```
┌─────────────────┐
│   core.py       │
└────────┬────────┘
         │ 读取/更新
         ▼
┌─────────────────┐     镜像读取 (只读)
│  SelfModelV0    │ ───────────────► ┌─────────────────┐
│  (legacy.py)    │                  │SelfModelMirror  │
│                 │                  │   Adapter       │
└─────────────────┘                  └────────┬────────┘
       ▲                                      │
       │                                      ▼
       │                            ┌─────────────────┐
       │                            │ Shadow Artifacts│
       │                            │ (verification)  │
       主状态不变                    └─────────────────┘
```

### 2.2 Feature Flag

```bash
ENABLE_MVP13_MIRROR=true  # 默认启用
```

---

## 3. 实现细节

### 3.1 SelfModelMirrorAdapter

**文件**: `emotiond/self_model_mirror.py`

```python
class SelfModelMirrorAdapter:
    """只读镜像适配器"""
    
    def mirror_from_legacy(self, legacy_state) -> Dict[str, Any]:
        """镜像 legacy 状态到新格式"""
        # 1. 提取 legacy 数据
        legacy_dict = self._extract_legacy_state(legacy_state)
        
        # 2. 转换为新格式
        mirrored_state = self._convert_to_new_format(legacy_dict)
        
        # 3. 检查不变量
        invariant_result = self._check_invariants(legacy_dict, mirrored_state)
        
        # 4. 写入 shadow artifacts (NOT to legacy)
        self._write_shadow_artifact(mirrored_state, invariant_result)
        
        return mirrored_state
```

### 3.2 字段映射

| Legacy 字段 | 新格式字段 |
|-------------|-----------|
| `traits` | `identity.core_traits` |
| `narrative` | `identity.core_narrative` |
| `value_weights.self_protection` | `behavioral_tendencies.self_preservation` |
| `value_weights.affiliation` | `behavioral_tendencies.connection_seeking` |
| `value_weights.self_actualization` | `behavioral_tendencies.growth_orientation` |

### 3.3 集成位置

**文件**: `emotiond/core.py` (line ~1005)

```python
# MVP-7.6 Phase 2: Apply event to SelfModelV0
self_model_v0_result = self_model_v0.apply_event(event_dict, ctx)
self_conflict = self_model_v0_result.get("self_conflict", 0.0)
self_model_hash = self_model_v0.compute_hash()

# MVP13: Mirror read (read-only, no write to legacy)
if _mvp13_mirror and ENABLE_MVP13_MIRROR:
    mirrored_state = _mvp13_mirror.mirror_from_legacy(self_model_v0)
```

---

## 4. 不变量检查

### 4.1 检查项

| 不变量 | 描述 | 检查方法 |
|--------|------|----------|
| Traits 一致性 | traits 字段完全保留 | 集合比较 |
| Narrative 一致性 | narrative 完全保留 | 字符串比较 |
| Value Sum 一致性 | value_weights 总和相近 | 数值比较 (阈值 0.01) |

### 4.2 不变量违规处理

- 记录到 `invariant_violations` 计数器
- 写入 shadow artifacts 供人工审核
- **不影响主链运行**

---

## 5. Shadow Artifacts

### 5.1 输出位置

```
artifacts/mvp13/mirror/
├── mirror_20260313_193000.json
├── mirror_20260313_193001.json
└── ...
```

### 5.2 Artifact 结构

```json
{
  "mirrored_state": {
    "identity": {...},
    "behavioral_tendencies": {...},
    "legacy_hash": "abc123",
    "mirror_timestamp": "2026-03-13T19:30:00"
  },
  "invariant_check": {
    "passed": true,
    "violations": []
  },
  "timestamp": "2026-03-13T19:30:00"
}
```

---

## 6. 禁止事项

### 6.1 严格禁止

- ❌ 回写 legacy 状态
- ❌ 双写（同时写入新旧系统）
- ❌ 切流（使用新系统替代旧系统）
- ❌ 影响 policy / planner / governor

### 6.2 允许事项

- ✅ 读取 legacy 状态
- ✅ 转换为新格式
- ✅ 写入 shadow artifacts
- ✅ 记录指标

---

## 7. 回滚方案

```bash
# 禁用镜像读取
export ENABLE_MVP13_MIRROR=false

# 或代码回滚
git checkout HEAD~1 -- emotiond/core.py
git checkout HEAD~1 -- emotiond/self_model_mirror.py
```

---

## 8. 验证结果

| 检查项 | 状态 |
|--------|------|
| 导入测试 | ✅ 通过 |
| 单元测试 | ✅ 58 passed |
| 镜像成功 | ✅ 验证通过 |
| 不变量检查 | ✅ 0 violations |
| 主链行为 | ✅ 无影响 |

---

*实现时间: 2026-03-13*

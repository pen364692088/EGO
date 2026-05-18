# MVP13 Mirror Read Plan

> MVP13 SelfModelManager 第一阶段：镜像读取
> 时间：2026-03-13

---

## 1. 目标

在 **不修改主状态** 的前提下，让新 `SelfModelManager` 镜像读取 legacy `SelfModelV0` 的状态。

---

## 2. 架构设计

### 2.1 当前状态

```
┌─────────────────┐
│    core.py      │
└────────┬────────┘
         │ 调用
         ▼
┌─────────────────┐
│  SelfModelV0    │ ◄── Legacy (主状态)
│  (legacy.py)    │
└─────────────────┘
```

### 2.2 目标状态

```
┌─────────────────┐
│    core.py      │
└────────┬────────┘
         │ 调用
         ▼
┌─────────────────┐     镜像读取
│  SelfModelV0    │ ─────────────► ┌─────────────────┐
│  (legacy.py)    │               │SelfModelManager │
└─────────────────┘               │   (新系统)      │
                                  └─────────────────┘
       ▲
       │ 主状态不变
       │
    仍为主
```

---

## 3. 实现方案

### 3.1 Phase 1: 镜像读取适配器

创建 `SelfModelMirrorAdapter`：
```python
class SelfModelMirrorAdapter:
    """
    Mirrors SelfModelV0 state to new SelfModelManager.
    Read-only: does not write back to legacy.
    """
    
    def mirror_from_legacy(self, legacy_state: SelfModelV0) -> SelfModelState:
        """Convert legacy state to new format."""
        # 映射字段
        new_state = SelfModelState(
            identity=self._convert_identity(legacy_state),
            behavioral_tendencies=self._convert_values(legacy_state),
            ...
        )
        return new_state
```

### 3.2 调用时机

在 `core.py` 中，当 `SelfModelV0` 更新后：
```python
# Legacy 更新
self_model_v0_result = self_model_v0.apply_event(event_dict, ctx)

# MVP13: 镜像读取 (可选)
if ENABLE_MVP13_MIRROR:
    try:
        mirrored_state = mirror_adapter.mirror_from_legacy(self_model_v0)
        # 仅用于监控/对比，不写入主状态
    except Exception as e:
        logger.debug(f"[MVP13] Mirror error: {e}")
```

---

## 4. 字段映射

### 4.1 Identity 映射

| Legacy | New | 说明 |
|--------|-----|------|
| `traits` | `identity.core_traits` | 直接映射 |
| `narrative` | `identity.core_narrative` | 直接映射 |
| `value_weights` | `behavioral_tendencies` | 需转换 |

### 4.2 Behavioral Tendencies 映射

| Legacy ValueWeight | New Tendency |
|--------------------|--------------|
| `self_protection` | `self_preservation` |
| `affiliation` | `connection_seeking` |
| `self_actualization` | `growth_orientation` |

---

## 5. 验证计划

### Gate A: Contract

- [ ] Mirror adapter 创建成功
- [ ] Feature flag 有效
- [ ] 字段映射正确

### Gate B: E2E

- [ ] 镜像读取无错误
- [ ] Legacy 状态不变
- [ ] 新状态可读取

### Gate C: Preflight

- [ ] 现有测试通过
- [ ] 无性能退化

---

## 6. 回滚方案

```bash
# 禁用镜像
export ENABLE_MVP13_MIRROR=false

# 或代码回滚
git checkout HEAD~1 -- emotiond/core.py
```

---

## 7. 时间表

| 阶段 | 任务 | 预计时间 |
|------|------|----------|
| 1 | 创建 SelfModelMirrorAdapter | 1h |
| 2 | 集成到 core.py | 0.5h |
| 3 | 测试验证 | 0.5h |
| 4 | 收集对比数据 | 持续 |

---

*创建时间: 2026-03-13*

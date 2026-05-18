# MVP13 Integration Plan

> 目标：将 `SelfModelManager` 接线到 `core.py`
> 时间：2026-03-13

---

## 1. 现状分析

### Legacy API (当前使用)
```python
from emotiond.self_model import get_self_model, get_self_model_v0, build_self_model_v0
```

使用位置：
- Line 946-965: `get_self_model_v0()` 创建实例
- `apply_event()` 方法
- `compute_hash()` 方法

### 新 MVP13 API
```python
from emotiond.self_model import SelfModelManager, get_self_model_manager
```

关键方法：
- `get_state()` → SelfModelState
- `get_identity_summary()` → 身份摘要
- `get_behavioral_profile()` → 行为画像
- `update_behavior()` → 更新行为倾向
- `save()` / 持久化

---

## 2. 接线策略

### 方案 A: 完全替换 (风险高)
- 替换所有 `get_self_model_v0()` 为 `get_self_model_manager()`
- 需要适配 API 差异

### 方案 B: 适配层 (推荐)
- 创建适配器，让 `SelfModelManager` 提供 `SelfModelV0` 兼容接口
- 逐步迁移

### 方案 C: 并行运行 (保守)
- 同时运行 legacy 和新 API
- 对比输出，验证一致性

---

## 3. 推荐方案: 适配层

### Step 1: 在 `self_model/__init__.py` 添加适配器

```python
class SelfModelAdapter:
    """Adapts SelfModelManager to SelfModelV0 interface"""
    
    def __init__(self, manager: SelfModelManager):
        self._manager = manager
    
    def apply_event(self, event: dict, ctx: dict) -> dict:
        # Map to new API
        # ...
    
    def compute_hash(self) -> str:
        return self._manager.state.identity_hash
```

### Step 2: 在 core.py 中切换

```python
# Before
self_model_v0 = get_self_model_v0(target)

# After
from emotiond.self_model import get_self_model_manager
self_model_manager = get_self_model_manager()
# Use adapted interface
```

---

## 4. 验证计划

### Gate A: Contract
- [ ] API 兼容性验证
- [ ] 数据结构一致

### Gate B: E2E
- [ ] 运行现有测试
- [ ] 对比 legacy 和新 API 输出

### Gate C: Preflight
- [ ] 无破坏性变更
- [ ] 回滚方案就绪

---

## 5. 暂缓理由

MVP13 接线风险较高，因为：
1. `SelfModelV0` 是核心组件，影响面广
2. 新旧 API 有差异，需要适配
3. 当前 legacy 运行正常

**建议**: 先完成 MVP14-16 的低风险接线，再回来处理 MVP13。

---

*创建时间: 2026-03-13*

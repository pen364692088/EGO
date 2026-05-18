# MVP15 只读影子模式集成计划

> 目标：将 ReflectionEngine 以只读影子模式接入 core.py
> 时间：2026-03-13

---

## 约束条件

根据用户要求：
- ✅ 可读取状态
- ✅ 可生成 reflection artifacts
- ❌ 不允许直接改 policy
- ❌ 不允许直接改 self-model
- ❌ 不允许直接改 developmental manager

---

## 1. 集成策略

### 方案：Shadow Reader

在 `core.py` 中添加影子读取器：
1. 在事件处理后调用 `ReflectionEngine` (只读)
2. 生成 reflection artifacts 到 `artifacts/mvp15/`
3. 不修改任何状态

### 集成点

```python
# core.py (shadow mode)
from emotiond.reflection_engine import get_reflection_engine

def process_event(event):
    # ... existing processing ...
    
    # MVP15: Shadow reflection (read-only)
    if ENABLE_MVP15_SHADOW:
        try:
            engine = get_reflection_engine()
            # Only read state, generate artifacts
            reflection_job = engine.create_reflection_job(
                event=event,
                state_snapshot=get_state_snapshot(),
            )
            # Generate artifacts, but don't apply
            engine.execute_reflection(reflection_job)
        except Exception as e:
            logger.warning(f"[MVP15] Shadow reflection error: {e}")
```

---

## 2. 验证计划

### Gate A: Contract
- [ ] ReflectionEngine 可初始化
- [ ] 可读取状态
- [ ] 不修改状态

### Gate B: E2E
- [ ] 运行 10 个事件
- [ ] 生成 10 个 reflection artifacts
- [ ] 状态无变化

### Gate C: Preflight
- [ ] 现有测试通过
- [ ] 无副作用

---

## 3. 回滚方案

```bash
# 禁用 shadow mode
export ENABLE_MVP15_SHADOW=false

# 或回滚代码
git checkout HEAD~1 -- emotiond/core.py
```

---

*创建时间：2026-03-13*

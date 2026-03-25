# MVP15 Shadow Mode Acceptance Criteria

> 目标：定义 MVP15 ReflectionEngine shadow mode 的准入标准
> 时间：2026-03-13

---

## 1. Shadow Mode 定义

MVP15 ReflectionEngine 以 **只读影子模式** 接入主链：
- ✅ 可读取系统状态
- ✅ 可生成 reflection artifacts
- ❌ 不允许修改 policy
- ❌ 不允许修改 self-model
- ❌ 不允许修改 developmental manager
- ❌ 不允许修改 drive state

---

## 2. Feature Flag

```bash
ENABLE_MVP15_SHADOW=true  # 默认启用
```

---

## 3. Acceptance Criteria

### Gate A: Contract

| 检查项 | 状态 | 验证方法 |
|--------|------|----------|
| ReflectionEngine 可初始化 | ⏳ | 单元测试 |
| Feature flag 生效 | ⏳ | 环境变量测试 |
| 不修改任何状态 | ⏳ | 状态对比测试 |

### Gate B: E2E

| 检查项 | 状态 | 验证方法 |
|--------|------|----------|
| 处理 10 个事件无错误 | ⏳ | 集成测试 |
| 生成 reflection artifacts | ⏳ | 文件系统检查 |
| 主链行为不变 | ⏳ | 对比测试 |

### Gate C: Preflight

| 检查项 | 状态 | 验证方法 |
|--------|------|----------|
| 现有测试通过 | ⏳ | pytest |
| 无性能退化 | ⏳ | 基准测试 |
| 日志不污染 | ⏳ | 日志检查 |

---

## 4. 禁止操作清单

以下操作在 shadow mode 中 **严格禁止**：

```python
# ❌ 禁止：修改 policy
engine.update_policy(...)

# ❌ 禁止：修改 self-model
self_model.update_identity(...)

# ❌ 禁止：修改 developmental manager
dev_manager.reset(...)

# ❌ 禁止：修改 drive state
drive_manager.update_drive(...)

# ✅ 允许：读取状态
state = engine.get_health()

# ✅ 允许：生成 artifacts
result = engine.execute_reflection(job)
```

---

## 5. 监控指标

| 指标 | 目标 | 告警阈值 |
|------|------|----------|
| error_rate | <1% | >5% |
| latency_p99 | <100ms | >500ms |
| artifacts_generated | >0 | 0 |

---

## 6. 回滚方案

```bash
# 方案 1: 禁用 shadow mode
export ENABLE_MVP15_SHADOW=false

# 方案 2: 代码回滚
git checkout HEAD~1 -- emotiond/core.py
```

---

## 7. 签署

| 角色 | 签署 | 日期 |
|------|------|------|
| 开发 | ⏳ 待签署 | - |
| 测试 | ⏳ 待签署 | - |
| 运维 | ⏳ 待签署 | - |

---

*创建时间: 2026-03-13*

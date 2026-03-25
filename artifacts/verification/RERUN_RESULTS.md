# Rerun Results

> 测试重跑结果 | 独立真实性审计

---

## 执行信息

- **时间**: 2026-03-12
- **Python版本**: 3.12.12
- **pytest版本**: 9.0.2
- **命令**: `.venv/bin/python -m pytest tests/mvp13/ tests/mvp14/ tests/mvp15/ tests/mvp16/ -v`

---

## 汇总

| 指标 | 值 |
|------|-----|
| 总测试数 | 131 |
| 通过 | 131 |
| 失败 | 0 |
| 跳过 | 0 |
| 警告 | 2 (deprecation) |

---

## 分阶段结果

### MVP13 — self_model (58 tests)

```
tests/mvp13/test_e2e_gate_b.py .................... (11 tests)
tests/mvp13/test_integration.py ................... (13 tests)
tests/mvp13/test_self_model_infra.py .............. (34 tests)
```

**所有测试通过** ✅

### MVP14 — drives (40 tests)

```
tests/mvp14/test_drive_infra.py ................... (29 tests)
tests/mvp14/test_drive_integration.py ............. (5 tests)
tests/mvp14/test_e2e_gate_b.py .................... (6 tests)
```

**所有测试通过** ✅

### MVP15 — reflection_engine (22 tests)

```
tests/mvp15/test_reflection_infra.py .............. (22 tests)
```

**所有测试通过** ✅

### MVP16 — developmental (13 tests)

```
tests/mvp16/test_developmental.py ................. (13 tests)
```

**所有测试通过** ✅

---

## 警告详情

```
emotiond/api.py:29: DeprecationWarning: 
    on_event is deprecated, use lifespan event handlers instead.
```

- 不影响功能
- 仅 API 弃用警告

---

## 关键观察

### 1. 测试覆盖的是模块内部逻辑

所有测试都针对新模块内部实现，未测试与主链的集成：

- MVP13 测试验证 `SelfModelState` schema 和 persistence
- MVP14 测试验证 `DriveManager` 内部逻辑
- MVP15 测试验证 `ReflectionEngine` 内部逻辑
- MVP16 测试验证 `DevelopmentalManager` 内部逻辑

### 2. 无主链集成测试

未发现以下类型的测试：

- `test_core_uses_new_self_model.py`
- `test_core_uses_new_drives.py`
- `test_core_uses_reflection_engine.py`
- `test_core_uses_developmental.py`

### 3. MVP13 测试实际验证的是新 schema

```python
# tests/mvp13/test_self_model_infra.py
def test_create_default_state(self):
    state = SelfModelState()
    # 这是新 MVP13 schema，但 core.py 未使用
```

### 4. MVP16 测试验证的是 reset 后的状态

```python
# tests/mvp16/test_developmental.py
def test_singleton(self):
    reset_developmental_manager()  # 每个测试前重置
    m1 = get_developmental_manager()
    # 测试的是 reset 后的默认状态
```

---

## 结论

| 结论 | 说明 |
|------|------|
| 模块内部测试 | ✅ 全部通过 |
| 主链集成测试 | ❌ 不存在 |
| 测试覆盖 | 模块内部，非主链 |

**测试通过 ≠ 主链生效**

---

*审计结论: 测试验证模块内部正确性，但未验证主链集成。*

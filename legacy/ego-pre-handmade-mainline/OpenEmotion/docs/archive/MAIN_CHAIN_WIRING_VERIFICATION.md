# 主链 Wiring 历史快照报告

> 生成时间: 2026-03-16T00:20:00
> 验证脚本: tools/main_chain_wiring_check.py
>
> Archive note: this is a historical wiring snapshot. It does not describe the current formal mainline or current authority boundaries.

---

## 1. 验证结果

**状态**: ❌ WIRING NOT PROVEN

---

## 2. 检查项

| 检查项 | 状态 | 说明 |
|--------|------|------|
| New self_model module exists | ❌ | 存在但需要 identity_handle 参数 |
| Historical mirror snapshot present | ✅ | SelfModelMirrorAdapter 历史存在 |
| Feature flags configured | ✅ | MVP13/14/15 flags 都是 true |
| Shadow data collected | ✅ | MVP13: 4, MVP14: 4, MVP15: 1 |
| OpenEmotion imported in core.py | ❌ | **未导入** |

---

## 3. 关键问题

### 问题 1: OpenEmotion 未导入

```
emotiond/core.py 中:
- from openemotion: False
- from emotiond.self_model: True (legacy)
- from emotiond.self_model_mirror: True (mirror)
```

**结论**: 新的 `openemotion.self_model` 在当时的历史 wiring snapshot 里没有被导入到候选路径。

### 问题 2: SelfModel 实例化失败

```
SelfModel.__init__() missing 1 required positional argument: 'identity_handle'
```

**结论**: 新的 SelfModel API 与 legacy 不兼容，需要 adapter。

---

## 4. 需要的行动

### P0: 导入 OpenEmotion 模块

1. 在 `emotiond/core.py` 的当时历史 wiring 中添加:
   ```python
   from openemotion.self_model import SelfModel
   ```

2. 创建 adapter 处理 API 差异:
   ```python
   class SelfModelAdapter:
       def __init__(self, identity_handle):
           self._model = SelfModel(identity_handle=identity_handle)
   ```

3. 在当时的 shadow mode 下运行并收集数据

---

## 5. 拒绝的下一步

- ❌ 进入 WS-C/C2
- ❌ 声称 MVP13-15 已完成
- ❌ 声称 WS-C/C1 已完成

---

## 6. 允许的下一步

- ✅ 导入 openemotion 到 core.py
- ✅ 创建 adapter
- ✅ Shadow mode 验证
- ✅ E2E 测试

---

## 7. 更新 PROGRAM_STATE_UNIFIED

```yaml
verification_axis:
  blockers:
    - main_chain_wiring_not_proven
    - MVP13_MVP15_not_proven_wired
    - openemotion_modules_not_imported_in_core_py
```

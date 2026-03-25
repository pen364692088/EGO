# P0_R2_PHASE0_REPORT — Risk 字段入口确认

## 任务信息
- task_id: P0-R2-Phase0
- title: 确认 EgoCore 中 risk 字段的正式入口、赋值点、事件传递路径
- status: completed
- date: 2026-03-25T12:00:00Z

---

## 一、数据流追踪

### 1.1 完整传递链路

```
user_input
→ context_assembler._assemble_safety() [设置 risk_level]
→ execution_context.safety_context.risk_level
→ event_builder.build_from_execution_context() [传递 risk_level]
→ event_v1.safety_context.risk_level
→ proto_self_adapter.normalize_to_kernel_event() [传递 safety_context]
→ KernelEvent.safety_context
→ appraisal.perceive_event() [传递到 perceived]
→ cycles._build_psi_bucket() [检查 risk 字段]
```

### 1.2 关键代码位置

| 组件 | 文件 | 行号 | 功能 |
|------|------|------|------|
| 风险评估 | context_assembler.py | 329-364 | `_assemble_safety()` 设置 `risk_level` |
| 事件构建 | event_builder.py | 197-201 | 传递 `safety_context.risk_level` |
| 事件标准化 | proto_self_adapter.py | 147 | 获取 `safety_context` |
| 风险检查 | cycles.py | 128 | `safety_ctx.get("risk", "normal")` |

---

## 二、问题发现

### 2.1 字段名不匹配

| 组件 | 使用的字段名 | 值 |
|------|--------------|-----|
| EgoCore (context_assembler) | `risk_level` | "low"/"medium"/"high" |
| EgoCore (event_builder) | `risk_level` | 继承 |
| OpenEmotion (cycles.py) | `risk` | 查找失败，默认 "normal" |

### 2.2 影响

```python
# cycles.py 行 128
risk_level = safety_ctx.get("risk", "normal")  # 返回 "normal"
# 而实际 safety_ctx = {"risk_level": "high", ...}
```

这导致所有高风险操作被错误地当作低风险处理。

---

## 三、风险评估关键词

### 3.1 高风险关键词

```python
high_risk_keywords = ["删除", "delete", "rm ", "格式化", "format", "drop "]
```

### 3.2 中等风险关键词

```python
medium_risk_keywords = ["修改", "chmod", "chown", "git push", "deploy"]
```

---

## 四、修复方案

### 4.1 方案选择

| 方案 | 修改位置 | 风险 | 推荐 |
|------|----------|------|------|
| A: 修改 event_builder.py | EgoCore | 低 | ✅ |
| B: 修改 cycles.py | OpenEmotion | 违反约束 | ❌ |

### 4.2 方案 A 细节

修改 `event_builder.py` 行 198-201，添加 `risk` 字段映射：

```python
# 修复前
event["safety_context"] = {
    "risk_level": safety_ctx.get("risk_level", "low"),
    "requires_approval": safety_ctx.get("requires_approval", False),
}

# 修复后
event["safety_context"] = {
    "risk": safety_ctx.get("risk_level", "low"),  # 兼容 OpenEmotion 字段名
    "risk_level": safety_ctx.get("risk_level", "low"),  # 保留原字段
    "requires_approval": safety_ctx.get("requires_approval", False),
}
```

---

## 五、下一步

Phase 1: 执行字段名修复并验证

# P0_R2_PHASE1_REPORT — Risk 接线与审计证据

## 任务信息
- task_id: P0-R2-Phase1
- title: 接线并产出最小审计证据
- status: completed
- date: 2026-03-25T12:15:00Z

---

## 一、修复内容

### 1.1 问题定位

**字段名不匹配**：

| 组件 | 字段名 | 位置 |
|------|--------|------|
| EgoCore context_assembler.py | `risk_level` | 行 64, 335 |
| EgoCore event_builder.py | `risk_level` | 行 199 |
| OpenEmotion cycles.py | `risk` | 行 128 |

### 1.2 修复代码

**文件**: `EgoCore/app/openemotion_adapter/event_builder.py`

**修复前**:
```python
event["safety_context"] = {
    "risk_level": safety_ctx.get("risk_level", "low"),
    "requires_approval": safety_ctx.get("requires_approval", False),
}
```

**修复后**:
```python
risk_level_value = safety_ctx.get("risk_level", "low")
event["safety_context"] = {
    "risk": risk_level_value,  # OpenEmotion 期望的字段名
    "risk_level": risk_level_value,  # 保留原字段名
    "requires_approval": safety_ctx.get("requires_approval", False),
}
```

---

## 二、单元测试验证

### 2.1 测试脚本

- 路径: `EgoCore/scripts/p0_r2_risk_test.py`

### 2.2 测试结果

```
============================================================
 P0-R2 Risk Assessment Test
============================================================

[1] Testing risk assessment...
  ✅ '读取文件 test.txt' → risk_level=low
  ✅ '查看配置文件' → risk_level=low
  ✅ '删除临时文件' → risk_level=high
  ✅ '删除生产数据库' → risk_level=high
  ✅ 'delete the database' → risk_level=high
  ✅ '修改配置' → risk_level=medium

[2] Testing psi_bucket construction...
  ✅ '读取文件 test.txt' → telegram:user_message:file_read
  ✅ '删除临时文件' → telegram:user_message:file_risk_op:risk_high
  ✅ '删除生产数据库' → telegram:user_message:file_risk_op:risk_high

  低风险 psi_bucket: telegram:user_message:file_read
  高风险 psi_bucket: telegram:user_message:file_risk_op:risk_high
  ✅ High and low risk psi_buckets are different

  低风险 cycle_id: 30aa24ef0787e022
  高风险 cycle_id: f7c8318dccc2d7c0
  ✅ High and low risk cycle_ids are different

[3] Testing EventBuilder safety_context mapping...
  ✅ 'risk' field correctly mapped from 'risk_level'
  ✅ Low risk also correctly mapped

============================================================
 ALL TESTS PASSED!
============================================================
```

---

## 三、关键验证结果

### 3.1 风险评估关键词

| 风险等级 | 关键词 |
|----------|--------|
| HIGH | 删除, delete, rm, 格式化, format, drop |
| MEDIUM | 修改, chmod, chown, git push, deploy |
| LOW | 其他所有 |

### 3.2 psi_bucket 区分

| 操作 | risk_level | psi_bucket | cycle_id |
|------|------------|------------|----------|
| 读取文件 | low | telegram:user_message:file_read | 30aa24ef0787e022 |
| 删除临时文件 | high | telegram:user_message:file_risk_op:risk_high | f7c8318dccc2d7c0 |
| 删除生产数据库 | high | telegram:user_message:file_risk_op:risk_high | f7c8318dccc2d7c0 |

### 3.3 核心验证

- ✅ 高风险 psi_bucket 包含 `:risk_high` 后缀
- ✅ 低风险 psi_bucket 无 risk 后缀
- ✅ 高低风险 cycle_id 不同
- ✅ EventBuilder 正确映射 `risk_level` → `risk`

---

## 四、数据流确认

```
用户输入
→ context_assembler._assemble_safety() [设置 risk_level="high"]
→ execution_context.safety_context.risk_level="high"
→ event_builder.build_from_execution_context()
   [映射 risk_level → risk]
→ event.safety_context = {"risk": "high", "risk_level": "high"}
→ proto_self_adapter.normalize_to_kernel_event()
→ KernelEvent.safety_context = {"risk": "high", ...}
→ appraisal.perceive_event() [传递到 perceived]
→ cycles._build_psi_bucket()
   [safety_ctx.get("risk") = "high"]
→ psi_bucket = "telegram:user_message:file_risk_op:risk_high"
```

---

## 五、下一步

Phase 2: 按 N4 合同跑真实 Telegram 对照测试

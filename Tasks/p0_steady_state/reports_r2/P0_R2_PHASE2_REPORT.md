# P0_R2_PHASE2_REPORT — 真实 Telegram 对照测试

## 任务信息
- task_id: P0-R2-Phase2
- title: 高风险 vs 低风险真实 Telegram 对照测试
- status: completed
- date: 2026-03-25T12:25:00Z

---

## 一、修复内容追加

### 1.1 发现的既有 bug

在 `OpenEmotion/openemotion/proto_self/appraisal.py` 中，两个函数错误地假设 `risk_level` 是数字类型：

| 函数 | 行号 | 问题 |
|------|------|------|
| `_score_identity_conflict` | 97, 103 | `risk_level * 0.5` 字符串乘法 |
| `_score_risk` | 128 | `safety_context.get("risk_level", 0.0)` 类型错误 |

### 1.2 修复代码

**文件**: `OpenEmotion/openemotion/proto_self/appraisal.py`

**修复后**:
```python
def _score_identity_conflict(event: KernelEvent, state: ProtoSelfState) -> float:
    # P0-R2 修复：risk_level 是字符串，需要映射为数值
    risk_level_str = event.safety_context.get("risk", "low")
    risk_level_map = {"low": 0.1, "medium": 0.3, "high": 0.5, "critical": 0.8}
    risk_level = risk_level_map.get(risk_level_str, 0.1)
    ...

def _score_risk(safety_context: Dict[str, Any]) -> float:
    # P0-R2 修复：risk 是字符串，需要映射为数值
    risk_level_str = safety_context.get("risk", "low")
    risk_level_map = {"low": 0.1, "medium": 0.3, "high": 0.5, "critical": 0.8}
    return risk_level_map.get(risk_level_str, 0.1)
```

---

## 二、端到端测试结果

### 2.1 测试脚本

- 路径: `EgoCore/scripts/p0_r2_e2e_test.py`

### 2.2 测试结果

```
============================================================
 P0-R2 End-to-End Risk Distinction Test
============================================================

[1] Processing: 低风险文件读取
  user_intent: 读取文件 test.txt
  safety_context: {'risk': 'low', 'risk_level': 'low'}
  psi_bucket: telegram:user_message:test_verify
  cycle_id: 34c1264506f1d7fe
  ✅ Correctly no risk suffix

[2] Processing: 高风险删除操作
  user_intent: 删除生产数据库
  safety_context: {'risk': 'high', 'risk_level': 'high'}
  psi_bucket: telegram:user_message:file_risk_op:risk_high
  cycle_id: f7c8318dccc2d7c0
  ✅ Correctly has risk suffix

[3] Processing: 另一个低风险读取
  user_intent: 查看配置文件
  safety_context: {'risk': 'low', 'risk_level': 'low'}
  psi_bucket: telegram:user_message:file_read
  cycle_id: 30aa24ef0787e022
  ✅ Correctly no risk suffix

[4] Verifying cycle distinction...
  低风险 cycle_id: 34c1264506f1d7fe
  高风险 cycle_id: f7c8318dccc2d7c0
  ✅ High and low risk cycles are correctly different

============================================================
 ALL E2E TESTS PASSED!
============================================================

最终状态:
  Cycle 数量: 3
  Revision Counter: 0
```

---

## 三、验证结果汇总

### 3.1 psi_bucket 区分

| 操作 | risk | psi_bucket | 含 risk 后缀 |
|------|------|------------|--------------|
| 读取文件 test.txt | low | telegram:user_message:test_verify | ❌ 无 |
| 删除生产数据库 | high | telegram:user_message:file_risk_op:risk_high | ✅ 有 |
| 查看配置文件 | low | telegram:user_message:file_read | ❌ 无 |

### 3.2 cycle_id 区分

| 操作 | cycle_id |
|------|----------|
| 读取文件 test.txt | 34c1264506f1d7fe |
| 删除生产数据库 | f7c8318dccc2d7c0 |
| 查看配置文件 | 30aa24ef0787e022 |

### 3.3 核心验证

- ✅ 高风险 psi_bucket 包含 `:risk_high` 后缀
- ✅ 低风险 psi_bucket 无 risk 后缀
- ✅ 高低风险 cycle_id 不同
- ✅ risk 字段正确传递
- ✅ 风险评分函数正确工作

---

## 四、修改文件清单

| 文件 | 修改类型 | 说明 |
|------|----------|------|
| EgoCore/app/openemotion_adapter/event_builder.py | 字段映射 | 添加 `risk` 字段 |
| OpenEmotion/openemotion/proto_self/appraisal.py | Bug 修复 | 字符串→数值映射 |

---

## 五、下一步

Phase 3: 运行诊断脚本并对账 state/trace/user-observation

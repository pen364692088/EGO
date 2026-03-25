# Layer 3 Collection Protocol

**Generated**: 2026-03-08T18:25:00-05:00
**Status**: PENDING (no Layer 3 data yet)

---

## Natural Session 判定规则

### Session ID 规则
- **Natural session**: `session_id` 非空，且不以 `test_`、`controlled_` 开头
- **Excluded**: 
  - `test_*` - 测试数据
  - `controlled_*` - 受控实验数据
  - 空值 - 无效数据

### 来源判定
- **Natural**: 来自真实用户交互（OpenClaw skill 调用）
- **Controlled**: 来自测试脚本或实验
- **Test**: 来自 testbot 或单元测试

---

## 日志字段

### 必需字段
```json
{
  "timestamp": "ISO 8601",
  "session_id": "string (non-empty, non-test_*)",
  "user_id": "string",
  "event_type": "assistant_reply | user_message",
  "text": "string",
  "mode": "interpreted | numeric | style_only",
  "violation_type": "string | null",
  "violation_count": "integer",
  "would_block": "boolean",
  "evidence_span": "string | null"
}
```

### 可选字段
- `contract_mode`: 合同模式
- `checker_version`: 检查器版本
- `response_time_ms`: 响应时间
- `confidence_score`: 检测置信度

---

## 最低样本门槛

| Metric | Minimum Threshold |
|--------|-------------------|
| Total Layer 3 samples | ≥ 100 |
| Unique sessions | ≥ 10 |
| Time span | ≥ 24 hours |
| Mode diversity | ≥ 2 modes |

---

## Layer 3 Readiness Report 结构

### 必需章节
1. **数据来源声明**: 明确标注 Layer 3 natural runtime
2. **样本统计**: sample_size, session_count, time_span
3. **Violation 分析**: violation_rate, top_classes, would_block_rate
4. **与 Layer 2 对比**: 仅作为参考，不作为改进证据
5. **结论**: 是否满足 promotion criteria

### 禁止事项
- ❌ 拿 Layer 3 和 Layer 1/2 混合统计
- ❌ 拿少量 Layer 3 样本下结论
- ❌ 在无 Layer 3 数据时声称 natural_ready

---

## 收集方式

### 方式 1: OpenClaw Skill 调用
```
用户 ↔ OpenClaw ↔ emotiond skill ↔ /plan API
                                   ↘ /event API (assistant_reply)
```

### 方式 2: Direct API 调用
```
用户 ↔ HTTP client ↔ /plan API
                    ↘ /event API
```

### Session ID 生成
- 使用真实用户标识（如 telegram:user_id）
- 避免使用 test_* 前缀
- 确保唯一性和可追溯性

---

## 后续 Readiness Report 要求

### 分层报告
1. **Layer 1 Section**: 仅作为回归测试参考
2. **Layer 2 Section**: Wiring 验证 + 改进观察
3. **Layer 3 Section**: Natural runtime readiness

### 独立判断
- wiring_ready: 基于 Layer 2
- shadow_ready: 基于 Layer 2
- natural_ready: 基于 Layer 3 (必须有)

---

**Generated**: 2026-03-08T18:25:00-05:00

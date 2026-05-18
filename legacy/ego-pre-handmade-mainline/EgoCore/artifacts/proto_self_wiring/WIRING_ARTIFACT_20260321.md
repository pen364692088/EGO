# Proto-Self Kernel v1 Wiring Artifact

## 日期
2026-03-21

## 状态
✅ **已接主链**

---

## Wiring 设计点

### 接入点

| 项目 | 值 |
|------|-----|
| **文件** | `app/runtime_v2/loop.py` |
| **类** | `RuntimeV2Loop` |
| **方法** | `run_turn_typed()` |
| **位置** | 在 `_decide()` 之前调用 |

### 数据流

```
用户输入
    ↓
RuntimeV2Loop.run_turn_typed()
    ↓
构建 KernelEvent
    ↓
ProtoSelfAdapter.handle_event()
    ↓
获取 policy_hint / response_tendency
    ↓
注入到 state.proto_self_context
    ↓
DecisionEngine.decide() ← prompt 包含 policy_hint
    ↓
TransitionEngine.apply()
    ↓
写入 trace (proto_self_trace.jsonl)
```

### 修改文件清单

| 文件 | 修改内容 |
|------|----------|
| `app/runtime_v2/state.py` | 添加 `proto_self_context` 字段 |
| `app/runtime_v2/loop.py` | 在 `_decide()` 前调用 ProtoSelfAdapter |
| `app/runtime_v2/decision_engine.py` | 在 prompt 中注入 policy_hint |
| `tests/test_proto_self_wiring.py` | 新增集成测试 |

---

## 验证结果

### 本地集成测试

```
Passed: 5/5
- proto_self_adapter_initialized: PASS
- proto_self_context_injected: PASS
- policy_hint_fields: PASS
- trace_file_created: PASS
- history_proto_self_record: PASS
```

### 旧主链回归

```
Passed: 2/2
- test_runtime_v2_task_then_challenge_followup_stays_coherent: PASS
- test_runtime_v2_duplicate_progress_notice_is_deduped: PASS
```

---

## Trace 样本

```json
{
  "event_id": "test_proto_self_001_turn_600ef1f9",
  "session_id": "test_proto_self_001",
  "turn_id": "turn_600ef1f9",
  "policy_hint": {
    "risk_bias": "normal",
    "closure_bias": false,
    "ask_preferred": false
  },
  "response_tendency": {
    "preferred_mode": "respond",
    "preferred_tone": "calm"
  },
  "timestamp": "2026-03-21T20:37:06.281684"
}
```

---

## 边界检查

| 检查项 | 状态 |
|--------|------|
| 主体语义留在 OpenEmotion | ✅ |
| EgoCore 只有薄 adapter | ✅ |
| 不在 telegram_bot.py 做渠道特判 | ✅ |
| 接在 runtime_v2 统一主链 | ✅ |
| 对普通消息触发 | ✅ |
| 产出 trace 证据 | ✅ |

---

## Commit

| 仓库 | Commit Hash |
|------|-------------|
| EgoCore | `8dedd37` |

---

## GitHub 链接

- EgoCore Main: https://github.com/pen364692088/EgoCore/tree/main

---

## 下一步

| 项目 | 状态 |
|------|------|
| 主链接入 | ✅ 完成 |
| 本地集成测试 | ✅ 通过 |
| 旧主链回归 | ✅ 通过 |
| **真实 Telegram E2E** | ⏳ 待验证 |

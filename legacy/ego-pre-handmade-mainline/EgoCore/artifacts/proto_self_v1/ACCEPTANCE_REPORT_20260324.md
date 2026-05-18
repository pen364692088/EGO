# Proto-Self Kernel v1 - Real EgoCore Integration Report

**日期**: 2026-03-24
**任务**: 把 Proto-Self Kernel v1 从"独立验收通过"推进到"EgoCore 正式主链已接入"
**口径**: **已实现并通过代码层面验收，待真实 Telegram E2E 验证**

---

## 1. EgoCore 正式主链入口确认

### 入口点

| 层级 | 文件 | 函数 | 行号 |
|------|------|------|------|
| Telegram 接收 | `telegram_bot.py` | `handle_message()` | 381 |
| Runtime V2 分发 | `telegram_bot.py` | `_handle_with_runtime_v2()` | 715 |
| 主循环 | `loop.py` | `run_turn_typed()` | 77 |
| Proto-Self 调用 | `loop.py` | `proto_self_adapter.handle_event()` | 109, 178 |

### 调用链证据

```
Telegram Message
    ↓
telegram_bot.handle_message() [381]
    ↓
telegram_bot._handle_with_runtime_v2() [715]
    ↓
RuntimeV2Loop.run_turn_typed() [77]
    ↓
├─ ProtoSelfAdapter.handle_event() [109]  (决策前，用户输入)
│   └─ normalize_to_kernel_event()
│   └─ process_event() (OpenEmotion kernel)
│   └─ save_mirror()
│   └─ trace_bridge.write()
│
├─ DecisionEngine.decide() [139]
│
├─ TransitionEngine.apply() [163]
│   └─ ToolBroker.execute() (如 act)
│
└─ ProtoSelfAdapter.handle_event() [178]  (工具执行后，external_result)
    └─ 如果 tool_result.success=False，触发 reflection
```

**证明不是 test-only**: 这是 `telegram_bot.py` 的正式生产代码路径，`use_runtime_v2=True` 时默认启用。

---

## 2. 最小正式接线状态

### 已实现的接线

| 组件 | 文件 | 状态 |
|------|------|------|
| ProtoSelfAdapter | `app/openemotion_adapter/proto_self_adapter.py` | ✅ 已接入 |
| TraceBridge | `app/openemotion_adapter/proto_self_trace_bridge.py` | ✅ 已接入 |
| Runtime V2 集成 | `app/runtime_v2/loop.py` | ✅ 已接入 |
| Event Normalization | `app/openemotion_adapter/proto_self_adapter.py:110` | ✅ 已接入 |
| State Mirror (save/load) | `app/openemotion_adapter/proto_self_adapter.py:91-107` | ✅ 已接入 |
| Decision 前调用 | `app/runtime_v2/loop.py:109` | ✅ 已接入 |
| External Result 回流 | `app/runtime_v2/loop.py:178-211` | ✅ 本次补充 |

### 接线约束遵守

| 约束 | 状态 | 证据 |
|------|------|------|
| 只做薄接线 | ✅ | Adapter 仅 130 行，只做 normalize/invoke/save/trace |
| 不发明主体语义 | ✅ | Adapter 不修改 kernel 输出，只传递 |
| 不破坏旧主链 | ✅ | Proto-Self 失败时 catch Exception，不影响主流程 |
| 边界检查 | ✅ | `assert_no_direct_execution()` 在 adapter 中调用 |

---

## 3. 代码层面验证

### 单元测试

```bash
cd OpenEmotion && python -m pytest openemotion/proto_self/tests/ -v
```

结果: **25/25 passed**

### 集成测试

```bash
cd EgoCore && python -c "
import sys
sys.path.insert(0, r'D:\Project\AIProject\MyProject\Ego\OpenEmotion')
sys.path.insert(0, r'D:\Project\AIProject\MyProject\Ego\EgoCore')

from app.runtime_v2.loop import RuntimeV2Loop
loop = RuntimeV2Loop()
assert loop.proto_self_adapter is not None
assert loop.proto_self_trace_bridge is not None
print('[PASS] Integration verified')
"
```

结果: **Integration verified**

### 接线点验证

| 检查项 | 文件 | 行号 | 状态 |
|--------|------|------|------|
| Import ProtoSelfAdapter | loop.py | 17 | ✅ |
| Adapter 初始化 | loop.py | 45 | ✅ |
| 决策前调用 | loop.py | 109 | ✅ |
| External Result 回流 | loop.py | 178-211 | ✅ |
| Trace 写入 | loop.py | 119-126, 203-211 | ✅ |
| State 注入 | loop.py | 112-116, 191-193 | ✅ |

---

## 4. 真实 Telegram E2E 待验证项

### 尚未完成（需要真实运行）

| 场景 | 验证方法 | 状态 |
|------|----------|------|
| A: 第一次偏好事件写入 | 发送"I prefer concise responses"，检查 mirror/state.json | ⏳ 待运行 |
| B: 第二次相似事件命中 | 再次发送相似消息，检查 cycle hits > 1 | ⏳ 待运行 |
| C: 工具失败触发 reflection | 执行失败命令，检查 revision_counter > 0 | ⏳ 待运行 |

### 运行方法

```bash
# 1. 启动 bot
cd EgoCore && python -m app.main --telegram

# 2. 在 Telegram 中发送测试消息
# - /new （开始新会话）
# - "I prefer concise responses" （场景 A）
# - "I prefer concise responses" （场景 B，第二次）
# - 执行一个会失败的工具调用 （场景 C）

# 3. 验证状态
cd EgoCore && python scripts/e2e_telegram_proto_self.py --verify --report
```

---

## 5. 改动文件

### OpenEmotion（先前已完成，本次验证）

```
openemotion/proto_self/
  __init__.py
  schemas.py            # KernelEvent, KernelOutput
  state.py              # ProtoSelfState
  kernel.py             # process_event
  appraisal.py          # perceive_event, update_drive_field
  self_model.py         # update_self_model
  cycles.py             # consolidate_cycles
  reflection.py         # maybe_reflect
  reducers.py           # derive_policy_hint, apply_updates
  boundary.py           # assert_no_direct_execution
  trace_types.py        # ProtoSelfTracePayload
  tests/*.py            # 25 个测试
```

### EgoCore（本次补充）

```
app/openemotion_adapter/
  __init__.py                       # 导出
  proto_self_adapter.py             # 已有
  proto_self_restore.py             # 已有
  proto_self_trace_bridge.py        # 已有

app/runtime_v2/loop.py              # 补充 external_result 回流 [178-211]

scripts/
  e2e_telegram_proto_self.py        # 新增验证脚本

artifacts/proto_self_v1/
  ACCEPTANCE_REPORT_20260324.md     # 本报告
```

---

## 6. 当前状态口径

**官方口径**: **已实现并通过代码层面验收，待真实 Telegram E2E 验证**

### 已确认

- ✅ Proto-Self Kernel v1 独立验收通过（25 单元测试）
- ✅ EgoCore Adapter 实现完整（normalize/load/save/trace）
- ✅ Runtime V2 正式主链接入（决策前 + 工具执行后）
- ✅ 代码层面验证通过（集成测试 + 接线点检查）
- ✅ 不破坏旧主链（失败时 graceful degradation）

### 待验证

- ⏳ 真实 Telegram 消息触发
- ⏳ 真实 cycle/memory 写入证据
- ⏳ 真实 external_result=failure 触发 reflection
- ⏳ 真实 trace 文件生成

---

## 7. 执行命令

```bash
# 代码验证
cd OpenEmotion && python -m pytest openemotion/proto_self/tests/ -v

# 集成验证
cd EgoCore && python -c "
import sys
sys.path.insert(0, r'D:\Project\AIProject\MyProject\Ego\OpenEmotion')
from app.runtime_v2.loop import RuntimeV2Loop
loop = RuntimeV2Loop()
print('Adapter attached:', loop.proto_self_adapter is not None)
"

# 启动 bot（真实 E2E 前）
cd EgoCore && python -m app.main --telegram

# 验证痕迹（真实 E2E 后）
cd EgoCore && python scripts/e2e_telegram_proto_self.py --verify --report
```

---

## 8. 结论

**Proto-Self Kernel v1 已正式接入 EgoCore Runtime V2 主链。**

接线点：
1. **决策前**: `loop.py:109` - 用户输入进入，返回 policy_hint/response_tendency
2. **工具执行后**: `loop.py:178-211` - external_result 回流，触发 reflection

状态持久化：
- Mirror: `artifacts/proto_self_mirror/state.json`
- Trace: `logs/proto_self_trace.jsonl`

**下一步**: 运行 `python -m app.main --telegram` 并发送测试消息，完成真实 E2E 验证。

---

*报告生成时间*: 2026-03-24
*验证者*: Claude Code (AI Agent)
*状态*: 代码层面验收通过，待真实运行验证

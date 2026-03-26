# P1 FAILURE_ATTRIBUTION

## 目标失败项
`EgoCore/tests/test_runtime_v2_minimal.py::test_runtime_v2_loop_runs_plan_act_complete`

## 归因结论
该失败当前应归类为：

> **旧测试与当前跨平台输入契约不一致**

不是当前证据下的首要归因：
- 不是 P1 helper 拆分直接引入的新主链回归
- 不是 state / transition / decision 更深层语义残留的首证
- 不是运行环境缺依赖导致的假失败

## 最小复现

### 复现字符串
测试当前直接构造：

```python
RuntimeV2Action.from_model_output(
    '{"type":"act","tool":"file","input":{"operation":"read","path":"' + str(target) + '"}}'
)
```

在 Windows 上，`str(target)` 形如：

```text
C:\Users\LEO\AppData\Local\Temp\pytest-of-LEO\pytest-1\test_runtime_v2_loop_runs_plan0\hello.html
```

该路径直接拼进 JSON 后，反斜杠未转义，导致 `json.loads()` 失败。

### 实际复现结果
- `RuntimeV2Action.from_model_output(...)` 返回：
  - `type = "ask"`
  - `raw.kind = "invalid_json"`
- `RuntimeV2Loop.run_turn_typed()` 因连续遇到 `invalid_json`，最终回到：
  - `status = "waiting_input"`

### 对照复现
当路径先做 JSON 转义后，同一场景在 Windows Python 下可得到：
- `status = "completed_verified"`
- `last_verification_result.passed = True`

## 责任点

| layer | responsibility | verdict |
|---|---|---|
| `EgoCore/tests/test_runtime_v2_minimal.py` | 直接手拼 JSON action 字符串 | **主责任点** |
| `RuntimeV2Action.from_model_output()` | 对非法 JSON 保守降级为 `ask/invalid_json` | 行为符合当前契约 |
| `RuntimeV2Loop.run_turn_typed()` | 遇到连续 `invalid_json` 后返回 `waiting_input` | 行为符合当前契约 |
| P1 helper 拆分 | proto-self/risk/evidence 迁移 | 当前未见直接导致该失败的证据 |

## 为什么不是 P1 新回归
- 同样的 `plan -> act -> complete` 流程，在 Windows 下只要把路径正确转义，就能得到 `completed_verified`
- 失败落点发生在 action 构造/解析之前置阶段，而不是 helper 拆分后的 proto-self/evidence side-effects
- 失败结果是 `invalid_json` 降级，不是 runtime orchestration 语义突变

## 是否必须修
结论：**建议修，但不是为了修主链，而是为了修测试契约。**

原因：
- 不修会持续把 Windows 路径字符串问题误报成 runtime 回归
- 修复范围可限制在测试文件，不必动 runtime 主链
- 当前它阻碍 P1 对“行为是否未破”的进一步判断

## 修完后影响范围

### 预计影响极小
- 目标文件：`EgoCore/tests/test_runtime_v2_minimal.py`
- 修法应为：使用 `json.dumps()` 或显式路径转义来构造测试 action
- 不应影响：
  - `RuntimeV2Loop`
  - `RuntimeV2Action`
  - `transition / state / decision`
  - 真实 Telegram / integration / simulated runner

## 当前状态
- 已修复
- 修复方式：`EgoCore/tests/test_runtime_v2_minimal.py` 改为使用 `json.dumps(..., ensure_ascii=False)` 构造 `plan / act / complete` action
- 修复后验证：
  - `cmd.exe /c py -3 -m pytest tests\test_runtime_v2_minimal.py::test_runtime_v2_loop_runs_plan_act_complete tests\test_runtime_v2_proto_self_runtime.py tests\test_runtime_v2_turn_result.py -q`
  - 结果：`8 passed`

## 当前能证明什么
- 能证明这条失败首先是测试构造的 Windows JSON 路径转义问题
- 能证明它不足以单独判定为 P1 新主链回归

## 当前不能证明什么
- 不能证明 P1 完全没有其他副作用
- 不能证明修完该测试后，所有 runtime 全量回归都会通过
- 不能证明更深层 state / transition / decision 完全无语义残留

# Contract Runtime Trace Schema

当前 Telegram native 主链的最小 contract runtime 事件 schema 为 `contract_runtime_v1`。

适用事件：
- `contract_locked`
- `next_step_decided`
- `step_verified`
- `need_relock`

统一 payload 字段：

```yaml
trace_schema: contract_runtime_v1
event_kind: contract_locked | next_step_decided | step_verified | need_relock
contract_phase: pending | contract_locked | step_selected | executing | verifying | re_lock_needed | completed
task_id: str | null
goal: str | null
success_criteria: list[str]
hard_constraints: list[str]
risk_level: low | medium | high | null
ask_needed: bool | null
step_id: str | null
action_type: reply | ask_user | call_tool | wait | finish | block | null
expected_signal: str | null
tool_name: str | null
need_relock: bool
expected_signal_matched: bool | null
stop_reason: str | null
contract_delta: dict
```

约束：
- `contract_locked` 必须带 `task_id / goal / success_criteria`
- `next_step_decided` 必须带 `step_id / action_type / expected_signal`
- `step_verified` 必须带 `expected_signal_matched / need_relock / stop_reason`
- `need_relock` 必须是单独事件，不能只靠 `step_verified.need_relock=true` 代替

当前证据等级：
- 代码与本地主回归已覆盖
- 真实 Telegram 样本仍需补一条公开可核验 artifact
